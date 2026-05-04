"""CLI entry point for ABC calibration."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from calibration.abc import RejectionABC


def main() -> None:
    parser = argparse.ArgumentParser(description="Run ABC calibration for EvoSeer")
    parser.add_argument(
        "--config",
        default="calibration/config/default_calibration.yaml",
        help="Path to calibration YAML config",
    )
    parser.add_argument(
        "--output",
        default="calibration_results.json",
        help="Path to write results JSON",
    )
    args = parser.parse_args()

    abc = RejectionABC(args.config)
    result = abc.run()

    Path(args.output).write_text(result.to_json())

    print(f"\nDone.")
    print(f"  acceptance rate : {result.acceptance_rate:.2%}")
    print(f"  accepted samples: {len(result.accepted)}")
    print(f"  results written : {args.output}")


if __name__ == "__main__":
    main()
