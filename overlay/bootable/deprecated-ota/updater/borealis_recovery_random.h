// Copyright 2026 The BorealisOS Authors
// SPDX-License-Identifier: Apache-2.0
#pragma once

#include <errno.h>
#include <stdint.h>
#include <stdlib.h>
#include <sys/random.h>
#include <unistd.h>

// This header is included ONLY by the statically linked legacy OTA updater.
// Recovery kernels without MADV_WIPEONFORK cannot run modern Bionic's cached
// arc4random PRNG. Use the kernel CSPRNG directly instead: blocking getrandom
// waits for initialization, and no userspace PRNG state is inherited on fork.
// Do not include this in Android's libc or other platform executables.
#if !defined(__BIONIC__) && !defined(BOREALIS_UPDATER_RANDOM_HOST_TEST)
#error "This compatibility implementation is restricted to the Bionic OTA updater"
#endif

#if defined(__GLIBC__)
#define BOREALIS_RANDOM_NOTHROW noexcept
#else
#define BOREALIS_RANDOM_NOTHROW
#endif

extern "C" void arc4random_buf(void* buffer, size_t length) BOREALIS_RANDOM_NOTHROW {
  const int saved_errno = errno;
  auto* cursor = static_cast<unsigned char*>(buffer);
  while (length != 0) {
    // Small reads have the strongest getrandom guarantees; still handle
    // interrupted and partial reads explicitly. Never use GRND_NONBLOCK or
    // fall back to uninitialized /dev/urandom on a broken/absent syscall.
    const size_t requested = length < 256 ? length : 256;
    const ssize_t count = getrandom(cursor, requested, 0);
    if (count == -1 && errno == EINTR) continue;
    if (count <= 0 || static_cast<size_t>(count) > requested) {
      static constexpr char message[] =
          "Borealis updater: getrandom failed; refusing unsafe randomness\n";
      // Avoid allocators and logging that may recursively request randomness.
      (void)write(STDERR_FILENO, message, sizeof(message) - 1);
      abort();
    }
    cursor += count;
    length -= static_cast<size_t>(count);
  }
  errno = saved_errno;
}

extern "C" uint32_t arc4random(void) BOREALIS_RANDOM_NOTHROW {
  uint32_t result;
  arc4random_buf(&result, sizeof(result));
  return result;
}

extern "C" uint32_t arc4random_uniform(uint32_t upper_bound) BOREALIS_RANDOM_NOTHROW {
  if (upper_bound < 2) return 0;
  // Rejection sampling preserves the public API's uniform distribution.
  const uint32_t threshold = -upper_bound % upper_bound;
  uint32_t value;
  do {
    value = arc4random();
  } while (value < threshold);
  return value % upper_bound;
}

// Bionic's startup registers these atfork hooks. There is no PRNG cache or
// mutex in this executable's implementation. Defining all five entry points
// keeps the incompatible cached PRNG object out of the static libc link.
extern "C" void arc4random_mutex_lock() {}
extern "C" void arc4random_mutex_unlock() {}

#undef BOREALIS_RANDOM_NOTHROW
