export SHELL = sh
LDFLAGS = -shared -dll
CC = x86_64-w64-mingw32-gcc
STRIP = x86_64-w64-mingw32-strip

all: cpuid.dll

cpuid.dll: cpuid.c
	$(CC) -o $@ $(LDFLAGS) $^
	$(STRIP) $@
