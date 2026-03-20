# Percona Binary Log Server

## Architecture

![Architecture: Source MySQL to Percona Binary Log Server to Local Disk or S3](/_static/binlog-arch.png)

Percona Binary Log Server runs as a single process. The server connects to a source MySQL server as a [replication client](glossary.md#replication-client), reads [binary log](glossary.md#binary-log) events over the MySQL replication protocol, and writes those events to configured [storage](glossary.md#storage) (local filesystem or [S3-compatible](glossary.md#s3-compatible-storage) object storage). The architecture diagram at the top of this page summarizes the data path; the following describes how connections and writes actually behave.

### Data path and process model

* One configuration file and one process: no separate “archiver” and “uploader” daemons. The same process reads from MySQL and writes to the chosen backend.

* Writes are committed only at [transaction boundary](glossary.md#transaction-boundary) points. Stored binlog files do not contain half-written transactions. If the process is killed, the last visible data on disk or S3 ends at the last flushed transaction. See [Transaction-safe writes](#transaction-safe-writes) and [Core behavior](operational-behavior-reference.md) for details.

* [Resume](glossary.md#resume) is automatic. A new run reads the last position from storage (metadata and [checkpoint](glossary.md#checkpoint) state) and continues from there; no manual position bookkeeping is required.

### Connection management

* Single active connection. The server maintains one replication connection to the source MySQL server at a time. The server does not open multiple replication streams or connection pools.

* [`fetch`](glossary.md#fetch) mode. Connect, read all available events, write to storage, then disconnect and exit. Any error (network, disk full, and so on) terminates the process; storage is left consistent at the last transaction boundary.

* [`pull`](glossary.md#pull) mode. Connect and read until caught up. When no new events are available, the server waits on the connection for up to the configured read timeout (see `connection.read_timeout`). If that time elapses with no new data, the server closes the connection and enters an idle phase: the server sleeps for `replication.idle_time` seconds, then reconnects and repeats. So the reconnect interval in pull mode is a fixed delay (`idle_time`), not exponential backoff.

* [Graceful shutdown](glossary.md#graceful-shutdown). On SIGINT or SIGTERM, the server flushes buffered data at a transaction boundary and exits. Response can be delayed by up to `connection.read_timeout` seconds plus idle-sleep granularity, because the MySQL client API blocks on read. See [Core behavior](operational-behavior-reference.md#graceful-shutdown).

* Network failure and reconnect. In fetch mode any error exits the process; in pull mode the server retries after connect or switch-to-replication failure, and after connection-lost (`CR_SERVER_LOST`) during read, by sleeping `replication.idle_time` then reconnecting (fixed delay only, no exponential backoff). A short `idle_time` during an outage can storm the source and trigger rate limits or circuit breakers in cloud environments; set `idle_time` to 30s or 60s in production unless you need faster retries. Full details and best practice: [Core behavior](operational-behavior-reference.md#network-failure-and-reconnect-behavior).

### Transaction-safe writes

Stored binary logs are the basis for recovery; partial transactions would make them unusable. Percona Binary Log Server avoids partial writes:

* The server flushes data to storage only at transaction boundaries. Each binlog file on disk or in S3 never contains a half-written transaction.

* With `replication.verify_checksum` enabled, binlog event checksums are verified before writing (the source’s algorithm, for example MySQL CRC32 or NONE). That reduces the risk of persisting corrupted data.

* If the process is killed (for example, `kill -9`), the last visible data ends at the last transaction that was flushed. A new run resumes from that position. Full details: [Core behavior](operational-behavior-reference.md#transaction-atomicity-and-partial-writes).

## What you get (and what to watch)

Factual outcomes and operational caveats:

* Resume without re-download. A new run continues from the last position stored in metadata; no manual position tracking.

* Search by time or [GTID set](glossary.md#gtid-set). [`search_by_timestamp`](glossary.md#search_by_timestamp) and [`search_by_gtid_set`](glossary.md#search_by_gtid_set) return the minimal set of stored files for a given point in time or GTID set, so you can feed the right files into your recovery or downstream pipeline.

* Binlog archiving to [S3](glossary.md#s3). The server can write directly to S3 or S3-compatible storage with configurable [checkpoint](glossary.md#checkpoint)s. S3 does not support append; each flush re-uploads the object, so short checkpoints can cause very high PUT cost. See [Cost Optimization (S3)](storage-reference.md#cost-optimization-s3) and [Storage Reference](storage-reference.md).

* Operational risks to plan for. The server does not manage IAM or credentials. If the IAM role or credentials used for S3 expire or are revoked, writes will fail until credentials are fixed. S3 or endpoint rate limits can cause upload failures; the application may retry (behavior is implementation-dependent), but you should monitor storage errors and alert on them. For graceful shutdown and consistent storage, use SIGINT/SIGTERM; `kill -9` can leave recent data unwritten.

## When NOT to use this

If your MySQL source is on Percona Operator for MySQL (PXC) v2.x or later, use the operator’s native PITR (`backup.pitr`) unless you need something the Binary Log Server provides (for example, streaming to a third-party or data lake, or search by timestamp/GTID). Do not run the Binary Log Server and the operator’s PITR agent against the same bucket and prefix. See [Using with Percona Operators](use-with-operators.md) for the [decision matrix](use-with-operators.md#decision-matrix) and when to ignore this tool.

!!! warning "Note for PXC users"
    If you connect the Binary Log Server to a Percona XtraDB Cluster (PXC) node, ensure `log_slave_updates` (or `log_replica_updates`) is enabled on that node. If it is OFF, the node’s binlog contains only writes that originated on that node, not writes applied from other cluster nodes, so your archive will miss cluster traffic and recovery will be incomplete. See [Using with Percona Operators](use-with-operators.md#connecting-to-the-cluster) for the full requirement.

## Features

Percona Binary Log Server provides the following capabilities:

* streaming binary logs from Oracle MySQL Server and Percona Server for MySQL

* storing binary log files on a local filesystem or in object storage

* supporting position-based replication and GTID-based replication

* resuming work from the last completed position after restart

* searching saved binary logs by timestamp

* searching saved binary logs by GTID set

* supporting TLS and SSL connection settings

* supporting graceful shutdown with consistent storage state

## Documentation By Task

Start here for installation and first-time use:

* [Install Percona Binary Log Server](install.md)

* [Build Percona Binary Log Server From Source](build-from-source.md)

* [Get Started With Percona Binary Log Server](get-started.md)

Before trusting the server with production binlogs, read how the server keeps storage consistent and how to run the server in production:

* [Core behavior](operational-behavior-reference.md) — transaction-safe writes, metadata files, resume, graceful shutdown, and network failure and reconnect behavior

* [Operations](operations.md) — logging, monitoring, and alerting in production

* [Using with Percona Operators](use-with-operators.md) — run alongside Percona Operator for MySQL (PS or PXC); connect to the primary, deploy in Kubernetes

## Reference

Use the following pages for lookup information:

* [Command Reference](command-reference.md)

* [Configuration Reference](configuration-reference.md)

* [Storage Reference](storage-reference.md)

* [Glossary](glossary.md)

* [FAQ](faq.md)

## Licensing

Percona Binary Log Server uses GPLv2.
