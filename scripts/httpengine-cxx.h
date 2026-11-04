// HttpEngine's exported atomic helpers use Chromium's libc++ namespace.
#include <__config_site>
#undef _LIBCPP_ABI_NAMESPACE
#define _LIBCPP_ABI_NAMESPACE __Cr
// libc++ explicitly supports this hook; retain fatal assertions without a namespace shim.
#define _LIBCPP_VERBOSE_ABORT(...) __builtin_abort()
