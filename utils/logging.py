"""Colored logging setup for EvoSeer CLI tools."""

from __future__ import annotations

import logging

_RESET  = "\033[0m"
_BOLD   = "\033[1m"
_DIM    = "\033[2m"
_RED    = "\033[31m"
_GREEN  = "\033[32m"
_YELLOW = "\033[33m"
_CYAN   = "\033[36m"
_GREY   = "\033[90m"

_LEVEL_COLORS = {
    logging.DEBUG:   _GREY,
    logging.INFO:    _CYAN,
    logging.WARNING: _YELLOW,
    logging.ERROR:   _RED,
}

_MSG_HIGHLIGHTS: list[tuple[str, str]] = [
    ("✓ accepted",      _GREEN + _BOLD),
    ("✗ rejected_early", _RED),
    ("✗ rejected",       _RED),
    ("hit max_sims",     _YELLOW),
]

LEVELS = {
    "debug":   logging.DEBUG,
    "verbose": logging.DEBUG,
    "info":    logging.INFO,
    "warning": logging.WARNING,
    "error":   logging.ERROR,
}


_NAME_WIDTH = 20


class ColorFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        level_color = _LEVEL_COLORS.get(record.levelno, "")
        level_str = f"{level_color}{record.levelname:<8}{_RESET}"
        name = f"{_DIM}{record.name:<{_NAME_WIDTH}}{_RESET}"

        msg = record.getMessage()
        for keyword, color in _MSG_HIGHLIGHTS:
            if keyword in msg:
                msg = msg.replace(keyword, f"{color}{keyword}{_RESET}", 1)
                break

        return f"{level_str} {name} — {msg}"


def setup_logging(level: str = "info") -> None:
    """Configure root logger with colored output. Call once at CLI entry point."""
    handler = logging.StreamHandler()
    handler.setFormatter(ColorFormatter())
    logging.basicConfig(level=LEVELS[level], handlers=[handler])
