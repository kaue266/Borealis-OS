/* Local userspace adapter: UK11.27 base_jd_atom to installed UK11.16 v2.
 * Input: x0 uku context; x1 {u64 atoms, u32 count, u32 stride=64}.
 * Keep source arrays and descriptors unchanged. The kernel copies the
 * converted array synchronously in ioctl. Completion event layout is v2
 * (24 bytes) on both sides and is intentionally unchanged.
 */
.text
.p2align 2
.global borealis_atom_adapter
.type borealis_atom_adapter, %function
borealis_atom_adapter:
    stp x29, x30, [sp, #-64]!
    mov x29, sp
    stp x19, x20, [sp, #16]
    stp x21, x22, [sp, #32]
    mov x19, x1
    bl mali_get_fd
    mov w20, w0
    ldr w21, [x19, #8]
    cmp w21, #256
    b.hi reject
    ldr w8, [x19, #12]
    cmp w8, #64
    b.ne reject
    mov w8, #48
    umull x8, w21, w8
    add x8, x8, #16
    sub sp, sp, x8
    mov x22, sp
    add x10, sp, #16
    str x10, [sp]
    str w21, [sp, #8]
    mov w8, #48
    str w8, [sp, #12]
    ldr x9, [x19]
    add x9, x9, #8
    mov w11, w21
    cbz w11, invoke
copy_atom:
    ldp x12, x13, [x9]
    stp x12, x13, [x10]
    ldp x14, x15, [x9, #16]
    stp x14, x15, [x10, #16]
    ldp x12, x13, [x9, #32]
    stp x12, x13, [x10, #32]
    add x9, x9, #64
    add x10, x10, #48
    subs w11, w11, #1
    b.ne copy_atom
invoke:
    mov w0, w20
    mov w1, #0x8002
    movk w1, #0x4010, lsl #16
    mov x2, x22
    bl mali_ioctl
    cmn w0, #1
    b.ne success
    bl mali_errno
    ldr w8, [x0]
    mov w9, #3
    mov w10, #63
    cmp w8, #16
    csel w9, w10, w9, eq
    cmp w8, #12
    mov w8, #2
    csel w0, w8, w9, eq
    b finish
reject:
    mov w0, #3
    b finish
success:
    mov w0, wzr
finish:
    mov sp, x29
    ldp x19, x20, [sp, #16]
    ldp x21, x22, [sp, #32]
    ldp x29, x30, [sp], #64
    ret
.size borealis_atom_adapter, .-borealis_atom_adapter
.section .note.GNU-stack,"",%progbits
