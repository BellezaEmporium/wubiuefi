import os
from pathlib import Path
import re
import logging
import shutil
import subprocess
import threading

log = logging.getLogger('btdownloader')


def _find_aria2c(root_dir=None):
    """Search for aria2c in known project locations."""
    candidates = []
    if root_dir:
        candidates += [
            str(Path(root_dir) / 'blobs' / 'aria2c.exe'),
            str(Path(root_dir) / 'bin' / 'aria2c.exe'),
        ]
    system = shutil.which('aria2c') or shutil.which('aria2c.exe')
    if system:
        candidates.append(system)
    for path in candidates:
        if path and Path(path).is_file():
            return path
    raise FileNotFoundError(
        "aria2c not found. Place aria2c.exe in the blobs/ or bin/ directory."
    )


def download(torrent_path_or_url, save_dir, associated_task=None,
             root_dir=None, web_proxy=None):
    """
    Downloads a file using aria2c with progress tracking.
    :param torrent_path_or_url: Path or URL to the .torrent file
    :param save_dir: Directory where the downloaded file will be saved
    :param associated_task: Optional task object for progress updates
    :param root_dir: Optional root directory to search for aria2c
    :param web_proxy: Optional web proxy URL (e.g., "http://proxy:port")
    :return: Path to the downloaded file
    :raises Exception: If the download fails or is cancelled
    """
    aria2c = _find_aria2c(root_dir)

    cmd = [
        aria2c,
        '--dir', save_dir,
        '--seed-time=0',          # do not seed after download
        '--summary-interval=1',   # display progress every second
        '--console-log-level=warn',
    ]

    if web_proxy:
        cmd += ['--all-proxy', web_proxy]

    cmd.append(torrent_path_or_url)

    if associated_task:
        associated_task.unit = "%"
        associated_task.size = 100
        associated_task.set_progress(0)

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding='utf-8',
        errors='replace',
        bufsize=1,
    )

    downloaded_file = None
    cancelled = False

    def _read_output():
        nonlocal downloaded_file, cancelled
        # aria2c shows : [#hash   SIZE/TOTAL(PCT%) CN:N DL:X MiB/s]
        pct_re = re.compile(r'\((\d+)%\)')
        # and at the end : "Download complete: /path/to/file"
        done_re = re.compile(r'Download complete:\s*(.+)')

        if proc.stdout is None:
            return
        for line in proc.stdout:
            line = line.strip()
            log.debug("aria2c: %s" % line)

            m = pct_re.search(line)
            if m and associated_task:
                pct = int(m.group(1))
                if associated_task.set_progress(pct):
                    cancelled = True
                    proc.terminate()
                    return

            m = done_re.search(line)
            if m:
                downloaded_file = m.group(1).strip()

    reader = threading.Thread(target=_read_output, daemon=True)
    reader.start()
    proc.wait()
    reader.join()

    if cancelled:
        raise Exception("Download cancelled by user")

    if proc.returncode != 0:
        raise Exception("aria2c failed with code %d" % proc.returncode)

    if not downloaded_file or not Path(downloaded_file).is_file():
        # Search for the file in save_dir if aria2c did not log the path
        files = [
            str(Path(save_dir) / f)
            for f in os.listdir(save_dir)
            if not f.endswith('.aria2')
        ]
        if files:
            downloaded_file = str(max(files, key=os.path.getmtime))
        else:
            raise Exception("Fichier téléchargé introuvable dans %s" % save_dir)

    if associated_task:
        associated_task.set_progress(100)
        associated_task.finish()

    return downloaded_file