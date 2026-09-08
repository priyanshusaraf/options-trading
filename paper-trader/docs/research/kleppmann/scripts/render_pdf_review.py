#!/usr/bin/env python3
"""Create page-level text receipts and compact visual contact sheets for a PDF.

The output is ignored review evidence. Rendering does not mark a page inspected;
the human-readable source note must record the later direct visual review.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess


def run(*args: str) -> str:
    return subprocess.run(args, check=True, text=True, capture_output=True).stdout


def read_ppm(path: Path) -> tuple[int, int, bytes]:
    data = path.read_bytes()
    match = re.match(rb"P6\s+(?:#[^\n]*\n\s*)*(\d+)\s+(\d+)\s+255\s", data)
    if not match:
        raise ValueError(f"unsupported PPM header: {path}")
    width, height = int(match.group(1)), int(match.group(2))
    pixels = data[match.end() :]
    if len(pixels) != width * height * 3:
        raise ValueError(f"unexpected PPM payload: {path}")
    return width, height, pixels


def write_sheet(paths: list[Path], target: Path, columns: int, gap: int = 4) -> None:
    images = [read_ppm(path) for path in paths]
    width = max(item[0] for item in images)
    height = max(item[1] for item in images)
    rows = (len(images) + columns - 1) // columns
    sheet_width = columns * width + (columns + 1) * gap
    sheet_height = rows * height + (rows + 1) * gap
    white = bytes([255, 255, 255])
    canvas = bytearray(white * (sheet_width * sheet_height))
    for index, (image_width, image_height, pixels) in enumerate(images):
        row, column = divmod(index, columns)
        x0 = gap + column * (width + gap)
        y0 = gap + row * (height + gap)
        for y in range(image_height):
            source_start = y * image_width * 3
            target_start = ((y0 + y) * sheet_width + x0) * 3
            canvas[target_start : target_start + image_width * 3] = pixels[
                source_start : source_start + image_width * 3
            ]
    target.write_bytes(
        f"P6\n{sheet_width} {sheet_height}\n255\n".encode("ascii") + bytes(canvas)
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdf", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--slug", required=True)
    parser.add_argument("--pages-per-sheet", type=int, default=25)
    parser.add_argument("--columns", type=int, default=5)
    parser.add_argument("--thumbnail-size", type=int, default=280)
    args = parser.parse_args()

    target = args.output / args.slug
    pages_dir = target / "pages"
    text_dir = target / "text"
    sheets_dir = target / "sheets"
    pages_dir.mkdir(parents=True, exist_ok=True)
    text_dir.mkdir(parents=True, exist_ok=True)
    sheets_dir.mkdir(parents=True, exist_ok=True)

    metadata = run("pdfinfo", str(args.pdf))
    page_match = re.search(r"^Pages:\s+(\d+)$", metadata, re.MULTILINE)
    if not page_match:
        raise ValueError("pdfinfo did not report a page count")
    page_count = int(page_match.group(1))
    subprocess.run(
        [
            "pdftoppm",
            "-r",
            "72",
            "-scale-to",
            str(args.thumbnail_size),
            str(args.pdf),
            str(pages_dir / "page"),
        ],
        check=True,
    )

    image_counts: dict[int, int] = {}
    for line in run("pdfimages", "-list", str(args.pdf)).splitlines():
        match = re.match(r"\s*(\d+)\s+\d+\s+", line)
        if match:
            page = int(match.group(1))
            image_counts[page] = image_counts.get(page, 0) + 1

    receipt = []
    for page in range(1, page_count + 1):
        text_path = text_dir / f"page-{page:03d}.txt"
        subprocess.run(
            [
                "pdftotext",
                "-f",
                str(page),
                "-l",
                str(page),
                "-layout",
                str(args.pdf),
                str(text_path),
            ],
            check=True,
        )
        text = text_path.read_text(encoding="utf-8", errors="replace")
        receipt.append(
            {
                "page": page,
                "text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                "text_characters": len(text),
                "nonblank_lines": sum(bool(line.strip()) for line in text.splitlines()),
                "embedded_image_objects": image_counts.get(page, 0),
                "rendered": True,
                "direct_visual_inspection": False,
            }
        )

    page_files = sorted(pages_dir.glob("page-*.ppm"))
    if len(page_files) != page_count:
        raise ValueError(f"rendered {len(page_files)} pages, expected {page_count}")
    sheet_records = []
    for offset in range(0, page_count, args.pages_per_sheet):
        subset = page_files[offset : offset + args.pages_per_sheet]
        first_page = offset + 1
        last_page = offset + len(subset)
        ppm_path = sheets_dir / f"pages-{first_page:03d}-{last_page:03d}.ppm"
        png_path = ppm_path.with_suffix(".png")
        write_sheet(subset, ppm_path, args.columns)
        subprocess.run(
            ["sips", "-s", "format", "png", str(ppm_path), "--out", str(png_path)],
            check=True,
            stdout=subprocess.DEVNULL,
        )
        ppm_path.unlink()
        sheet_records.append(
            {
                "first_page": first_page,
                "last_page": last_page,
                "path": str(png_path),
                "sha256": hashlib.sha256(png_path.read_bytes()).hexdigest(),
            }
        )

    result = {
        "schema": "pdf-page-review-receipt/1",
        "source_pdf": str(args.pdf),
        "source_sha256": hashlib.sha256(args.pdf.read_bytes()).hexdigest(),
        "page_count": page_count,
        "pages": receipt,
        "contact_sheets": sheet_records,
        "visual_state": "rendered_pending_direct_inspection",
    }
    (target / "page-inspection.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({"slug": args.slug, "pages": page_count, "sheets": len(sheet_records)}))


if __name__ == "__main__":
    main()
