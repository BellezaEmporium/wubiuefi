export SHELL = sh
PACKAGE = wubi
ICON = data/images/Wubi.ico
VERSION = $(shell head -n 1 debian/changelog | sed -e "s/^$(PACKAGE) (\(.*\)).*/\1/g" | cut -d r -f 1)
REVISION = $(shell head -n 1 debian/changelog | sed -e "s/^$(PACKAGE) (\(.*\)).*/\1/g" | cut -d r -f 2)
COPYRIGHTYEAR = 2009
AUTHOR = Agostino Russo
EMAIL = agostino.russo@gmail.com

WSL = wsl -u root --
WSLPATH = $(shell wsl -u root -- wslpath -u "$$(cmd.exe /c 'cd' 2>/dev/null | tr -d '\r')" 2>/dev/null || echo "/mnt/d/GH Repos/wubiuefi")
PYTHON_DLL = /cygdrive/c/Python313/python313.dll

all: build check

build: wubi

wubi: wubi-pre-build
	PYTHONPATH=src tools/pywine -OO pypack --verbose --bytecompile --outputdir=build/wubi src/main.py data build/bin build/version.py build/winboot build/translations
	PYTHONPATH=src tools/pywine -OO build/pylauncher/pack.py build/wubi
	mv build/application.exe build/wubi.exe

wubizip: wubi-pre-build
	PYTHONPATH=src tools/pywine pypack --verbose --outputdir=build/wubi src/main.py data build/bin build/version.py build/winboot build/translations
	cp "$(PYTHON_DLL)" build/wubi
	cd build; zip -r wubi.zip wubi

wubi-pre-build: check_winboot pylauncher winboot2 src/main.py src/wubi/*.py cpuid version.py translations
	rm -rf build/wubi
	rm -rf build/bin
	cp -a blobs build/bin
	cp "$(PYTHON_DLL)" build/pylauncher
	cp build/cpuid/cpuid.dll build/bin

pot:
	xgettext --default-domain="$(PACKAGE)" --output="po/$(PACKAGE).pot" $(shell find src/wubi -name "*.py" | sort)
	sed -i 's/SOME DESCRIPTIVE TITLE/Translation template for $(PACKAGE)/' po/$(PACKAGE).pot
	sed -i "s/YEAR THE PACKAGE'S COPYRIGHT HOLDER/$(COPYRIGHTYEAR)/" po/$(PACKAGE).pot
	sed -i 's/FIRST AUTHOR <EMAIL@ADDRESS>, YEAR/$(AUTHOR) <$(EMAIL)>, $(COPYRIGHTYEAR)/' po/$(PACKAGE).pot
	sed -i 's/Report-Msgid-Bugs-To: /Report-Msgid-Bugs-To: $(EMAIL)/' po/$(PACKAGE).pot
	sed -i 's/CHARSET/UTF-8/' po/$(PACKAGE).pot
	sed -i 's/PACKAGE VERSION/$(VERSION)-r$(REVISION)/' po/$(PACKAGE).pot
	sed -i 's/PACKAGE/$(PACKAGE)/' po/$(PACKAGE).pot

update-po: pot
	for i in po/*.po ;\
	do \
	mv $$i $${i}.old ; \
	(msgmerge $${i}.old po/wubi.pot | msgattrib --no-obsolete > $$i) ; \
	rm $${i}.old ; \
	done

translations: po/*.po
	mkdir -p build/translations/
	@for po in $^; do \
		language=$$(basename $$po); \
		language=$${language%%.po}; \
		target="build/translations/$$language/LC_MESSAGES"; \
		mkdir -p $$target; \
		wsl -u root -- msgfmt \
			--output="$(WSLPATH)/$$target/$(PACKAGE).mo" \
			"$(WSLPATH)/$$po"; \
	done

version.py:
	$(shell echo 'version = "$(VERSION)"' > build/version.py)
	$(shell echo 'revision = $(REVISION)' >> build/version.py)
	$(shell echo 'application_name = "$(PACKAGE)"' >> build/version.py)

pylauncher: 7z src/pylauncher/*
	cp -rf src/pylauncher build
	cp "$(ICON)" build/pylauncher/application.ico
	sed -i 's/application_name/$(PACKAGE)/' build/pylauncher/pylauncher.exe.manifest
	cd build/pylauncher; make

cpuid: src/cpuid/cpuid.c
	cp -rf src/cpuid build
	cd build/cpuid; make

winboot2:
	mkdir -p build/winboot build/winboot/EFI build/grubutil
	cp -f data/wubildr.cfg data/wubildr-bootstrap.cfg build/winboot/
	$(WSL) /usr/lib/grub/i386-pc/grub-ntldr-img --grub2 \
		--boot-file=wubildr \
		-o "$(WSLPATH)/build/winboot/wubildr.mbr"
	cd build/winboot && tar cf wubildr.tar wubildr.cfg
	$(WSL) grub-mkimage -O i386-pc \
		-c "$(WSLPATH)/build/winboot/wubildr-bootstrap.cfg" \
		-m "$(WSLPATH)/build/winboot/wubildr.tar" \
		-o "$(WSLPATH)/build/grubutil/core.img" \
		loadenv biosdisk part_msdos part_gpt fat ntfs ext2 ntfscomp \
		iso9660 loopback search linux boot minicmd cat cpuid chain \
		halt help ls reboot echo test configfile gzio normal sleep \
		memdisk tar font gfxterm gettext true vbe vga video_bochs video_cirrus probe
	wsl -u root -- sh -c "cat /usr/lib/grub/i386-pc/lnxboot.img \
		'/mnt/d/GH Repos/wubiuefi/build/grubutil/core.img' \
		> '/mnt/d/GH Repos/wubiuefi/build/winboot/wubildr'"

winboot: grub4dos grubutil
	mkdir -p build/winboot
	cp -f data/menu.winboot build/winboot/menu.lst
	cp -f build/grub4dos/stage2/grldr build/winboot/wubildr
	cp -f build/grub4dos/stage2/grub.exe build/winboot/wubildr.exe
	dd if=build/winboot/wubildr of=build/winboot/wubildr.mbr bs=1 count=8192
	cd build/winboot; ../grubutil/grubinst/grubinst -o -b=wubildr wubildr.mbr

grub4dos: src/grub4dos/*
	cp -rf src/grub4dos build
	cd build/grub4dos;./configure --enable-preset-menu=../../data/menu.winboot
	cd build/grub4dos; make

grubutil: src/grubutil/grubinst/*
	cp -rf src/grubutil build
	cd build/grubutil/grubinst; make

# not compiling 7z at the moment, but source is used by pylauncher
7z: src/7z/C/*.c
	mkdir -p build/7z
	cp -rf src/7z build

runbin: wubi
	rm -rf build/test
	mkdir build/test
	cd build/test; ../../tools/wine ../wubi.exe --test

check_winboot: tools/check_winboot
	tools/check_winboot

unittest:
	tools/pywine tools/test

check: wubi
	tests/run

runpy:
	PYTHONPATH=src tools/pywine src/main.py --test

clean:
	rm -rf dist/*
	rm -rf build/*

distclean: clean
	rm -rf wine
	rm -rf tools/buildtest/*
	find . -type f -name "*.pyo" -delete
	find . -type f -name "*.pyc" -delete
	rm -rf .key
	rm -rf data/custom-installation/packages
	rm -rf shim

.PHONY: all build test wubi wubizip wubi-pre-build pot runpy runbin check_winboot unittest
	7z translations version.py pylauncher winboot winboot2 grubutil grub4dos clean distclean
