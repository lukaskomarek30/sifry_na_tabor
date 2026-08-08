"""ZIP export and restore helpers for Sifrator user data."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import os
import shutil
import tempfile
import uuid
import zipfile

from app_paths import get_user_data_dir


BACKUP_FORMAT_VERSION = 1
BACKUP_APP_NAME = "Sifrator_Mraveniste"
BACKUP_MANIFEST_NAME = "sifrator_user_data_backup.json"
BACKUP_DATA_PREFIX = "user_data/"


class UserDataBackupError(RuntimeError):
    """Raised when a backup ZIP cannot be exported or restored safely."""


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def default_backup_filename(app_version: str = "") -> str:
    version = str(app_version or "").strip().lstrip("vV") or "data"
    safe_version = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in version)
    return f"sifrator_udaje_v{safe_version}_{_timestamp()}.zip"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _normalize_zip_name(name: str) -> str:
    return str(name or "").replace("\\", "/")


def _validate_zip_name(name: str) -> str:
    normalized = _normalize_zip_name(name)
    if not normalized or normalized.startswith("/"):
        raise UserDataBackupError(f"Neplatna cesta v ZIPu: {name!r}")
    first_part = normalized.split("/", 1)[0]
    if ":" in first_part:
        raise UserDataBackupError(f"Neplatna cesta v ZIPu: {name!r}")
    parts = [part for part in normalized.split("/") if part]
    if any(part == ".." for part in parts):
        raise UserDataBackupError(f"Neplatna cesta v ZIPu: {name!r}")
    return normalized


def _is_same_path(left: str, right: str) -> bool:
    try:
        return os.path.normcase(os.path.abspath(left)) == os.path.normcase(os.path.abspath(right))
    except Exception:
        return False


def _is_inside(path: str, root: str) -> bool:
    try:
        common = os.path.commonpath([os.path.abspath(path), os.path.abspath(root)])
        return _is_same_path(common, root)
    except Exception:
        return False


def _iter_source_files(source_dir: str, output_path: str | None = None):
    source_dir = os.path.abspath(source_dir)
    output_path = os.path.abspath(output_path) if output_path else ""
    if not os.path.isdir(source_dir):
        return
    for current_root, dirs, files in os.walk(source_dir):
        dirs[:] = [name for name in dirs if name != "__pycache__"]
        for file_name in sorted(files):
            source_path = os.path.join(current_root, file_name)
            if output_path and _is_same_path(source_path, output_path):
                continue
            if file_name.endswith(".tmp"):
                continue
            rel_path = os.path.relpath(source_path, source_dir).replace(os.sep, "/")
            yield source_path, rel_path


def export_user_data_zip(output_path: str, app_version: str = "", source_dir: str | None = None) -> dict:
    """Export the complete user data directory into a backup ZIP."""
    if not output_path:
        raise UserDataBackupError("Neni vybrana cesta pro ulozeni zalohy.")

    target_path = os.path.abspath(output_path)
    if not target_path.lower().endswith(".zip"):
        target_path += ".zip"
    os.makedirs(os.path.dirname(target_path) or ".", exist_ok=True)

    source_root = os.path.abspath(source_dir or get_user_data_dir())
    os.makedirs(source_root, exist_ok=True)
    files = list(_iter_source_files(source_root, target_path))

    manifest = {
        "app": BACKUP_APP_NAME,
        "format": BACKUP_FORMAT_VERSION,
        "created_at": _utc_now_iso(),
        "app_version": str(app_version or ""),
        "data_prefix": BACKUP_DATA_PREFIX,
        "file_count": len(files),
    }

    descriptor, temp_path = tempfile.mkstemp(
        prefix="sifrator_udaje_", suffix=".zip.tmp", dir=os.path.dirname(target_path) or "."
    )
    os.close(descriptor)
    try:
        total_bytes = 0
        with zipfile.ZipFile(temp_path, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr(
                BACKUP_MANIFEST_NAME,
                json.dumps(manifest, ensure_ascii=False, indent=2),
            )
            for source_path, rel_path in files:
                archive_name = BACKUP_DATA_PREFIX + rel_path
                archive.write(source_path, archive_name)
                try:
                    total_bytes += os.path.getsize(source_path)
                except OSError:
                    pass
        os.replace(temp_path, target_path)
    except Exception as error:
        try:
            os.unlink(temp_path)
        except OSError:
            pass
        if isinstance(error, UserDataBackupError):
            raise
        raise UserDataBackupError(f"Zalohu se nepodarilo vytvorit: {error}") from error

    return {
        "path": target_path,
        "source_dir": source_root,
        "file_count": len(files),
        "bytes": total_bytes,
    }


def inspect_user_data_backup(zip_path: str) -> dict:
    """Validate a backup ZIP and return a short summary."""
    if not zip_path or not os.path.exists(zip_path):
        raise UserDataBackupError("Vybrany ZIP neexistuje.")
    if not zipfile.is_zipfile(zip_path):
        raise UserDataBackupError("Vybrany soubor neni platny ZIP.")

    with zipfile.ZipFile(zip_path, "r") as archive:
        members = archive.infolist()
        names = [_validate_zip_name(member.filename) for member in members]
        if BACKUP_MANIFEST_NAME not in names:
            raise UserDataBackupError("ZIP neobsahuje manifest zalohy Sifratoru.")
        try:
            manifest = json.loads(archive.read(BACKUP_MANIFEST_NAME).decode("utf-8"))
        except Exception as error:
            raise UserDataBackupError(f"Manifest zalohy nejde nacist: {error}") from error

        if manifest.get("app") != BACKUP_APP_NAME:
            raise UserDataBackupError("ZIP nevypada jako zaloha teto aplikace.")
        if int(manifest.get("format", 0) or 0) != BACKUP_FORMAT_VERSION:
            raise UserDataBackupError("ZIP ma nepodporovanou verzi formatu zalohy.")

        data_files = [
            member
            for member in members
            if _normalize_zip_name(member.filename).startswith(BACKUP_DATA_PREFIX)
            and not member.is_dir()
        ]
        total_bytes = sum(max(0, int(member.file_size or 0)) for member in data_files)

    return {
        "path": os.path.abspath(zip_path),
        "manifest": manifest,
        "file_count": len(data_files),
        "bytes": total_bytes,
        "created_at": manifest.get("created_at", ""),
        "app_version": manifest.get("app_version", ""),
    }


def _extract_backup_data(zip_path: str, destination: str) -> int:
    os.makedirs(destination, exist_ok=True)
    extracted = 0
    destination_abs = os.path.abspath(destination)
    with zipfile.ZipFile(zip_path, "r") as archive:
        for member in archive.infolist():
            name = _validate_zip_name(member.filename)
            if member.is_dir() or not name.startswith(BACKUP_DATA_PREFIX):
                continue
            rel_name = name[len(BACKUP_DATA_PREFIX):].strip("/")
            if not rel_name:
                continue
            target_path = os.path.abspath(os.path.join(destination_abs, *rel_name.split("/")))
            if not _is_inside(target_path, destination_abs):
                raise UserDataBackupError(f"Neplatna cesta v ZIPu: {name!r}")
            os.makedirs(os.path.dirname(target_path), exist_ok=True)
            with archive.open(member, "r") as source, open(target_path, "wb") as target:
                shutil.copyfileobj(source, target)
            extracted += 1
    return extracted


def _unique_restore_dir(parent: str, base_name: str) -> str:
    stamp = _timestamp()
    candidate = os.path.join(parent, f"{base_name}_pred_importem_{stamp}")
    if not os.path.exists(candidate):
        return candidate
    for index in range(2, 1000):
        candidate = os.path.join(parent, f"{base_name}_pred_importem_{stamp}_{index}")
        if not os.path.exists(candidate):
            return candidate
    raise UserDataBackupError("Nepodarilo se pripravit docasnou slozku pro import.")


def _make_work_dir(parent: str, prefix: str) -> str:
    os.makedirs(parent, exist_ok=True)
    for _attempt in range(100):
        candidate = os.path.join(parent, f"{prefix}_{uuid.uuid4().hex}")
        try:
            os.makedirs(candidate, exist_ok=False)
            return candidate
        except FileExistsError:
            continue
    raise UserDataBackupError("Nepodarilo se pripravit pracovni slozku pro import.")


def import_user_data_zip(
    zip_path: str,
    app_version: str = "",
    target_dir: str | None = None,
    automatic_backup_dir: str | None = None,
) -> dict:
    """Replace the current user data directory with the content of a backup ZIP."""
    info = inspect_user_data_backup(zip_path)
    target_root = os.path.abspath(target_dir or get_user_data_dir())
    parent_dir = os.path.dirname(target_root)
    os.makedirs(parent_dir, exist_ok=True)

    backup_dir = os.path.abspath(automatic_backup_dir or parent_dir)
    os.makedirs(backup_dir, exist_ok=True)
    automatic_backup_path = os.path.join(
        backup_dir,
        f"sifrator_zaloha_pred_importem_{_timestamp()}.zip",
    )
    backup_stats = export_user_data_zip(
        automatic_backup_path,
        app_version=app_version,
        source_dir=target_root,
    )

    temp_root = _make_work_dir(parent_dir, "sifrator_import")
    extracted_root = os.path.join(temp_root, "user_data")
    previous_root = ""
    try:
        imported_files = _extract_backup_data(zip_path, extracted_root)
        previous_root = _unique_restore_dir(parent_dir, os.path.basename(target_root) or BACKUP_APP_NAME)
        if os.path.exists(target_root):
            os.replace(target_root, previous_root)
        try:
            shutil.copytree(extracted_root, target_root)
        except Exception:
            if os.path.exists(target_root):
                shutil.rmtree(target_root, ignore_errors=True)
            if previous_root and os.path.exists(previous_root):
                os.replace(previous_root, target_root)
            raise
        if previous_root and os.path.exists(previous_root):
            shutil.rmtree(previous_root, ignore_errors=True)
    except Exception as error:
        if isinstance(error, UserDataBackupError):
            raise
        raise UserDataBackupError(f"Import zalohy se nepodaril: {error}") from error
    finally:
        shutil.rmtree(temp_root, ignore_errors=True)

    return {
        "target_dir": target_root,
        "backup_path": backup_stats["path"],
        "imported_files": imported_files,
        "backup_file_count": backup_stats["file_count"],
        "source_created_at": info.get("created_at", ""),
        "source_app_version": info.get("app_version", ""),
    }
