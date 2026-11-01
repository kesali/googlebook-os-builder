// Google's clients use platform libc++, not the NDK's separately named ABI.
#include <__config_site>
#undef _LIBCPP_ABI_NAMESPACE
#define _LIBCPP_ABI_NAMESPACE __1
