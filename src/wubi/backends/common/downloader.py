import os
import time
import threading
import logging
import requests

log = logging.getLogger('downloader')


class DownloadProgress(object):
    def __init__(self, associated_task, cancel_event=None):
        self.associated_task = associated_task
        self._cancel_event = cancel_event or threading.Event()
        self._last_update_time = None
        self._last_bytes = 0
        self._speed_samples = []

    def start(self, filename, url, basename, length, text):
        self.filename = filename
        self.url = url
        self.basename = basename
        self.length = length
        self._last_update_time = time.time()
        self._last_bytes = 0
        if self.associated_task:
            self.associated_task.size = max(length // 1024, 1)
        log.debug("Download start filename=%s url=%s length=%s" % (filename, url, length))
        if self.associated_task:
            self.associated_task.set_progress(0)

    def update(self, amount_read):
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
                speed="%i KB/s" % int(avg_speed)
            )
            if cancelled:
                self._cancel_event.set()
                return True
        return False

    def end(self, amount_read):
        log.debug("Download finished (%s bytes)" % amount_read)
        if self.associated_task:
            self.associated_task.finish()


def download(url, filename=None, associated_task=None, web_proxy=None):
    if associated_task:
        associated_task.description = "Downloading %s" % os.path.basename(url)
        associated_task.unit = "KB"
    log.debug("downloading %s > %s" % (url, filename))

    cancel_event = threading.Event()
    progress_obj = DownloadProgress(associated_task, cancel_event)
    proxies = {'http': web_proxy, 'https': web_proxy} if web_proxy else None

    if filename and os.path.isdir(filename):
        filename = os.path.join(filename, os.path.basename(url))
    if filename is None:
        filename = os.path.basename(url)

    response = requests.get(url, proxies=proxies, stream=True, timeout=30)
    response.raise_for_status()

    content_length = int(response.headers.get('content-length', 0))
    progress_obj.start(filename, url, os.path.basename(url), content_length, "")

    bytes_read = 0
    try:
        with open(filename, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    bytes_read += len(chunk)
                    if progress_obj.update(bytes_read):
                        log.info("Download cancelled — suppression du fichier partiel")
                        response.close()
                        break
    finally:
        if cancel_event.is_set() and os.path.exists(filename):
            try:
                os.remove(filename)
            except OSError as e:
                log.warning("Impossible de supprimer le fichier partiel %s : %s" % (filename, e))
        elif not cancel_event.is_set():
            progress_obj.end(bytes_read)

    if cancel_event.is_set():
        raise Exception("Download cancelled by user")

    return filename
