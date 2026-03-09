# Build Percona Binary Log Server From Source

Use a source build when local compilation, debugging, packaging work, or source-code changes are required.

For general product information, command usage, and configuration details, see the main page:

* [Percona Binary Log Server](index.md)

## Build Requirements

Build from source with CMake and a supported compiler.

Dependencies:

* CMake 3.20.0 or later (the provided CMake presets for Boost, AWS SDK, and the main application require CMake 3.21.0 or later)

* Clang 15 through 19, or GCC 12 through 14

* Boost 1.88.0 from the Boost Git repository

* MySQL client library 8.0.x (`libmysqlclient`)

* libcurl 8.6.0 or later

* AWS SDK for C++ 1.11.570

## Create a Build Workspace

```bash
mkdir ws
cd ws
```

## Clone the Source Repository

```bash
git clone https://github.com/Percona-Lab/percona-binlog-server.git
```

## Select a Build Preset

Set `BUILD_PRESET` to a supported configuration and toolchain.

Supported configurations:

* `debug`

* `release`

* `asan`

Supported toolchains:

* `gcc14`

* `clang19`

Example:

```bash
export BUILD_PRESET=release_gcc14
```

## Build Boost

```bash
git clone --recurse-submodules -b boost-1.88.0 --jobs=8 https://github.com/boostorg/boost.git
cd boost
git switch -c required_release
cp ../percona-binlog-server/extra/cmake_presets/boost/CMakePresets.json .
cmake . --preset "${BUILD_PRESET}"
cmake --build "../boost-build-${BUILD_PRESET}" --parallel
cmake --install "../boost-build-${BUILD_PRESET}"
cd ..
```

## Build AWS SDK for C++

```bash
git clone --recurse-submodules -b 1.11.570 --jobs=8 https://github.com/aws/aws-sdk-cpp
cd aws-sdk-cpp
git switch -c required_release
cp ../percona-binlog-server/extra/cmake_presets/aws-sdk-cpp/CMakePresets.json .
cmake . --preset "${BUILD_PRESET}"
cmake --build "../aws-sdk-cpp-build-${BUILD_PRESET}" --parallel
cmake --install "../aws-sdk-cpp-build-${BUILD_PRESET}"
cd ..
```

## Build Percona Binary Log Server

```bash
cmake ./percona-binlog-server --preset "${BUILD_PRESET}"
cmake --build "./percona-binlog-server-build-${BUILD_PRESET}" --parallel
```

The final binary is available at:

```text
ws/percona-binlog-server-build-${BUILD_PRESET}/binlog_server
```

Source project: [Percona Binary Log Server README](https://github.com/Percona-Lab/percona-binlog-server/blob/main/README.md)
