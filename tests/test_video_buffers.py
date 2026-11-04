"""Compile the video-buffer patch logic against fake Vulkan/gralloc inputs, never a GPU."""

from pathlib import Path
import subprocess
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]


def additions(name):
    return "\n".join(line[1:] for line in (REPO / "hardware/drivers/amdgpu" / name).read_text().splitlines()
                     if line.startswith("+") and not line.startswith("+++")
                     and not line.startswith("+#include"))


class VideoBufferTests(unittest.TestCase):
    def compile_and_run(self, source):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary)
            (path / "test.c").write_text(source)
            subprocess.run(
                ["cc", "-std=c11", "-Wall", "-Wextra", "-Werror",
                 str(path / "test.c"), "-o", str(path / "test")],
                check=True, capture_output=True, text=True,
            )
            subprocess.run([str(path / "test")], check=True, capture_output=True, text=True)

    def test_external_format_query_preserves_errors_and_memory_type_safeguard(self):
        logic = additions("mesa-radv-yv12.patch")
        self.assertIn("vk_common_GetAndroidHardwareBufferPropertiesANDROID", logic)
        self.compile_and_run(r"""
#include <assert.h>
#include <stdint.h>
typedef int VkResult;
enum { VK_SUCCESS = 0, VK_FORMAT_UNDEFINED = 0 };
typedef struct { unsigned format, usage; } AHardwareBuffer_Desc;
typedef struct { unsigned memoryTypeBits; } Properties;
static int common_calls, common_result;
static void AHardwareBuffer_describe(const AHardwareBuffer_Desc *b, AHardwareBuffer_Desc *d)
{ *d = *b; }
static unsigned vk_format_from_android(unsigned format, unsigned usage)
{ (void)usage; return format; }
static VkResult vk_common_GetAndroidHardwareBufferPropertiesANDROID(
    int device, const AHardwareBuffer_Desc *buffer, Properties *properties)
{
    (void)device; (void)buffer;
    ++common_calls;
    properties->memoryTypeBits = 0xff;
    return common_result;
}
static VkResult query(const AHardwareBuffer_Desc *buffer, Properties *pProperties)
{
    int device_h = 1;
    struct { unsigned memory_types_32bit; } physical = { 0x0c }, *pdev = &physical;
""" + logic + r"""
    return 17; /* Existing RADV path for directly supported RGB/NV12. */
}
int main(void)
{
    Properties properties = {0};
    AHardwareBuffer_Desc external = {0, 0}, rgb = {1, 0}, nv12 = {2, 0};
    assert(query(&external, &properties) == VK_SUCCESS);
    assert(properties.memoryTypeBits == 0xf3);
    assert(common_calls == 1);
    assert(query(&rgb, &properties) == 17);
    assert(query(&nv12, &properties) == 17);
    assert(common_calls == 1);
    common_result = -1000072003;
    assert(query(&external, &properties) == common_result);
    assert(common_calls == 2);
}
""")

    def test_yuv_luma_and_chroma_pitch_for_all_widths_through_8k(self):
        logic = additions("minigbm-yuv-pitch.patch")
        self.compile_and_run(r"""
#include <assert.h>
#include <stdint.h>
#define ALIGN(value, alignment) (((value) + (alignment) - 1) & ~((alignment) - 1))
enum { DRM_FORMAT_YVU420 = 1, DRM_FORMAT_YVU420_ANDROID = 2, RGB = 3,
       DRM_FORMAT_NV12 = 4, DRM_FORMAT_NV21 = 5 };
static unsigned width_for_format(unsigned width, unsigned format)
{
    struct { unsigned width; } alloc_args = {width};
""" + logic + r"""
    return alloc_args.width;
}
int main(void)
{
    for (unsigned width = 1; width <= 8192; ++width) {
        for (unsigned format = DRM_FORMAT_YVU420; format <= DRM_FORMAT_YVU420_ANDROID; ++format) {
            unsigned luma = width_for_format(width, format);
            unsigned chroma = luma / 2;
            assert(luma >= width && luma < width + 512);
            assert(luma % 512 == 0);
            assert(chroma % 256 == 0);
            assert(chroma == ALIGN(luma / 2, 16));
        }
        for (unsigned format = DRM_FORMAT_NV12; format <= DRM_FORMAT_NV21; ++format) {
            unsigned pitch = width_for_format(width, format);
            assert(pitch >= width && pitch < width + 256);
            assert(pitch % 256 == 0);
        }
        assert(width_for_format(width, RGB) == width);
    }
    assert(width_for_format(640, DRM_FORMAT_NV12) == 768);
    assert(width_for_format(1280, DRM_FORMAT_NV12) == 1280);
    assert(width_for_format(1280, DRM_FORMAT_YVU420_ANDROID) == 1536);
    assert(width_for_format(1920, DRM_FORMAT_YVU420_ANDROID) == 2048);
}
""")


if __name__ == "__main__":
    unittest.main()
