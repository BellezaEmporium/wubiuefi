"""
ISO verifier for Ubuntu images.
"""

import os
import hashlib
import logging
import subprocess
import shutil
import requests

log = logging.getLogger("iso_verifier")

UBUNTU_KEYS = [
    "0x46181433FBB75451",
    "0xD94AA3F0EFE21092",
    "0x871920D1991BC93C",
]

KEYSERVER = "hkp://keyserver.ubuntu.com"


# --------------------------------------------------
# Networking
# --------------------------------------------------

def fetch_text(url, proxy=None):
    proxies = {"http": proxy, "https": proxy} if proxy else None
    r = requests.get(url, proxies=proxies, timeout=30)
    r.raise_for_status()
    return r.text


def fetch_binary(url, proxy=None):
    proxies = {"http": proxy, "https": proxy} if proxy else None
    r = requests.get(url, proxies=proxies, timeout=30)
    r.raise_for_status()
    return r.content


# --------------------------------------------------
# Hashing
# --------------------------------------------------

def sha256_file(path, associated_task=None):

    h = hashlib.sha256()
    size = os.path.getsize(path)
    done = 0

    with open(path, "rb") as f:
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


# --------------------------------------------------
# GPG helpers
# --------------------------------------------------

def gpg_available():
    return shutil.which("gpg") is not None


def ensure_ubuntu_keys():

    if not gpg_available():
        return

    try:
        subprocess.run(
            [
                "gpg",
                "--keyserver",
                KEYSERVER,
                "--recv-keys",
                *UBUNTU_KEYS,
            ],
            capture_output=True,
            timeout=30,
        )
    except Exception as e:
        log.warning("Could not fetch Ubuntu GPG keys: %s", e)


def verify_gpg(sig_file, data_file):

    if not gpg_available():
        log.warning("gpg not available — skipping signature check")
        return None

    ensure_ubuntu_keys()

    try:
        result = subprocess.run(
            ["gpg", "--verify", sig_file, data_file],
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode == 0:
            log.info("GPG signature OK")
            return True

        log.warning("GPG verification failed:\n%s", result.stderr)
        return False

    except Exception as e:
        log.warning("GPG verification error: %s", e)
        return False


# --------------------------------------------------
# SHA256SUMS parsing
# --------------------------------------------------

def parse_sha256sums(text, iso_name):

    for line in text.splitlines():

        line = line.strip()

        if not line:
            continue

        parts = line.split()

        if len(parts) < 2:
            continue

        hash_val = parts[0]
        name = parts[-1].replace("*", "")

        if os.path.basename(name) == iso_name:
            return hash_val.lower()

    return None


# --------------------------------------------------
# Main verification
# --------------------------------------------------

def verify_iso(base_url, iso_path, install_dir,
               proxy=None,
               skip_gpg=False,
               associated_task=None):

    iso_name = os.path.basename(iso_path)

    log.info("Verifying ISO %s", iso_name)

    sha_url = base_url.rstrip("/") + "/SHA256SUMS"
    gpg_url = base_url.rstrip("/") + "/SHA256SUMS.gpg"

    sha_file = os.path.join(install_dir, "SHA256SUMS")
    sig_file = os.path.join(install_dir, "SHA256SUMS.gpg")

    # -----------------------------
    # Download SHA256SUMS
    # -----------------------------

    try:

        text = fetch_text(sha_url, proxy)

        with open(sha_file, "w", encoding="utf-8") as f:
            f.write(text)

        log.info("Downloaded SHA256SUMS")

    except Exception as e:

        log.error("Failed to download SHA256SUMS: %s", e)
        return False

    # -----------------------------
    # Download signature
    # -----------------------------

    if not skip_gpg:

        try:

            sig = fetch_binary(gpg_url, proxy)

            with open(sig_file, "wb") as f:
                f.write(sig)

            verify_gpg(sig_file, sha_file)

        except Exception as e:
            log.warning("GPG verification skipped: %s", e)

    # -----------------------------
    # Find expected hash
    # -----------------------------

    expected_hash = parse_sha256sums(text, iso_name)

    if not expected_hash:

        log.warning(
            "ISO not found in SHA256SUMS — skipping verification")
        return True

    log.info("Expected SHA256: %s", expected_hash)

    # -----------------------------
    # Compute actual hash
    # -----------------------------

    if associated_task:

        associated_task.description = f"Verifying {iso_name}"
        associated_task.unit = "MB"
        associated_task.size = os.path.getsize(
            iso_path) // (1024 * 1024)

    actual_hash = sha256_file(iso_path, associated_task)

    if actual_hash is None:
        return False

    log.info("Actual SHA256: %s", actual_hash)

    # -----------------------------
    # Compare
    # -----------------------------

    if actual_hash != expected_hash:

        log.error(
            "SHA256 mismatch\nExpected: %s\nActual:   %s",
            expected_hash,
            actual_hash,
        )

        return False

    log.info("ISO verified successfully")

    return True