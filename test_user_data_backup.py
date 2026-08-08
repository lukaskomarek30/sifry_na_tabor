import json
import os
import shutil
import unittest
import uuid
import zipfile

from user_data_backup import (
    UserDataBackupError,
    export_user_data_zip,
    import_user_data_zip,
    inspect_user_data_backup,
)


PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
TEST_TMP_DIR = os.path.join(PROJECT_DIR, "tmp", "tests")


class TemporaryWorkspace:
    def __enter__(self):
        os.makedirs(TEST_TMP_DIR, exist_ok=True)
        self.path = os.path.join(TEST_TMP_DIR, f"backup_{uuid.uuid4().hex}")
        os.makedirs(self.path, exist_ok=False)
        return self.path

    def __exit__(self, exc_type, exc, traceback):
        shutil.rmtree(self.path, ignore_errors=True)
        return False


def temporary_workspace() -> TemporaryWorkspace:
    os.makedirs(TEST_TMP_DIR, exist_ok=True)
    return TemporaryWorkspace()


class UserDataBackupTests(unittest.TestCase):
    def test_export_and_import_replaces_user_data_with_safety_backup(self):
        with temporary_workspace() as folder:
            source = os.path.join(folder, "source")
            target = os.path.join(folder, "target")
            automatic_backups = os.path.join(folder, "automatic_backups")
            os.makedirs(os.path.join(source, "groups"), exist_ok=True)
            os.makedirs(os.path.join(source, "planner_attachments"), exist_ok=True)
            os.makedirs(target, exist_ok=True)

            with open(os.path.join(source, "historie_zprav.json"), "w", encoding="utf-8") as file:
                json.dump([{"cipher": "Morse"}], file)
            with open(os.path.join(source, "groups", "oddily.json"), "w", encoding="utf-8") as file:
                json.dump({"groups": [{"name": "Prvni"}]}, file)
            with open(os.path.join(source, "planner_attachments", "note.txt"), "w", encoding="utf-8") as file:
                file.write("priloha")
            with open(os.path.join(target, "old.json"), "w", encoding="utf-8") as file:
                json.dump({"old": True}, file)

            backup_path = os.path.join(folder, "backup.zip")
            export_stats = export_user_data_zip(backup_path, app_version="0.0.test", source_dir=source)
            info = inspect_user_data_backup(backup_path)

            self.assertEqual(3, export_stats["file_count"])
            self.assertEqual(3, info["file_count"])
            self.assertEqual("0.0.test", info["app_version"])

            import_stats = import_user_data_zip(
                backup_path,
                app_version="0.0.test",
                target_dir=target,
                automatic_backup_dir=automatic_backups,
            )

            self.assertEqual(3, import_stats["imported_files"])
            self.assertFalse(os.path.exists(os.path.join(target, "old.json")))
            self.assertTrue(os.path.exists(os.path.join(target, "groups", "oddily.json")))
            self.assertTrue(os.path.exists(os.path.join(target, "planner_attachments", "note.txt")))
            self.assertTrue(os.path.exists(import_stats["backup_path"]))

            with zipfile.ZipFile(import_stats["backup_path"], "r") as archive:
                self.assertIn("user_data/old.json", archive.namelist())

    def test_import_rejects_zip_path_traversal(self):
        with temporary_workspace() as folder:
            bad_zip = os.path.join(folder, "bad.zip")
            with zipfile.ZipFile(bad_zip, "w", zipfile.ZIP_DEFLATED) as archive:
                archive.writestr(
                    "sifrator_user_data_backup.json",
                    json.dumps({"app": "Sifrator_Mraveniste", "format": 1}),
                )
                archive.writestr("user_data/../evil.txt", "nope")

            with self.assertRaises(UserDataBackupError):
                inspect_user_data_backup(bad_zip)


if __name__ == "__main__":
    unittest.main()
