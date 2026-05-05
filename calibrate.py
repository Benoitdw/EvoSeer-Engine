"""CLI entry point for ABC calibration."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from calibration.abc import RejectionABC
from utils.logging import LEVELS, setup_logging

logger = logging.getLogger(__name__)


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
    parser.add_argument(
        "--log-level",
        default="info",
        choices=list(LEVELS),
        metavar="LEVEL",
        help="Logging verbosity: debug/verbose, info (default), warning, error",
    )
    args = parser.parse_args()

    setup_logging(args.log_level)

    logger.debug("config=%s  output=%s", args.config, args.output)

    abc = RejectionABC(args.config)
    result = abc.run()

    Path(args.output).write_text(result.to_json())

    logger.info("acceptance rate : %.2f%%", result.acceptance_rate * 100)
    logger.info("accepted samples: %d", len(result.accepted))
    logger.info("results written : %s", args.output)


if __name__ == "__main__":
    main()
