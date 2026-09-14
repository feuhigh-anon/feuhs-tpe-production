"""Build a protocol-shaped qualitative summary from a historical export.

This is a rehearsal artifact. It does not call an LLM and must not be used as
the current school-year teacher report. It exercises the same output contract
that an approved LLM provider will populate later.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from feval.ingestion import load_and_normalize
from feval.qualitative_summary import build_protocol_qualitative_summary
from feval.questions import get_question_block


DEFAULT_SOURCE = ROOT / "Students Evaluation" / "tpe" / "tpe_2024-2025_02.csv"
DEFAULT_OUTPUT = ROOT / "exports" / "qualitative_review" / "protocol_rehearsal.csv"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--block", choices=("shs", "jhs"), required=True)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    normalized = load_and_normalize(args.source, get_question_block(args.block))
    summary = build_protocol_qualitative_summary(normalized)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(args.output, index=False)
    print(f"Wrote {len(summary)} protocol rehearsal rows to {args.output}")
    print("generation_mode=deterministic_rehearsal; no LLM was called")


if __name__ == "__main__":
    main()