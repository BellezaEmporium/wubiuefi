#!/bin/sh
set -x

CUSTOM=/custom-installation
PATCH=$CUSTOM/patch

# load loop module for later use (boot loop)
modprobe loop 2>/dev/null || true

# --- lupin patches (for subiquity & calamares) ---

# loop-remount : patch initramfs for loop-remount (boot loop)
if [ -f "$PATCH/loop-remount" ]; then
    mkdir -p /target/etc/initramfs-tools/hooks
    cp "$PATCH/loop-remount" /target/etc/initramfs-tools/hooks/loop-remount
    chmod +x /target/etc/initramfs-tools/hooks/loop-remount
fi

# grub lupin : replace grub-install and grub-mkimage with patched versions, and add a custom grub.d script
if [ -f /host/wubildr ]; then
    if [ -f "$PATCH/grub-install" ]; then
        mkdir -p /target/usr/local/sbin
        cp "$PATCH/grub-install" /target/usr/local/sbin/grub-install
        chmod +x /target/usr/local/sbin/grub-install
    fi
    if [ -f "$PATCH/grub-mkimage-lupin" ]; then
        mkdir -p /target/usr/local/sbin
        cp "$PATCH/grub-mkimage-lupin" /target/usr/local/sbin/grub-mkimage-lupin
        chmod +x /target/usr/local/sbin/grub-mkimage-lupin
    fi
    if [ -f "$PATCH/10_lupin" ]; then
        mkdir -p /target/etc/grub.d
        cp "$PATCH/10_lupin" /target/etc/grub.d/10_lupin
        chmod +x /target/etc/grub.d/10_lupin
    fi
fi
