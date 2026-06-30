#define _GNU_SOURCE
#include <dlfcn.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <fcntl.h>
#include <unistd.h>
#include <EGL/egl.h>
#include <EGL/eglext.h>
#include <gbm.h>

static struct gbm_device *gbm_dev = NULL;
static int shim_ready = 0;

typedef EGLDisplay (*real_eglGetDisplay_t)(EGLNativeDisplayType);
typedef EGLDisplay (*real_eglGetPlatformDisplay_t)(EGLenum, void *, const EGLAttrib *);

__attribute__((constructor))
void init_shim(void) {
    if (shim_ready) return;

    setenv("__EGL_VENDOR_LIBRARY_FILENAMES", "/usr/share/glvnd/egl_vendor.d/50_mesa.json", 1);
    setenv("MESA_LOADER_DRIVER_OVERRIDE", "swrast", 1);
    setenv("EGL_PLATFORM", "gbm", 1);

    void *libgbm = dlopen("libgbm.so.1", RTLD_LAZY | RTLD_LOCAL);
    if (!libgbm) {
        fprintf(stderr, "egl_shim: cannot open libgbm.so.1: %s\n", dlerror());
        shim_ready = -1;
        return;
    }

    struct gbm_device* (*create_device)(int) = dlsym(libgbm, "gbm_create_device");
    if (!create_device) {
        fprintf(stderr, "egl_shim: no gbm_create_device\n");
        shim_ready = -1;
        return;
    }

    int fd = open("/dev/null", O_RDWR);
    if (fd < 0) {
        fprintf(stderr, "egl_shim: cannot open /dev/null\n");
        shim_ready = -1;
        return;
    }

    gbm_dev = create_device(fd);
    if (!gbm_dev) {
        fprintf(stderr, "egl_shim: gbm_create_device failed\n");
        close(fd);
        shim_ready = -1;
        return;
    }

    shim_ready = 1;
    fprintf(stderr, "egl_shim: GBM device ready from /dev/null (backend: %s)\n",
            gbm_device_get_backend_name(gbm_dev));
}

EGLDisplay eglGetDisplay(EGLNativeDisplayType display_id) {
    if (!shim_ready) {
        if (shim_ready == 0) init_shim();
        if (shim_ready < 0) {
            real_eglGetDisplay_t real = (real_eglGetDisplay_t)dlsym(RTLD_NEXT, "eglGetDisplay");
            if (real) return real(display_id);
            return EGL_NO_DISPLAY;
        }
    }

    fprintf(stderr, "egl_shim: eglGetDisplay(%p) -> redirecting to GBM platform\n",
            (void*)display_id);

    // Redirect to eglGetPlatformDisplay with our GBM device
    real_eglGetPlatformDisplay_t real_pf = (real_eglGetPlatformDisplay_t)dlsym(RTLD_DEFAULT, "eglGetPlatformDisplay");
    if (!real_pf) {
        // Try EXT variant
        typedef EGLDisplay (*eglGetPlatformDisplayEXT_t)(EGLenum, void *, const EGLint *);
        void *proc = dlsym(RTLD_DEFAULT, "eglGetPlatformDisplayEXT");
        if (!proc)
            proc = ((void* (*)(const char*))dlsym(RTLD_DEFAULT, "eglGetProcAddress"))("eglGetPlatformDisplayEXT");
        if (!proc) {
            fprintf(stderr, "egl_shim: no eglGetPlatformDisplay available\n");
            real_eglGetDisplay_t real = (real_eglGetDisplay_t)dlsym(RTLD_NEXT, "eglGetDisplay");
            if (real) return real(display_id);
            return EGL_NO_DISPLAY;
        }
        EGLint attribs[] = {EGL_NONE};
        EGLDisplay d = ((eglGetPlatformDisplayEXT_t)proc)(EGL_PLATFORM_GBM_KHR, (void*)gbm_dev, attribs);
        fprintf(stderr, "egl_shim: GBM-EGL display via EXT = %p\n", (void*)d);
        return d;
    }

    EGLAttrib attribs[] = {EGL_NONE};
    EGLDisplay d = real_pf(EGL_PLATFORM_GBM_KHR, (void*)gbm_dev, attribs);
    fprintf(stderr, "egl_shim: GBM-EGL display = %p\n", (void*)d);
    return d;
}
