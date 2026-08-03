# Build Percona Binary Log Server from source

Build from source when you need to compile, debug, package, or patch the binary locally. For a product overview and configuration details, see [Percona Binary Log Server](index.md).

## Build requirements

You build the project with CMake and a supported compiler. The dependency versions in this section match the latest release tag, [`pbs-0.3.0`](https://github.com/Percona-Lab/percona-binlog-server/releases/tag/pbs-0.3.0). For other tags, check the upstream `CMakeLists.txt` for that tag.

You need the following dependencies:

* CMake 3.20.0 or later (the Boost, AWS SDK, and main-application presets need 3.21.0 or later)

* GCC 14 or Clang 19 (the only toolchains wired up as build presets at this tag)

* Boost 1.90.0 from the Boost Git repository (not the source tarball)

* `libmysqlclient` 8.0.x, for connecting to MySQL or MySQL-compatible servers

* libcurl 8.6.0 or later

* AWS SDK for C++ 1.11.774

## Create a build workspace

```bash
mkdir ws
cd ws
```

## Clone the source repository

Clone the upstream repository at the release tag that you want to build. Then create a local branch so the working tree is not in detached HEAD.

```bash
git clone -b pbs-0.3.0 https://github.com/Percona-Lab/percona-binlog-server.git
cd percona-binlog-server
git switch -c required_release
cd ..
```

## Select a build preset

Choose a configuration and a toolchain, then export the combination as `BUILD_PRESET`.

The following configurations are supported:

* `debug`

* `release`

* `asan`

The following toolchains are supported:

* `gcc14`

* `clang19`

Example:

```bash
export BUILD_PRESET=release_gcc14
```

## Build Boost

```bash
git clone --recurse-submodules -b boost-1.90.0 --jobs=8 https://github.com/boostorg/boost.git
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
git clone --recurse-submodules -b 1.11.774 --jobs=8 https://github.com/aws/aws-sdk-cpp
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

### Version pins and troubleshooting

The upstream `CMakeLists.txt` pins exact Boost and AWS SDK versions through `find_package`. If your build fails because of a version mismatch, confirm that the source tree is at the tag that you intend to build (`git status` and `git describe --tags`) and use the branches and tags shown in the Boost and AWS SDK sections. The pins differ across release tags. For the active pins, check `CMakeLists.txt` at the tag you build (for example, [`pbs-0.3.0/CMakeLists.txt`](https://github.com/Percona-Lab/percona-binlog-server/blob/pbs-0.3.0/CMakeLists.txt)).
