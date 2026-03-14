export SHELL = sh
PACKAGE = wubi
ICON = data/images/Wubi.ico
VERSION = $(shell head -n 1 debian/changelog | sed -e "s/^$(PACKAGE) (\(.*\)).*/\1/g" | cut -d r -f 1)
REVISION = $(shell head -n 1 debian/changelog | sed -e "s/^$(PACKAGE) (\(.*\)).*/\1/g" | cut -d r -f 2)
COPYRIGHTYEAR = 2009
AUTHOR = Agostino Russo
EMAIL = agostino.russo@gmail.com

# Adapted from the original Makefile, for Debian under WSL.
# Adapt the PYTHON_WIN variable to point to your version of Python, be it version whatever.
# as long as it's Python 3 or later, it should be fine.
PYTHON_WIN = /mnt/c/Python313/python.exe 

all: build check

build: wubi

wubi: wubi-pre-build
	/mnt/c/Python313/python.exe -m PyInstaller --noconfirm wubi.spec
	mv dist/$(PACKAGE).exe build/wubi.exe

wubizip: wubi-pre-build
	sh -c 'PYTHONPATH=src tools/pywine pypack --verbose --outputdir=build/wubi src/main.py data build/bin build/version.py build/winboot build/translations'
	cp "$(PYTHON_DLL)" build/wubi
	sh -c 'cd build && zip -r wubi.zip wubi'

wubi-pre-build: check_winboot winboot2 src/main.py src/wubi/*.py version.py translations
	/mnt/c/Python313/python.exe -m pip install -r requirements.txt
	rm -rf build/wubi
	rm -rf build/bin
	cp -a blobs build/bin

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
	for i in po/*.po; do \
		mv $$i $${i}.old; \
		msgmerge $${i}.old po/wubi.pot | msgattrib --no-obsolete > $$i; \
		rm $${i}.old; \
	done

translations: po/*.po
	mkdir -p build/translations/
	@for po in $^; do \
		language=$$(basename $$po); \
		language=$${language%%.po}; \
		target="build/translations/$$language/LC_MESSAGES"; \
		mkdir -p $$target; \
		msgfmt \
			--output="$$target/$(PACKAGE).mo" \
			"$$po"; \
	done

version.py:
	sh -c 'echo "version = \"$(VERSION)\"" > build/version.py'
	sh -c 'echo "revision = $(REVISION)" >> build/version.py'
	sh -c 'echo "application_name = \"$(PACKAGE)\"" >> build/version.py'

winboot2:
	mkdir -p build/winboot build/winboot/EFI build/grubutil
	cp -f data/wubildr.cfg data/wubildr-bootstrap.cfg build/winboot/
	/usr/lib/grub/i386-pc/grub-ntldr-img --grub2 \
		--boot-file=wubildr \
		-o "build/winboot/wubildr.mbr"
	sh -c 'cd build/winboot && tar cf wubildr.tar wubildr.cfg'
	grub-mkimage -O i386-pc \
		-c "build/winboot/wubildr-bootstrap.cfg" \
		-m "build/winboot/wubildr.tar" \
		-o "build/grubutil/core.img" \
		loadenv biosdisk part_msdos part_gpt fat ntfs ext2 ntfscomp \
		iso9660 loopback search linux boot minicmd cat chain \
		halt help ls reboot echo test configfile gzio normal sleep \
		memdisk tar font gfxterm gettext true vbe vga video_bochs video_cirrus probe
	sh -c "cat /usr/lib/grub/i386-pc/lnxboot.img \
		'build/grubutil/core.img' \
		> 'build/winboot/wubildr'"

winboot: grub4dos grubutil
	mkdir -p build/winboot
	cp -f data/menu.winboot build/winboot/menu.lst
	cp -f build/grub4dos/stage2/grldr build/winboot/wubildr
	cp -f build/grub4dos/stage2/grub.exe build/winboot/wubildr.exe
	dd if=build/winboot/wubildr of=build/winboot/wubildr.mbr bs=1 count=8192
	sh -c 'cd build/winboot && ../grubutil/grubinst/grubinst -o -b=wubildr wubildr.mbr'

grub4dos: src/grub4dos/*
	cp -rf src/grub4dos build
	sh -c 'cd build/grub4dos && ./configure --enable-preset-menu=../../data/menu.winboot'
	sh -c 'cd build/grub4dos && make'

grubutil: src/grubutil/grubinst/*
	cp -rf src/grubutil build
	sh -c 'cd build/grubutil/grubinst && make'

runbin: wubi
	rm -rf build/test
	mkdir build/test
	sh -c 'cd build/test && ../wubi --test'

check_winboot: tools/check_winboot

unittest:
	tools/test

check: wubi
	PYTHONPATH=src $(PYTHON_WIN) tests/run

runpy:
	sh -c 'PYTHONPATH=src src/main.py --test'

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

.PHONY: all build check wubi wubizip wubi-pre-build pot runpy runbin check_winboot unittest clean distclean translations version.py winboot winboot2 grubutil grub4dos
