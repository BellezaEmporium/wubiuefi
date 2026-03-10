/*
 * cpuid.c - test for long mode using cpuid instruction
 * Rewritten to use <cpuid.h> intrinsic for 64-bit compatibility
 */

#include <windows.h>
#include <intrin.h>

#define bit_LM (1 << 29)

__declspec(dllexport) int
check_64bit(void)
{
    unsigned int eax, ebx, ecx, edx;
    unsigned int ext_level;

    /* Check extended CPUID availability */
    int regs[4];
    __cpuid(regs, 0);
    eax = regs[0];
    if (eax == 0)
        return 0;

    __cpuid(regs, 0x80000000);
    ext_level = regs[0];
    if (ext_level < 0x80000001)
        return 0;

    __cpuid(regs, 0x80000001);
    edx = regs[3];
    return !!(edx & bit_LM);
}