import time
import threading
import logging
from pathlib import Path
import httpx

log = logging.getLogger('downloader')

_MAX_OPEN_RETRIES = 5
_RETRY_DELAY_S    = 2.0


class DownloadProgress:
    def __init__(self, associated_task, cancel_event: threading.Event | None = None) -> None:
        self.associated_task = associated_task
        self._cancel_event = cancel_event or threading.Event()
        self._last_update_time: float | None = None
        self._last_bytes = 0
        self._speed_samples: list[float] = []

    def start(self, filename: str, url: str, basename: str, length: int, text: str) -> None:
        self.filename = filename
        self.url = url
        self.basename = basename
        self.length = length
        self._last_update_time = time.time()
        self._last_bytes = 0
        if self.associated_task:
            self.associated_task.size = max(length // 1024, 1)
        log.debug(f"Download start filename={filename} url={url} length={length}")
        if self.associated_task:
            self.associated_task.set_progress(0)

    def update(self, amount_read: int) -> bool:
        if self._cancel_event.is_set():
            return True
        if not self.associated_task:
            return False
        now = time.time()
        dt = now - (self._last_update_time or now)
        if dt >= 0.5:
            delta_kb = (amount_read - self._last_bytes) / 1024
            speed_kbps = delta_kb / dt if dt > 0 else 0
            self._speed_samples.append(speed_kbps)
            self._speed_samples = self._speed_samples[-6:]
            avg_speed = sum(self._speed_samples) / len(self._speed_samples)
            self._last_update_time = now
            self._last_bytes = amount_read
            cancelled = self.associated_task.set_progress(
                amount_read // 1024,
                speed=f"{int(avg_speed)} KB/s",
            )
            if cancelled:
                self._cancel_event.set()
                return True
        return False

    def end(self, amount_read: int) -> None:
        log.debug(f"Download finished ({amount_read} bytes)")
        if self.associated_task:
            self.associated_task.finish()


def download(
    url: str,
    filename: str | None = None,
    associated_task=None,
    web_proxy: str | None = None,
) -> str:
    if associated_task:
        associated_task.description = f"Downloading {Path(url).name}"
        associated_task.unit = "KB"
    log.debug(f"downloading {url} → {filename}")

    cancel_event = threading.Event()
    progress_obj = DownloadProgress(associated_task, cancel_event)
    proxies = {"http://": web_proxy, "https://": web_proxy} if web_proxy else {}

    dest = Path(filename) if filename else Path(url).name
    if dest.is_dir():
        dest = dest / Path(url).name

    with httpx.Client(proxies=proxies, follow_redirects=True, timeout=httpx.Timeout(5.0, read=60.0)) as client:
        with client.stream("GET", url) as response:
            response.raise_for_status()
            content_length = int(response.headers.get("content-length", 0))
            progress_obj.start(str(dest), url, dest.name, content_length, "")

            bytes_read = 0
            try:
                with open(dest, "wb") as f:
                    for chunk in response.iter_bytes(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            bytes_read += len(chunk)
                            if progress_obj.update(bytes_read):
                                log.info("Download cancelled — removing partial file")
                                break
            finally:
                if cancel_event.is_set() and dest.exists():
                    try:
                        dest.unlink()
                    except OSError as e:
                        log.warning(f"Could not remove partial file {dest}: {e}")
                elif not cancel_event.is_set():
                    progress_obj.end(bytes_read)

    if cancel_event.is_set():
        raise Exception("Download cancelled by user")

    for attempt in range(1, _MAX_OPEN_RETRIES + 1):
        try:
            with open(dest, "rb") as probe:
                probe.read(1)
            break
        except OSError:
            if attempt == _MAX_OPEN_RETRIES:
                raise RuntimeError(
                    f"File {dest.name} is still locked after {_MAX_OPEN_RETRIES} attempts. "
                    "An antivirus program may be scanning it. Please retry."
                )
            log.warning(f"File locked (attempt {attempt}/{_MAX_OPEN_RETRIES}), retrying in {_RETRY_DELAY_S}s…")
            time.sleep(_RETRY_DELAY_S)

    return str(dest)