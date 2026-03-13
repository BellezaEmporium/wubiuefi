import os
import logging
from threading import Event
from aiotorrent import Torrent
import asyncio

log = logging.getLogger('btdownloader')

stop_signal = Event()

class DownloadError(Exception):
    pass

async def download(torrent_path, filename, associated_task=None):
    log.debug("parsing torrent %s > %s" % (torrent_path, filename))
    torrent = Torrent(torrent_path)
    loop = asyncio.get_event_loop()
    loop.run_until_complete(torrent.download(file=torrent_path))

    if associated_task:
        associated_task.description = ("Parsing %s") % os.path.basename(torrent_path)
        associated_task.unit = "KB"
        associated_task.set_progress(0)

    def set_saveas(default, size, filename, dir):
        '''set final saveas'''
        return filename

    def stop_download():
        return stop_signal.is_set()

    def on_progress(kargs):
        # get the file size and percent completed from the torrent client
        if torrent and torrent.files:
            torr_file = torrent.files[0]  # Assuming single file torrent
            file_size = torr_file.length
            total_download = float(file_size)*1024
            percent_completed = float(kargs.get("fractionDone", 0))
            percent_completed = min(0.99, percent_completed)
            size = 1
            if percent_completed:
                size = total_download/percent_completed
                percent_completed = size*percent_completed
            if associated_task:
                associated_task.size = size
                if associated_task.set_progress(percent_completed):
                    stop_signal.set()
        else:
            log.warning("Torrent has no files, cannot report progress")


    def finish_callback():
        if associated_task:
            associated_task.finish()
        stop_signal.set()

    def error_callback(message):
        raise DownloadError(message)

    return filename