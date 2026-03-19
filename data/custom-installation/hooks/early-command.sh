#!/bin/sh
set -ex

CUSTOM="${1:-/ubuntu/install/custom-installation}"
PATCH="$CUSTOM/patch"

# loop-remount hook
if [ -f "$PATCH/loop-remount" ]; then
    mkdir -p /target/etc/initramfs-tools/hooks
    cp "$PATCH/loop-remount" /target/etc/initramfs-tools/hooks/loop-remount
    chmod +x /target/etc/initramfs-tools/hooks/loop-remount
fi

# grub lupin patches
if [ -f /host/wubildr ] || [ -f /boot/efi/wubildr ]; then
    for f in grub-install grub-mkimage-lupin; do
        if [ -f "$PATCH/$f" ]; then
            mkdir -p /target/usr/local/sbin
            cp "$PATCH/$f" /target/usr/local/sbin/$f
            chmod +x /target/usr/local/sbin/$f
        fi
    done
    if [ -f "$PATCH/10_lupin" ]; then
        mkdir -p /target/etc/grub.d
        cp "$PATCH/10_lupin" /target/etc/grub.d/10_lupin
        chmod +x /target/etc/grub.d/10_lupin
    fi
fi
