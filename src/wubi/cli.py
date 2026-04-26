from __future__ import annotations

import os
from argparse import ArgumentParser

from wubi.info import Info


def parse_args(info: Info, argv: list[str] | None = None) -> None:
    """
    Parse sys.argv (or a custom list) and write results directly into info.
    Separated from application.py so it can be unit-tested without spinning
    up a full Wubi instance.
    """
    parser = ArgumentParser(prog=info.application_name)

    # ── Verbosity ──────────────────────────────────────────────────
    verb = parser.add_mutually_exclusive_group()
    verb.add_argument("--quiet",   action="store_const", const="quiet",   dest="verbosity")
    verb.add_argument("--verbose", action="store_const", const="verbose", dest="verbosity")

    # ── Task selection ─────────────────────────────────────────────
    task = parser.add_mutually_exclusive_group()
    task.add_argument("--install",   action="store_const", const="install",   dest="run_task")
    task.add_argument("--uninstall", action="store_const", const="uninstall", dest="run_task")
    task.add_argument("--cdmenu",    action="store_const", const="cd_menu",   dest="run_task")
    task.add_argument("--cdboot",    action="store_const", const="cd_boot",   dest="run_task")
    task.add_argument("--showinfo",  action="store_const", const="show_info", dest="run_task")

    # ── Skip / override flags ──────────────────────────────────────
    parser.add_argument("--nobittorrent",    action="store_true", dest="no_bittorrent")
    parser.add_argument("--32bit",           action="store_true", dest="force_i386")
    parser.add_argument("--force-wubi",      action="store_true", dest="force_wubi")
    parser.add_argument("--skipmd5check",    action="store_true", dest="skip_md5_check")
    parser.add_argument("--skipsizecheck",   action="store_true", dest="skip_size_check")
    parser.add_argument("--skipmemorycheck", action="store_true", dest="skip_memory_check")
    parser.add_argument("--noninteractive",  action="store_true", dest="non_interactive")

    # ── Dev / debug ────────────────────────────────────────────────
    parser.add_argument("--test",  action="store_true", dest="test")
    parser.add_argument("--debug", action="store_true", dest="debug")

    # ── Value arguments ────────────────────────────────────────────
    parser.add_argument("--drive",        dest="target_drive")
    parser.add_argument("--size",         type=int,  dest="installation_size_mb")
    parser.add_argument("--locale",       dest="locale")
    parser.add_argument("--language",     dest="language")
    parser.add_argument("--username",     dest="username")
    parser.add_argument("--password",     dest="password")
    parser.add_argument("--distro",       dest="distro_name")
    parser.add_argument("--accessibility",dest="accessibility")
    parser.add_argument("--webproxy",     dest="web_proxy")
    parser.add_argument("--isopath",      dest="iso_path")
    parser.add_argument("--dimagepath",   dest="disk_image_path")
    parser.add_argument("--exefile",      dest="original_exe",  default=None)
    parser.add_argument("--log-file",     dest="log_file",      default=None)
    parser.add_argument("--interface",    dest="use_frontend",  default=None)

    args = parser.parse_args(argv)
    info.update(vars(args))

    # ── Post-parse fixups ──────────────────────────────────────────

    # --test / --debug both imply verbose output
    if info.test or info.debug:
        info.verbosity = "verbose"

    # If launched via an uninstall wrapper exe, force uninstall task
    if info.original_exe:
        exe = info.original_exe.strip().strip("'\"")
        info.original_exe = exe
        if os.path.basename(exe).lower().startswith("uninstall-"):
            info.run_task = "uninstall"