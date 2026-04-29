export SHELL = sh
PACKAGE = wubi
ICON = data/images/Wubi.ico
VERSION = $(shell head -n 1 debian/changelog | sed -e "s/^$(PACKAGE) (\(.*\)).*/\1/g" | cut -d r -f 1)
REVISION = $(shell head -n 1 debian/changelog | sed -e "s/^$(PACKAGE) (\(.*\)).*/\1/g" | cut -d r -f 2)
COPYRIGHTYEAR = 2009
AUTHOR = Agostino Russo
EMAIL = agostino.russo@gmail.com

PYTHON_WIN = /mnt/c/Python313/python.exe

GRUB_MODULES = \
    part_gpt part_msdos \
    fat ntfs ext2 \
    search search_fs_file search_fs_uuid search_label \
    loopback normal configfile \
    linux initrd \
    echo test probe ls cat \
    memdisk tar \
    all_video gfxterm gfxterm_background font \
    jpeg png tga \
    reboot halt

all: build check

build: wubi

wubi: wubi-pre-build
	$(PYTHON_WIN) tools/nuitka_build.py

wubi-pre-build: check_winboot winboot translations
	$(PYTHON_WIN) -m pip install -r requirements.txt
	rm -rf build/wubi build/bin
	cp -a blobs build/bin
	$(MAKE) version.py

winboot: check_winboot
	@echo "Verifying EFI binaries..."
	@for f in shimx64.efi grubx64.efi; do \
	    if [ ! -f "build/winboot/EFI/$$f" ]; then \
	        echo "ERROR: build/winboot/EFI/$$f is missing after check_winboot"; \
	        exit 1; \
	    fi; \
	done

	# Copy wubildr.cfg template so modify_EFI_folder can find it at data_dir
	@if [ -f data/wubildr.cfg ]; then \
	    cp -f data/wubildr.cfg build/winboot/wubildr.cfg; \
	    echo "Copied wubildr.cfg -> build/winboot/wubildr.cfg"; \
	else \
	    echo "WARNING: data/wubildr.cfg not found — boot config will be missing"; \
	fi

	@echo "winboot ready:"
	@ls -lh build/winboot/EFI/

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
	sh -c 'echo "version = \"$(VERSION)\"" > src/version.py'
	sh -c 'echo "revision = $(REVISION)" >> src/version.py'
	sh -c 'echo "application_name = \"$(PACKAGE)\"" >> src/version.py'

runbin: wubi
	rm -rf build/test
	mkdir build/test
	sh -c 'cd build/test && ../wubi --test'

check_winboot:
	tools/check_winboot

unittest:
	tools/test

check: wubi
	PYTHONPATH=src $(PYTHON_WIN) tests/run

runpy:
	sh -c 'PYTHONPATH=src src/main.py --test'

clean:
	rm -rf dist/* build/*
	rm -f src/version.py

distclean: clean
	rm -rf wine
	rm -rf tools/buildtest/*
	find . -type f -name "*.pyo" -delete
	find . -type f -name "*.pyc" -delete
	rm -rf .key
	rm -rf data/custom-installation/packages
	rm -rf shim

.PHONY: all build check wubi wubizip wubi-pre-build pot runpy runbin \
        check_winboot unittest clean distclean translations version.py \
        winboot grub4dos update-po