cmake_minimum_required(VERSION 3.18)
project(gbos_builder_lpmake LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

find_path(ANDROID_BASE_INCLUDE android-base/file.h PATH_SUFFIXES android REQUIRED)
find_path(ANDROID_EXT4_INCLUDE ext4_utils/ext4_utils.h PATH_SUFFIXES android REQUIRED)
find_path(ANDROID_SPARSE_INCLUDE sparse/sparse.h PATH_SUFFIXES android REQUIRED)
find_path(ANDROID_CUTILS_INCLUDE cutils/android_get_control_file.h PATH_SUFFIXES android REQUIRED)
foreach(name base log sparse ext4_utils cutils)
    find_library(ANDROID_${name}_LIBRARY NAMES ${name} PATH_SUFFIXES android REQUIRED)
endforeach()
find_package(OpenSSL REQUIRED)
find_package(ZLIB REQUIRED)

set(LIBLP "${LP_CORE}/fs_mgr/liblp")
add_executable(lpmake
    "${LP_EXTRAS}/partition_tools/lpmake.cc"
    "${LIBLP}/builder.cpp"
    "${LIBLP}/super_layout_builder.cpp"
    "${LIBLP}/images.cpp"
    "${LIBLP}/partition_opener.cpp"
    "${LIBLP}/property_fetcher.cpp"
    "${LIBLP}/reader.cpp"
    "${LIBLP}/utility.cpp"
    "${LIBLP}/writer.cpp"
)
target_compile_definitions(lpmake PRIVATE _FILE_OFFSET_BITS=64)
target_include_directories(lpmake PRIVATE
    "${LIBLP}/include" "${ANDROID_BASE_INCLUDE}" "${ANDROID_EXT4_INCLUDE}"
    "${ANDROID_SPARSE_INCLUDE}" "${ANDROID_CUTILS_INCLUDE}"
)
target_link_libraries(lpmake PRIVATE
    ${ANDROID_base_LIBRARY} ${ANDROID_log_LIBRARY} ${ANDROID_sparse_LIBRARY}
    ${ANDROID_ext4_utils_LIBRARY} ${ANDROID_cutils_LIBRARY}
    OpenSSL::Crypto ZLIB::ZLIB
)
