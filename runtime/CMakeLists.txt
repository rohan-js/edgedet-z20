cmake_minimum_required(VERSION 3.20)
project(edgedet_runtime C)

set(CMAKE_C_STANDARD 99)
set(CMAKE_C_STANDARD_REQUIRED ON)

add_library(edz_runtime STATIC
    src/edz_accel_io.c
    src/edz_protocol.c
    src/edz_postprocess.c
)
target_include_directories(edz_runtime PUBLIC include)

if(MSVC)
    target_compile_options(edz_runtime PRIVATE /W4)
else()
    target_compile_options(edz_runtime PRIVATE -Wall -Wextra -Wpedantic -Werror)
    target_link_libraries(edz_runtime PUBLIC m)
endif()

include(CTest)
if(BUILD_TESTING)
    add_executable(edz_runtime_tests tests/test_runtime.c)
    target_link_libraries(edz_runtime_tests PRIVATE edz_runtime)
    add_test(NAME edz_runtime_tests COMMAND edz_runtime_tests)
endif()
