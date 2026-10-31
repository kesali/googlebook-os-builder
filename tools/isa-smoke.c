/* Test the VEX encodings supported by the imported emulator, not legacy SSE GFNI. */
#include <immintrin.h>
#include <stdio.h>

__attribute__((target("avx,gfni"), noinline))
static int gfni(void)
{
    volatile unsigned char a = 0x57, b = 0x83;
    __m128i value = _mm_gf2p8mul_epi8(_mm_set1_epi8(a), _mm_set1_epi8(b));
    unsigned char result[16];
    _mm_storeu_si128((__m128i *)result, value);
    for (int i = 0; i < 16; ++i)
        if (result[i] != 0xc1)
            return 1;
    return 0;
}

__attribute__((target("avxvnni"), noinline))
static int vnni(void)
{
    volatile int a = 3, b = 2;
    __m256i value = _mm256_dpbusd_epi32(
        _mm256_set1_epi32(1), _mm256_set1_epi8(a), _mm256_set1_epi8(b));
    int result[8];
    _mm256_storeu_si256((__m256i *)result, value);
    for (int i = 0; i < 8; ++i)
        if (result[i] != 25)
            return 1;
    return 0;
}

int main(void)
{
    if (gfni() || vnni()) {
        fputs("ISA_SMOKE_FAILED\n", stderr);
        return 1;
    }
    puts("ISA_SMOKE_OK: VEX GFNI and AVX-VNNI");
    return 0;
}
