from __future__ import annotations

import logging
import os
import sys
import tempfile

from wubi.info import Info


def setup_logger(info: Info, log_to_console: bool = True) -> None:
    """
    Configure root logger with:
      - a file handler (always DEBUG level, written to info.log_file)
      - an optional stderr handler (level driven by info.verbosity)

    Kept separate from application.py so tests can call it with a
    temporary log path without side-effects on the real log file.
    """
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)

    # Clear any handlers that may have been added by an earlier call
    for h in list(root.handlers):
        root.removeHandler(h)

    # ── File handler ───────────────────────────────────────────────
    if not info.log_file or info.log_file.lower() != "none":
        if not info.log_file:
            filename = (info.full_application_name or "wubi") + ".log"
            info.log_file = os.path.join(tempfile.gettempdir(), filename)

        fh = logging.FileHandler(info.log_file, encoding="utf-8")
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(logging.Formatter(
            "%(asctime)s %(levelname)-6s %(name)s: %(message)s",
            datefmt="%m-%d %H:%M",
        ))
        root.addHandler(fh)

    # ── Console handler (stderr) ───────────────────────────────────
    # Suppressed when running as a packaged exe (original_exe is set)
    if log_to_console and not info.original_exe:
        level_map = {
            "verbose": logging.DEBUG,
            "quiet":   logging.ERROR,
        }
        ch = logging.StreamHandler(sys.stderr)
        ch.setLevel(level_map.get(info.verbosity or "", logging.INFO))
        ch.setFormatter(logging.Formatter("%(levelname)-6s %(message)s"))
        root.addHandler(ch)