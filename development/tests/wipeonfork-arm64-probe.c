/* SPDX-License-Identifier: GPL-2.0-only */
/* Freestanding ARM64 kernel ABI test: only RAM, fork, memfd and stdout.
 * No libc PRNG dependency; no block devices, mount, reboot or data writes.
 */
typedef unsigned long usize;
static long call6(long number, long a, long b, long c, long d, long e, long f)
{
    register long x0 __asm__("x0") = a;
    register long x1 __asm__("x1") = b;
    register long x2 __asm__("x2") = c;
    register long x3 __asm__("x3") = d;
    register long x4 __asm__("x4") = e;
    register long x5 __asm__("x5") = f;
    register long x8 __asm__("x8") = number;
    __asm__ volatile("svc 0" : "+r"(x0) : "r"(x1), "r"(x2), "r"(x3),
                     "r"(x4), "r"(x5), "r"(x8) : "memory", "cc");
    return x0;
}
static __attribute__((noreturn)) void done(int code)
{
    call6(94, code, 0, 0, 0, 0, 0); /* exit_group */
    __builtin_unreachable();
}
#define CHECK(test, code) do { if (!(test)) done(code); } while (0)
#define ADVISE(p, len, op) call6(233, (long)(p), len, op, 0, 0, 0)
#define FORK() call6(220, 17, 0, 0, 0, 0, 0) /* clone(SIGCHLD), no shared VM */
static void wait_ok(long pid, int code)
{
    int status = 0;
    CHECK(call6(260, pid, (long)&status, 0, 0, 0, 0) == pid, code);
    CHECK(status == 0, code + 1);
}
static void all(volatile unsigned char *p, usize n, unsigned char byte, int code)
{
    for (usize i = 0; i < n; ++i) CHECK(p[i] == byte, code);
}
static volatile unsigned char *map(long flags, long fd, usize length)
{
    long address = call6(222, 0, length, 3, flags, fd, 0); /* mmap RW */
    CHECK((usize)address < (usize)-4095, 10);
    return (volatile unsigned char *)address;
}
__attribute__((noreturn)) void _start(void)
{
    const usize page = 4096; /* A30's recorded ARM64_4K_PAGES configuration */
    volatile unsigned char *p = map(0x22, -1, page * 3); /* private anonymous */
    for (usize i = 0; i < page * 3; ++i) p[i] = (unsigned char)(0x41 + i / page);
    long result = ADVISE(p + page, page, 18);
    if (result == -22 || result == -38) {
        const char msg[] = "UNSUPPORTED: MADV_WIPEONFORK\n";
        call6(64, 1, (long)msg, sizeof(msg)-1, 0, 0, 0);
        done(77);
    }
    CHECK(result == 0, 11);
    long child = FORK();
    CHECK(child >= 0, 12);
    if (!child) {
        all(p, page, 'A', 13);
        all(p + page, page, 0, 14);
        all(p + page * 2, page, 'C', 15);
        for (usize i = page; i < page * 2; ++i) p[i] = 'D';
        long grandchild = FORK();
        CHECK(grandchild >= 0, 16);
        if (!grandchild) {
            all(p + page, page, 0, 17); /* flag remains in subsequent forks */
            done(0);
        }
        wait_ok(grandchild, 18);
        CHECK(ADVISE(p + page, page, 19) == 0, 20);
        grandchild = FORK();
        CHECK(grandchild >= 0, 21);
        if (!grandchild) {
            all(p + page, page, 'D', 22); /* KEEPONFORK cancels wiping */
            done(0);
        }
        wait_ok(grandchild, 23);
        done(0);
    }
    wait_ok(child, 25);
    all(p, page, 'A', 27);
    all(p + page, page, 'B', 28); /* parent was never wiped */
    all(p + page * 2, page, 'C', 29);
    volatile unsigned char *shared = map(0x21, -1, page);
    CHECK(ADVISE(shared, page, 18) == -22, 30);
    const char label[] = "wipeonfork-test";
    long fd = call6(279, (long)label, 1, 0, 0, 0, 0); /* memfd_create */
    CHECK(fd >= 0, 31);
    CHECK(call6(46, fd, page, 0, 0, 0, 0) == 0, 32); /* ftruncate RAM file */
    volatile unsigned char *file_map = map(2, fd, page);
    CHECK(ADVISE(file_map, page, 18) == -22, 33);
    CHECK(ADVISE(p + page + 1, page, 18) == -22, 34);
    const char msg[] = "PASS: private anonymous, partial range, parent, child, grandchild, KEEPONFORK, shared/file rejection\n";
    call6(64, 1, (long)msg, sizeof(msg)-1, 0, 0, 0);
    done(0);
}
