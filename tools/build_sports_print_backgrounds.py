"""Vytvoří přesné tiskové podklady Sportovního dne pro každý formát a orientaci."""

from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "icons" / "print_backgrounds"

FORMATS = {
    "a3": (1754, 2480),
    "a4": (1240, 1754),
    "a5": (874, 1240),
    "a6": (620, 877),
    "letter": (1275, 1650),
    "legal": (1275, 2100),
}


def _portrait_variant(source: Image.Image, size: tuple[int, int]) -> Image.Image:
    """Zachová horní dekorace i spodní rekvizity; mění jen klidný střed."""
    target_width, target_height = size
    scaled_height = round(source.height * target_width / source.width)
    scaled = source.resize((target_width, scaled_height), Image.Resampling.LANCZOS)

    top_height = round(scaled_height * 0.25)
    bottom_height = round(scaled_height * 0.36)
    available_middle = max(1, target_height - top_height - bottom_height)
    source_middle = scaled.crop((0, top_height, target_width, scaled_height - bottom_height))
    source_middle = source_middle.resize((target_width, available_middle), Image.Resampling.LANCZOS)

    result = Image.new("RGB", (target_width, target_height), "#061923")
    result.paste(scaled.crop((0, 0, target_width, top_height)), (0, 0))
    result.paste(source_middle, (0, top_height))
    result.paste(
        scaled.crop((0, scaled_height - bottom_height, target_width, scaled_height)),
        (0, target_height - bottom_height),
    )
    return result


def _landscape_variant(source: Image.Image, size: tuple[int, int]) -> Image.Image:
    """Zachová levé i pravé pirátské rekvizity; mění jen prázdný střed."""
    target_width, target_height = size
    scaled_width = round(source.width * target_height / source.height)
    scaled = source.resize((scaled_width, target_height), Image.Resampling.LANCZOS)

    left_width = round(scaled_width * 0.24)
    right_width = round(scaled_width * 0.24)
    available_middle = max(1, target_width - left_width - right_width)
    source_middle = scaled.crop((left_width, 0, scaled_width - right_width, target_height))
    source_middle = source_middle.resize((available_middle, target_height), Image.Resampling.LANCZOS)

    result = Image.new("RGB", (target_width, target_height), "#061923")
    result.paste(scaled.crop((0, 0, left_width, target_height)), (0, 0))
    result.paste(source_middle, (left_width, 0))
    result.paste(
        scaled.crop((scaled_width - right_width, 0, scaled_width, target_height)),
        (target_width - right_width, 0),
    )
    return result


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    master_sets = {
        "": (
            Image.open(OUTPUT / "sports_print_master_portrait.png").convert("RGB"),
            Image.open(OUTPUT / "sports_print_master_landscape.png").convert("RGB"),
        ),
        "_eco": (
            Image.open(OUTPUT / "sports_print_master_portrait_eco.png").convert("RGB"),
            Image.open(OUTPUT / "sports_print_master_landscape_eco.png").convert("RGB"),
        ),
    }

    for suffix, (portrait, landscape) in master_sets.items():
        for paper_name, portrait_size in FORMATS.items():
            variants = {
                "portrait": _portrait_variant(portrait, portrait_size),
                "landscape": _landscape_variant(landscape, tuple(reversed(portrait_size))),
            }
            for orientation, image in variants.items():
                path = OUTPUT / f"sports_print_{paper_name}_{orientation}{suffix}.jpg"
                image.save(path, "JPEG", quality=94, subsampling=0, dpi=(150, 150), optimize=True)
                print(f"{path.name}: {image.width} x {image.height}")


if __name__ == "__main__":
    main()
