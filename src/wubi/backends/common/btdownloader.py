# Copyright (c) 2008 Agostino Russo
#
# BitTorrent downloading is currently disabled.
# libtorrent does not support Python 3.13.
# The caller in backend.py will fall back to HTTP automatically.

import logging

log = logging.getLogger('btdownloader')


class DownloadError(Exception):
    pass


def download(url, filename, associated_task=None):
    log.info("BitTorrent download skipped (disabled), falling back to HTTP.")
    return None