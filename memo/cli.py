from __future__ import annotations

import argparse

from .generator import generate_memo_pdf
from .schema import load_memo_data


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a branded memo PDF.")
    parser.add_argument("--input", required=True, help="Path to YAML/JSON memo input file")
    parser.add_argument("--output", required=True, help="Path to output PDF file")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    memo = load_memo_data(args.input)
    out = generate_memo_pdf(memo, args.output)
    print(f"Generated memo PDF: {out}")


if __name__ == "__main__":
    main()
