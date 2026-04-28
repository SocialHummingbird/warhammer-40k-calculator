from __future__ import annotations

import argparse
from pathlib import Path

from warhammer.base_sizes import (
    BASE_SIZE_GUIDE_URL,
    download_base_size_pdf,
    parse_base_size_pdf,
    write_base_size_guide_csv,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract the official Warhammer 40,000 base-size guide to CSV.")
    parser.add_argument("--pdf", type=Path, default=Path("data/base_sizes/chapter_approved_tournament_companion_2026_01.pdf"))
    parser.add_argument("--output", type=Path, default=Path("data/base_sizes/base_size_guide.csv"))
    parser.add_argument("--url", default=BASE_SIZE_GUIDE_URL)
    parser.add_argument("--download", action="store_true", help="Download the PDF first if it is not already present.")
    args = parser.parse_args()

    if args.download:
        download_base_size_pdf(args.pdf, url=args.url)
    if not args.pdf.exists():
        parser.error(f"PDF not found: {args.pdf}. Re-run with --download or provide --pdf.")

    records = parse_base_size_pdf(args.pdf)
    write_base_size_guide_csv(records, args.output)
    print(f"Wrote {len(records)} base-size rows to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
