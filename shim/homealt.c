/*
 * homealt.c — LD_PRELOAD-шим для второго Steam-клиента.
 *
 * Что делает:
 *   1) подменяет домашний каталог пользователя (getpwuid/getpwuid_r) на ALT_HOME —
 *      чтобы Steam-библиотека внутри игры искала steam.pipe в нужном HOME;
 *   2) скрывает общий rendezvous-объект Steam в /dev/shm
 *      (u<uid>-ValveIPCSharedObj-Steam, ValveIPCSHM_*), чтобы игра не прицепилась
 *      к чужому клиенту.
 *
 * Основное решение проблемы всё же не в шиме, а в отдельном IPC-порте
 * (-master_ipc_name_override + steam_master_ipc_name_override) — см. README.
 * Шим оставлен как дополнительная страховка; проверялся в связке с портом.
 *
 * Сборка:
 *   gcc -shared -fPIC -O2 -DALT_HOME='"/home/user/steam-alt"' -o libhomealt.so homealt.c -ldl
 *
 * Использование (в Launch Options игры):
 *   LD_PRELOAD=/path/libhomealt.so STEAM_COMPAT_DATA_PATH=/path/compatdata/505460-alt %command%
 */
#define _GNU_SOURCE
#include <dlfcn.h>
#include <stdarg.h>
#include <string.h>
#include <errno.h>
#include <stdio.h>
#include <pwd.h>
#include <unistd.h>
#include <sys/stat.h>
#include <fcntl.h>

#ifndef ALT_HOME
#define ALT_HOME "/home/user/steam-alt"
#endif

static int blocked(const char *p) {
    if (!p) return 0;
    if (strstr(p, "ValveIPCSharedObj-Steam")) return 1;
    if (strstr(p, "ValveIPCSHM_")) return 1;
    return 0;
}

struct passwd *getpwuid(uid_t uid) {
    static struct passwd *(*real)(uid_t);
    if (!real) real = dlsym(RTLD_NEXT, "getpwuid");
    struct passwd *pw = real(uid);
    static struct passwd copy;
    static char dir[256];
    if (pw && uid == getuid()) {
        copy = *pw;
        snprintf(dir, sizeof dir, "%s", ALT_HOME);
        copy.pw_dir = dir;
        return &copy;
    }
    return pw;
}

int getpwuid_r(uid_t uid, struct passwd *pwd, char *buf, size_t len, struct passwd **res) {
    static int (*real)(uid_t, struct passwd*, char*, size_t, struct passwd**);
    if (!real) real = dlsym(RTLD_NEXT, "getpwuid_r");
    int rc = real(uid, pwd, buf, len, res);
    if (rc == 0 && res && *res && uid == getuid()) {
        size_t need = strlen(ALT_HOME) + 1;
        if (need <= len) {
            memcpy(buf, ALT_HOME, need);
            (*res)->pw_dir = buf;
        }
    }
    return rc;
}

int open(const char *path, int flags, ...) {
    static int (*real)(const char*, int, ...);
    if (!real) real = dlsym(RTLD_NEXT, "open");
    if (blocked(path)) { errno = ENOENT; return -1; }
    va_list ap; va_start(ap, flags); mode_t m = va_arg(ap, mode_t); va_end(ap);
    return real(path, flags, m);
}

int open64(const char *path, int flags, ...) {
    static int (*real)(const char*, int, ...);
    if (!real) real = dlsym(RTLD_NEXT, "open64");
    if (blocked(path)) { errno = ENOENT; return -1; }
    va_list ap; va_start(ap, flags); mode_t m = va_arg(ap, mode_t); va_end(ap);
    return real(path, flags, m);
}

int openat(int dirfd, const char *path, int flags, ...) {
    static int (*real)(int, const char*, int, ...);
    if (!real) real = dlsym(RTLD_NEXT, "openat");
    if (blocked(path)) { errno = ENOENT; return -1; }
    va_list ap; va_start(ap, flags); mode_t m = va_arg(ap, mode_t); va_end(ap);
    return real(dirfd, path, flags, m);
}

int openat64(int dirfd, const char *path, int flags, ...) {
    static int (*real)(int, const char*, int, ...);
    if (!real) real = dlsym(RTLD_NEXT, "openat64");
    if (blocked(path)) { errno = ENOENT; return -1; }
    va_list ap; va_start(ap, flags); mode_t m = va_arg(ap, mode_t); va_end(ap);
    return real(dirfd, path, flags, m);
}

int access(const char *path, int mode) {
    static int (*real)(const char*, int);
    if (!real) real = dlsym(RTLD_NEXT, "access");
    if (blocked(path)) { errno = ENOENT; return -1; }
    return real(path, mode);
}

int stat(const char *path, struct stat *st) {
    static int (*real)(const char*, struct stat*);
    if (!real) real = dlsym(RTLD_NEXT, "stat");
    if (blocked(path)) { errno = ENOENT; return -1; }
    return real(path, st);
}

int lstat(const char *path, struct stat *st) {
    static int (*real)(const char*, struct stat*);
    if (!real) real = dlsym(RTLD_NEXT, "lstat");
    if (blocked(path)) { errno = ENOENT; return -1; }
    return real(path, st);
}
