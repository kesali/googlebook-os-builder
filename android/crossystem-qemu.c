/* QEMU has no ChromeOS firmware state. GPT slot state is handled by the boot HAL. */
#include <stdio.h>
#include <string.h>

int main(int argc, char **argv)
{
    if (argc < 2) {
        fputs("crossystem-qemu: only boot-success assignments are supported\n", stderr);
        return 1;
    }
    for (int i = 1; i < argc; ++i) {
        if (strcmp(argv[i], "fw_result=success") && strcmp(argv[i], "fw_try_count=0")) {
            fprintf(stderr, "crossystem-qemu: unsupported firmware operation: %s\n", argv[i]);
            return 1;
        }
    }
    return 0;
}
