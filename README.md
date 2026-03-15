# WubiUEFI

## Introduction

Wubi is the Windows Ubuntu Installer. Wubi installs Ubuntu inside a file within a windows partition, and thus it does not require CD burning or dedicated partitions, yet the installation is a dual boot setup identical to a normal installation.

For more information see: <https://github.com/hakuna-m/wubiuefi/wiki>

## Disclaimer

This is a base rework of what Hakuna Matata and the Canonical team has done. This is a major rework of WubiUEFI, bumping the main requirements to Python 3.10+, ditching most of the external requirements for PyPi-available libraries and using the power of WSL instead of Wine.
This was forked and reworked solely for my own sake of trying to install an Ubuntu distro "properly" on another computer I possess.
It might have some quacks and flaws (might not look good as well).

I STRONGLY advise disabling Secure Boot BEFORE launching yourself into this for now, as I haven't done the necessary for signing stuff (yet). (Might also get over App Control block for Win10+).

## Compiling

| Make Command         | Description                                                                                                                                                               |
|----------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `make`               | Builds wubi.exe, note that the first time you run it, this is performed automatically, just confirm all the default choices in the installation screens that will appear. |
| `make runbin`        | Builds wubi and runs the packaged binary under wine                                                                                                                       |
| `make wubizip`       | Creates a debug version of Wubi, with Python and the necessary requirements. Unzip the archive, then run `python.exe main.py --verbose`                                   |
| `make pot`           | Generates a gettext template (`/po/wubi.pot`)                                                                                                                             |
| `make check_winboot` | Creates the environment for building and signing boot loaders if it doesn't exist.                                                                                        |
| `make winboot`       | Creates the bootloader files (old version)                                                                                                                                |
| `make winboot2`      | Creates the bootloader files (new version)                                                                                                                                |
| `make clean`         | Removes built files                                                                                                                                                       |
| `make distclean`     | Removes built files and environment                                                                                                                                       |

## Code overview

* `/src/winui` : Thin ctypes wrapper around win32 native graphical user interface
* `/src/wubi` : The main Wubi application, the code is split between backend and frontend, where each runs in its own thread. The two interact via a tasklist object, where the frontend usually runs a tasklist which is a set of backend tasks. Backend is platform-specific, and the frontend is built with tkinter, which means it should load without overhead on all OSs.
* `/data` : Settings for Wubi branding and customization
* `/po` : Translations
* `/bin` : Other binary files required at runtime (will be compiled at a later stage)

## Wubi tasks

Wubi performs the following tasks:

* Fetches information about the running system which will be used during installation
* Checks that the minimum installation requirements are met
* Retrieves required user information via a GUI
* Looks for available local CDs and ISO files
* Downloads the ISO if one is required, using Bittorrent and an HTTP download manager
* Checks the ISO/CD MD5 sums and the MD5 signature
* Extracts the kernel and initrd from the ISO
* Adds a new boot entry to the existing windows bootloader
* Prepares a preseed file to be used during the Linux-side installation
* Allocates space for the virtual disk files

*The actual installation is performed within Linux after rebooting the machine.*

## Customization

* Edit the files in data as appropriate and build your image
* You will need to provide an ISO that is similar to the Ubuntu ISO and in particular it must have .disk/info formatted like .disk/info in the Ubuntu ISO
* You must provide a webserver with metalink file, metalink file MD5 checksums and signatures for the MD5 sums
* Add your signing key to `data/trustedkeys.gpg`
* Replace the generated dummy keys in `.key` with your signing keys for Secure Boot
* On the Linux side, the distribution must be capable of booting and rebooting off a loop file, perform an automatic installation and accept the special boot parameters that indicate the local preseed file and ISO image to boot from.

## License

GPL v2. See [LICENSE](./LICENSE)
