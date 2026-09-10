cmake_minimum_required(VERSION 3.21)
project(fcitx5-mulga VERSION 0.1.0)

set(CMAKE_EXPORT_COMPILE_COMMANDS ON CACHE INTERNAL "")

if(CMAKE_EXPORT_COMPILE_COMMANDS)
  set(CMAKE_CXX_STANDARD_INCLUDE_DIRECTORIES
      ${CMAKE_CXX_IMPLICIT_INCLUDE_DIRECTORIES})
endif()

find_package(Fcitx5Core REQUIRED)

# Compiler options that match what Fcitx 5 itself is built with (C++17).
include("${FCITX_INSTALL_CMAKECONFIG_DIR}/Fcitx5Utils/Fcitx5CompilerSettings.cmake")

enable_testing()

add_subdirectory(src)
add_subdirectory(test)
