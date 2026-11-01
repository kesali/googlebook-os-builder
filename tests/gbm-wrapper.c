/* Exercise the patched upstream wrapper with fake Mesa operations, never a GPU. */
#include <assert.h>
#include <fcntl.h>
#include <stdio.h>
#include <unistd.h>

#include "gbm_mesa_driver/gbm_mesa_wrapper.c"

struct gbm_bo { int unused; };
static struct gbm_bo buffer;
static uint32_t last_usage;
static int exported_fd, destroyed;
static bool fail_create, fail_export, fail_import, fail_map;
static void *map_result;

static struct gbm_bo *create(struct gbm_device *dev, uint32_t w, uint32_t h,
                            uint32_t format, uint32_t usage)
{
    last_usage = usage;
    return fail_create ? NULL : &buffer;
}

static int export_fd(struct gbm_bo *bo)
{
    if (fail_export)
        return -1;
    int descriptors[2];
    assert(pipe(descriptors) == 0);
    close(descriptors[1]);
    exported_fd = descriptors[0];
    return exported_fd;
}

static uint32_t stride(struct gbm_bo *bo) { return 256; }
static uint64_t modifier(struct gbm_bo *bo) { return DRM_FORMAT_MOD_LINEAR; }
static void destroy(struct gbm_bo *bo) { destroyed++; }

static struct gbm_bo *import(struct gbm_device *dev, uint32_t type, void *data, uint32_t flags)
{
    return fail_import ? NULL : &buffer;
}

static void *map(struct gbm_bo *bo, uint32_t x, uint32_t y, uint32_t w, uint32_t h,
                 uint32_t flags, uint32_t *out_stride, void **data)
{
    *out_stride = 256;
    *data = &buffer;
    return fail_map ? map_result : &buffer;
}

static void unmap(struct gbm_bo *bo, void *data) {}

static void reset(void)
{
    fail_create = fail_export = fail_import = fail_map = false;
    destroyed = 0;
    exported_fd = -1;
    map_result = MAP_FAILED;
    gbm_priv_ops.gbm_bo_create = create;
    gbm_priv_ops.gbm_bo_get_fd = export_fd;
    gbm_priv_ops.gbm_bo_get_stride = stride;
    gbm_priv_ops.gbm_bo_get_modifier = modifier;
    gbm_priv_ops.gbm_bo_destroy = destroy;
    gbm_priv_ops.gbm_bo_import = import;
    gbm_priv_ops.gbm_bo_map = map;
    gbm_priv_ops.gbm_bo_unmap = unmap;
}

static void assert_fd_closed(void)
{
    errno = 0;
    assert(fcntl(exported_fd, F_GETFD) == -1 && errno == EBADF);
}

int main(void)
{
    struct alloc_args args = {
        .width = 64, .height = 64, .drm_format = DRM_FORMAT_ARGB8888,
        .use_cursor = true, .force_linear = true,
    };
    reset();
    assert(gbm_mesa_alloc(&args) == 0);
    assert(last_usage == (GBM_BO_USE_CURSOR | GBM_BO_USE_LINEAR));
    assert(args.out_stride == 256 && args.out_modifier == DRM_FORMAT_MOD_LINEAR);
    assert(destroyed == 1);
    close(args.out_fd);

    reset();
    args.use_cursor = args.force_linear = false;
    args.use_scanout = true;
    assert(gbm_mesa_alloc(&args) == 0 && last_usage == GBM_BO_USE_SCANOUT);
    close(args.out_fd);

    reset();
    fail_create = true;
    assert(gbm_mesa_alloc(&args) == -EINVAL && destroyed == 0);
    reset();
    fail_export = true;
    assert(gbm_mesa_alloc(&args) == -EINVAL && destroyed == 1);

    reset();
    args.needs_map_stride = true;
    assert(gbm_mesa_alloc(&args) == 0 && args.out_map_stride == 256);
    assert(destroyed == 2);
    close(args.out_fd);

    reset();
    fail_import = true;
    assert(gbm_mesa_alloc(&args) == -EINVAL && destroyed == 1);
    assert_fd_closed();
    for (int null_map = 0; null_map < 2; null_map++) {
        reset();
        fail_map = true;
        map_result = null_map ? NULL : MAP_FAILED;
        assert(gbm_mesa_alloc(&args) == -EINVAL && destroyed == 2);
        assert_fd_closed();
        void *addr = &buffer, *data = NULL;
        gbm_map(&buffer, 64, 64, &addr, &data);
        assert(addr == MAP_FAILED);
    }
    puts("Mesa GBM wrapper tests passed (usage flags, FD ownership, import/map failures).");
    return 0;
}
