# Percona Binary Log Server documentation

Percona Binary Log Server (`binlog_server`) is a command-line utility.

The utility works as a remote `mysqlbinlog` client with extra features.

Binary Log Server streams binary log events from Oracle MySQL Server or Percona Server for MySQL.

The utility writes events to a local filesystem or to Amazon Simple Storage Service (Amazon S3).

S3-compatible services such as MinIO are also supported.

The utility can reconnect and continue from the last stored position after an interruption.

## Features

* Fetch or pull binary logs from a remote source in position-based or Global Transaction Identifier (GTID) mode

* Store binlogs on local disk or object storage, with optional checkpoints

* Search and list stored binlogs by timestamp or GTID set

* Purge older binlog files

* Secure connections with Secure Sockets Layer (SSL) or Transport Layer Security (TLS) to the source MySQL server

* Encrypt binlogs at rest with a local keyring and per-file encryption envelopes

## Security

| Topic | Description |
|-------|-------------|
| [SSL and TLS connections](ssl-tls-connections.md) | Encrypt the replication connection to the source (`connection.ssl` / `connection.tls`) |
| [Binlog storage encryption](binlog-encryption.md) | Encrypt stored binlog files with a keyring and key-encryption key (KEK) (`storage.encryption`) |

## Source code

The product source code is in [Percona-Lab/percona-binlog-server](https://github.com/Percona-Lab/percona-binlog-server).

## Get help

* [Get help from Percona](get-help.md)

* [Copyright and licensing](copyright-and-licensing-information.md)
