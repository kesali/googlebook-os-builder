#pragma once
#include <stdio.h>

/* Host-side Android logging for the allocator's injected-failure tests. */
#define ALOGE(...) do { fprintf(stderr, __VA_ARGS__); fputc('\n', stderr); } while (0)
