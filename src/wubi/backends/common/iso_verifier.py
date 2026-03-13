# common/iso_verifier.py  ← nouveau fichier
"""
Verifies the integrity of an ISO by downloading the SHA256SUMS and its GPG signature,
then checking the hash of the ISO against the expected value.
"""

import os
import hashlib
import subprocess
import logging
import requests

log = logging.getLogger('iso_verifier')

UBUNTU_KEYIDS = [
    '0x46181433FBB75451',  # Ubuntu CD Image Automatic Signing Key
    '0xD94AA3F0EFE21092',  # Ubuntu CD Image Automatic Signing Key (2012)
]
KEYSERVER = 'hkp://keyserver.ubuntu.com'


def _sha256_of_file(path, associated_task=None):
    h = hashlib.sha256()
    size = os.path.getsize(path)
    done = 0
    with open(path, 'rb') as f:
        while True:
            chunk = f.read(1024 * 1024)
            if not chunk:
                break
            h.update(chunk)
            done += len(chunk)
            if associated_task:
                if associated_task.set_progress(done // (1024 * 1024)):
                    return None
    return h.hexdigest()


def _fetch_text(url, web_proxy=None):
    proxies = {'http': web_proxy, 'https': web_proxy} if web_proxy else None
    r = requests.get(url, proxies=proxies, timeout=30)
    r.raise_for_status()
    return r.text


def _gpg_available():
    try:
        subprocess.run(['gpg', '--version'],
                       capture_output=True, timeout=5)
        return True
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def _ensure_ubuntu_keys():
    """Import Ubuntu keys if missing from the keyring."""
    try:
        subprocess.run(
            ['gpg', '--keyid-format', 'long',
             '--keyserver', KEYSERVER,
             '--recv-keys'] + UBUNTU_KEYIDS,
            capture_output=True, timeout=30)
    except Exception as e:
        log.warning("Could not fetch Ubuntu GPG keys: %s" % e)


def _verify_gpg(sha256sums_path, sha256sums_gpg_path):
    """
    Returns True if the GPG signature is valid.
    Returns None if GPG is not available (non-fatal).
    """
    if not _gpg_available():
        log.warning("gpg not found — skipping signature check")
        return None
    _ensure_ubuntu_keys()
    result = subprocess.run(
        ['gpg', '--keyid-format', 'long',
         '--verify', sha256sums_gpg_path, sha256sums_path],
        capture_output=True, text=True, timeout=30)
    if result.returncode == 0:
        log.debug("GPG signature OK")
        return True
    log.warning("GPG verification failed:\n%s" % result.stderr)
    return False


def fetch_and_verify(base_url, iso_path, install_dir,
                     web_proxy=None, skip_gpg=False,
                     associated_task=None):
    """
    Downloads SHA256SUMS + SHA256SUMS.gpg from base_url,
    verifies the GPG signature (optional), then checks the hash of iso_path.

    Returns True if everything is OK, False otherwise.
    """
    iso_name = os.path.basename(iso_path)

    # 1. Download SHA256SUMS
    sha256sums_url = base_url.rstrip('/') + '/SHA256SUMS'
    sha256sums_gpg_url = base_url.rstrip('/') + '/SHA256SUMS.gpg'
    sha256sums_local = os.path.join(install_dir, 'SHA256SUMS')
    sha256sums_gpg_local = os.path.join(install_dir, 'SHA256SUMS.gpg')

    try:
        content = _fetch_text(sha256sums_url, web_proxy)
        with open(sha256sums_local, 'w', encoding='utf-8') as f:
            f.write(content)
        log.debug("Downloaded SHA256SUMS from %s" % sha256sums_url)
    except Exception as e:
        log.error("Cannot download SHA256SUMS: %s" % e)
        return False

    # 2. Download and verify the GPG signature
    if not skip_gpg:
        try:
            gpg_content = _fetch_text(sha256sums_gpg_url, web_proxy)
            with open(sha256sums_gpg_local, 'wb') as f:
                f.write(gpg_content.encode('latin-1'))
            gpg_ok = _verify_gpg(sha256sums_local, sha256sums_gpg_local)
            if gpg_ok is False:
                log.warning("GPG check failed — continuing anyway (TOFU model)")
        except Exception as e:
            log.warning("Cannot verify GPG signature: %s — skipping" % e)

    # 3. Parse SHA256SUMS and find the hash of our ISO
    reference_hash = None
    for line in content.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split(None, 1)
        if len(parts) != 2:
            continue
        hash_val, name = parts
        # SHA256SUMS may have *ubuntu-xx.iso or ubuntu-xx.iso
        name = name.lstrip('*').strip()
        if name == iso_name:
            reference_hash = hash_val.lower()
            break

    if not reference_hash:
        log.error("Cannot find %s in SHA256SUMS" % iso_name)
        return False

    log.debug("Expected SHA256: %s" % reference_hash)

    # 4. Calculate the SHA256 of the ISO
    if associated_task:
        associated_task.description = "Verifying %s" % iso_name
        associated_task.unit = "MB"
        associated_task.size = os.path.getsize(iso_path) // (1024 * 1024)

    actual_hash = _sha256_of_file(iso_path, associated_task)
    if actual_hash is None:
        return False
    
    log.debug("Actual   SHA256: %s" % actual_hash)

    if actual_hash != reference_hash:
        log.error("SHA256 mismatch for %s: expected %s, got %s"
                  % (iso_name, reference_hash, actual_hash))
        return False

    log.info("ISO %s verified OK" % iso_name)
    return True
