cmake_minimum_required(VERSION 3.21)
project(RallySlateSimulator C CXX)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_C_STANDARD 11)
if("$ENV{UNA_SDK}" STREQUAL "")
  message(FATAL_ERROR "Set UNA_SDK to the pinned official SDK checkout")
endif()
include($ENV{UNA_SDK}/cmake/una-simulator.cmake)
set(APP_ROOT ${CMAKE_CURRENT_SOURCE_DIR}/..)
add_executable(RallySlateSimulator
  main.cpp ${APP_ROOT}/Service/Service.cpp
  ${APP_ROOT}/Source/Gui.cpp ${APP_ROOT}/Source/Model.cpp ${APP_ROOT}/Source/Screen.cpp ${APP_ROOT}/Source/Notices.cpp
  ${UNA_SDK_SOURCES_SIMULATOR} ${UNA_SDK_SOURCES_SIMULATOR_SERVICE} ${UNA_SDK_SOURCES_SIMULATOR_LVGL})
target_include_directories(RallySlateSimulator PRIVATE
  ${CMAKE_CURRENT_SOURCE_DIR} ${APP_ROOT} ${APP_ROOT}/Source ${APP_ROOT}/Service
  ${UNA_SDK_INCLUDE_DIRS_SIMULATOR} ${UNA_SDK_INCLUDE_DIRS_GUI_LVGL})
target_compile_definitions(RallySlateSimulator PRIVATE
  ${UNA_SDK_DEFINES_SIMULATOR} ${UNA_SDK_DEFINES_GUI_LVGL}
  LV_MEM_SIZE=65536
  APP_ID="BEC65A5C096E4894" DEV_ID="brodyga45" BUILD_VERSION="0.1.0-sim"
)
find_package(Threads REQUIRED)
target_link_libraries(RallySlateSimulator PRIVATE Threads::Threads)
una_simulator_link_sdl2(RallySlateSimulator)
option(RALLY_TRACE_FRAMES "Write diagnostic app framebuffer snapshots" OFF)
if(RALLY_TRACE_FRAMES)
  target_compile_definitions(RallySlateSimulator PRIVATE RALLY_TRACE_FRAMES)
endif()
if(NOT MSVC)
  target_compile_options(RallySlateSimulator PRIVATE -Wall -Wextra -Wno-unused-parameter)
endif()
