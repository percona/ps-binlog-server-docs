# Install Percona Binary Log Server

Choose one of two install methods. Use [Docker](install-with-docker.md) when you want a prebuilt image. Use [build from source](build-from-source.md) when you need to compile, debug, package, or patch the binary locally. This page covers only how to obtain a runnable `binlog_server`.

## Choose an installation method

* Docker — prebuilt image; no local build required ([Install with Docker](install-with-docker.md))

* Source — development and custom builds ([Build from source](build-from-source.md))

## After installation

Next steps:

* [Get Started With Percona Binary Log Server](get-started.md) — create a config and run `fetch` (one-time archive) or `pull` (continuous collection)

* [Command Reference](command-reference.md) — operational modes as commands, not installation

* [Configuration Reference](configuration-reference.md)

* [Core behavior](operational-behavior-reference.md) — reconnect logic, idle timing, and storage internals (reference, not install)

### What this page does not cover

This page does not cover day-to-day operation. Topics such as the first configuration, commands, reconnects, checkpoints, and shutdowns live in [Get Started](get-started.md), [Command Reference](command-reference.md), and [Core behavior](operational-behavior-reference.md).
