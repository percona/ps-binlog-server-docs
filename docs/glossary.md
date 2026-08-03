# Glossary

Terms used in Percona Binary Log Server documentation.

## Abbreviations

Expanded forms and how each term applies in Percona Binary Log Server.

### API

Application programming interface. A defined way for one piece of software to call another piece of software across a network or a library boundary. In this documentation, the tool accesses object storage through an HTTP-based API, for example the S3 REST API. The tool does not mount a disk.

### CLI

Command-line interface. You operate the product through the `binlog_server` program. The product provides no graphical user interface.

### CRC32

Cyclic redundancy check. A common checksum algorithm for binary log events on MySQL or MySQL-compatible servers. When `replication.verify_checksum` is enabled, the server verifies events with the source's algorithm, for example `CRC32` or `NONE`, before writing.

### DNS SRV

DNS SRV records list candidate host names and ports for a service. `connection.dns_srv_name` uses DNS SRV to discover the source, instead of using a fixed host and port.

### GTID

Global Transaction Identifier. A unique identifier for a transaction in MySQL-family replication. GTIDs allow replication to track which transactions each server has applied.

### IAM

AWS Identity and Access Management. Roles, policies, and credentials that authorize access to S3. Percona Binary Log Server does not manage IAM for you. If the credentials expire or are revoked, writes stop until you renew the credentials.

### JSON and JSONC

JSON is JavaScript Object Notation. JSONC adds `//` line comments. Remove the comments before you pass the configuration to the binary.

### Point-in-time recovery and PITR

<span id="point-in-time-recovery"></span><span id="pitr"></span>Point-in-time recovery restores a database to a chosen moment. The procedure combines a full backup with binary log events up to that moment. Percona Binary Log Server supports PITR by archiving binary logs and by providing search commands. `search_by_timestamp` returns the first N metadata records of stored files from the oldest up to the requested time (based on `min_timestamp`). `search_by_gtid_set` returns a minimal cover of stored files for a requested GTID set. The Percona Operator for MySQL (PXC) also includes a native PITR feature (`backup.pitr`) that uploads binlogs to S3 or Azure.

### PS

Percona Server for MySQL, as referenced in the [Percona Operator for MySQL (PS)](https://docs.percona.com/percona-operator-for-mysql/ps/) documentation.

### PVC

PersistentVolumeClaim. A Kubernetes resource that requests a mounted volume for file storage.

### Percona XtraDB Cluster (PXC)

PXC is a MySQL-compatible cluster that uses Galera. In the operator documentation, the abbreviation PXC refers to the cluster that is deployed with [Percona Operator for MySQL (PXC)](https://docs.percona.com/percona-operator-for-mysql/pxc/). When you archive from a PXC primary, the cluster nodes must have the correct binlog settings, for example `log_replica_updates`.

### S3

Amazon Simple Storage Service, and services that use a compatible API. Percona Binary Log Server can write to S3 as a backend through an `s3://` URI.

### TLS and SSL

Transport Layer Security (TLS) encrypts connections to the server. SSL (Secure Sockets Layer) is the older name. The two terms appear interchangeably in settings and documentation.

### URI

Uniform Resource Identifier. In Percona Binary Log Server, the storage URI specifies where binary log files are written. For example: `file:///path`, `s3://bucket/path`, or `https://host/bucket/path`. The connection settings also accept URI-style strings.

### added_gtids

The GTID set that is added by the events in a given binary log file. Search results and metadata files may include this field. Percona Binary Log Server writes this field automatically as events arrive. Manual edits to `added_gtids` serve no operational purpose.

### backend

The storage type that Percona Binary Log Server writes to. The value is `file` for the local filesystem, or `s3` for Amazon S3 or an S3-compatible service.

### binary log

A file on a MySQL or MySQL-compatible server that records data changes as events. The format is suitable for replication and for point-in-time recovery. Percona Binary Log Server reads binary logs from a remote server and writes the data to the configured storage.

### binary log event

A single record in a binary log. Examples include a row change and a GTID event (which marks the start of a transaction). Percona Binary Log Server streams events from the source and writes the events to storage.

### checkpoint

The point at which Percona Binary Log Server flushes buffered data to permanent storage. Checkpoint thresholds are evaluated when a new event is processed. A checkpoint is triggered by accumulated size (`checkpoint_size`) or by elapsed time since the last flush (`checkpoint_interval`). Without incoming events, no checkpoint occurs even after the time threshold is crossed.

### checkpoint_interval

Time-based flush threshold. When a new event is processed and at least the configured interval has elapsed since the last flush, the server writes buffered data to storage. The threshold is evaluated only on event arrival; without incoming events the buffer is not flushed even after the interval elapses. Accepts a string with an optional suffix (for example, `30s`, `5m`, `1h`).

### checkpoint_size

Size-based flush threshold. When buffered data reaches the configured size, the server writes the data to storage. Accepts a string with an optional suffix (for example, `128M`, `1G`).

### connection

A configuration section that tells Percona Binary Log Server how to reach the MySQL or MySQL-compatible source. The section covers host, port or DNS SRV name, user, password, timeouts, and optional SSL or TLS settings.

### fetch

An operation mode that connects to the source, reads every binary log event available on the source, writes the events to storage, and then exits. Use `fetch` for one-time or on-demand collection.

### fs_buffer_directory

A configuration option that sets a local directory used to stage uploads to non-file storage, for example S3. The directory is not the buffer for unflushed events — unflushed events are held in the in-memory event buffer. Data enters this directory only when a flush occurs: the server writes the flushed bytes to a UUID-named temporary file and immediately uploads the cumulative S3 object from that file. The temporary file lives only while the corresponding binlog stream is open and is removed when the stream closes (for example, on rotation or graceful shutdown). The option is optional; when omitted, the server creates a UUID-named subdirectory under the OS temporary directory (`$TMPDIR`, or `/tmp` on Linux when unset) and removes that subdirectory at clean shutdown. A `fs_buffer_directory` set explicitly is used as-is and is never deleted by the server. Set this option explicitly in production to keep the staging directory at a stable, predictable, and disk-safe location.

### graceful shutdown

A clean shutdown of the process. During a graceful shutdown, the process flushes buffered data and leaves storage consistent. A graceful shutdown is triggered by `SIGINT` or `SIGTERM`. A forced stop with `kill -9` can drop recent progress.

### GTID set

One or more GTIDs, or one or more GTID ranges. A GTID set is used to configure GTID-based replication. A GTID set is also the input to `search_by_gtid_set` when you locate the binary log files that cover a set of transactions.

### GTID-based replication

A replication mode in which the server and the client track progress by GTID set, instead of by file name and byte position. GTID-based replication enables `search_by_gtid_set` and allows smoother failover and topology changes.

### previous_gtids

The GTID set that is already present at the start of a binary log file. The set carries over from the previous file. Both the per-file metadata JSON (for example, `binlog.000001.json`) and the `search_by_timestamp` and `search_by_gtid_set` JSON output use the key `previous_gtids`. The field is empty for storage not created in GTID mode. For the first stored file, this field is normally empty. If this field is non-empty, the source MySQL had a non-empty `@@gtid_purged` when Percona Binary Log Server started. The events corresponding to those purged GTIDs are not in the archive. Percona Binary Log Server writes this field automatically when each file is created. Manual edits to `previous_gtids` serve no operational purpose.

### MinIO

An object storage server that provides an S3-compatible API. Percona Binary Log Server can write binary logs to MinIO through an HTTP or HTTPS storage URI.

### metadata file

The JSON file that Percona Binary Log Server stores together with each stored binary log. The metadata file records event timestamps and GTID sets. The search commands use these values.

### mysqlbinlog

A utility that reads binlogs from files or from a remote server. Percona Binary Log Server adds reconnection, resume, direct S3 storage, and timestamp-based or GTID-based search.

### object storage

A storage model that keeps data as objects in buckets or containers. The data is accessed through an API, for example the HTTP APIs of Amazon S3 or S3-compatible services. Percona Binary Log Server can write binlog files directly to object storage.

### idle_time

The configuration value `replication.idle_time`. The value sets, in seconds, the wait time between reconnect attempts in pull mode. The delay is fixed. The retry loop applies no exponential backoff. A short value during an outage can produce a high rate of connection attempts. A high rate can trigger rate limits or circuit breakers in cloud environments.

### list

The operation mode that is selected with the `list` command. The mode reads stored metadata and returns the metadata of every binlog file currently in storage, in chronological order. The output JSON uses the same per-file schema as `search_by_timestamp` and `search_by_gtid_set`. Unlike the search commands, `list` returns `status: success` with an empty `result` array on an empty storage. Use `list` to enumerate the archive without applying a filter, and to distinguish an empty storage from a corrupted one. See [`list` mode](operational-behavior-reference.md#list-mode) and [`list` in Command reference](command-reference.md#list).

### last_sequence_number

A field in each binlog metadata file (for example, `binlog.000001.json`) that records the `sequence_number` value of the last GTID-class event written to that file. Percona Binary Log Server uses the field to keep `sequence_number` and `last_committed` monotonic across restarts when [`replication.rewrite`](configuration-reference.md#replicationrewrite-optional) is enabled. The value is `0` when no qualifying event has been written, or when storage was not created in GTID mode. The field is written by Percona Binary Log Server as new events arrive; manual edits serve no operational purpose.

### position-based replication

A replication mode in which the client tracks progress by binlog file name and byte position. The stored files align physically with the source's binlog files.

### pull

The operation mode that is selected with the `pull` command. `pull` provides continuous archiving of the binlog stream. The `pull` command reads new events, writes the events to storage, and reconnects after pauses or errors. The command runs until you stop the process. For details about wait timing and reconnect behavior, see [Core behavior](operational-behavior-reference.md).

### purge_binlogs

The operation mode that is selected with the `purge_binlogs` command. The command takes a target binlog file name and removes every stored file with a sequence number at or below the target, together with each file's metadata sidecar. The current tail file (the most recent stored binlog) is refused to preserve the resume position. The mode rewrites `binlog.index` atomically, then deletes payloads and sidecars in a best-effort batch. A failure during batch deletion produces a `status: warning` response and leaves orphan files that the next Percona Binary Log Server startup refuses to open until manually cleaned up. Run `purge_binlogs` only when no `fetch` or `pull` process is writing to the same storage; a separate Percona Binary Log Server instance writing to a different `storage.uri` is unaffected. See [`purge_binlogs` mode](operational-behavior-reference.md#purge_binlogs-mode) and [`purge_binlogs` in Command reference](command-reference.md#purge_binlogs).

### REPLICATION SLAVE

The privilege that a user needs in order to act as a replication client and to read binary logs from the server. The account in the `connection` section must have the `REPLICATION SLAVE` privilege.

### replication client

The role that Percona Binary Log Server plays when the tool connects to a MySQL or MySQL-compatible server. The upstream server streams binary log events to the client. The account must have the `REPLICATION SLAVE` privilege.

### resume

The behavior in which a subsequent run of Percona Binary Log Server continues from the position where the previous run stopped. The resume cursor depends on the replication mode. In position-based replication, the cursor is the pair `(current binlog file name, byte position)`. In GTID-based replication, the cursor is the GTID set. The GTID set is computed as `previous_gtids ∪ added_gtids` from the most recent binlog metadata file. Resume avoids re-reads of events that are already in storage.

### S3-compatible storage

An object storage service that exposes an API that is compatible with Amazon S3, for example MinIO. Percona Binary Log Server connects to such services through an `http://` or `https://` storage URI.

### search_by_gtid_set

A command that returns the smallest set of stored binlog files that cover a given GTID set. The command requires storage that was created in GTID-based replication mode.

### search_by_timestamp

A command that walks the stored binlog records in order from the oldest and returns every record up to and including the last record whose `min_timestamp` is at or before the timestamp that you supply. As soon as the command encounters a record whose `min_timestamp` is greater than that timestamp, the walk stops. The result is therefore the first N records of the binlog metadata list, not a minimal cover. If even the oldest record's `min_timestamp` is greater than the requested timestamp, the command returns `Timestamp is too old`.

### server_id

The numeric identifier that the replication client presents to the upstream server. The replication protocol requires this value. Set the value through `replication.server_id`.

### storage

The configuration section that defines where Percona Binary Log Server writes binlog files. The section contains the backend type and URI, and optional buffer directory and checkpoint settings.

### transaction boundary

A point in a binary log that marks the start or the end of a transaction. Percona Binary Log Server flushes at transaction boundaries whenever possible. As a result, the stored files remain usable for recovery and resume. In GTID-based replication, the GTIDs of complete transactions in a given binlog file are recorded as [`added_gtids`](#added_gtids) in the file's metadata.

### warning (response status)

A top-level `status` value emitted by [`purge_binlogs`](#purge_binlogs) when the command commits the new `binlog.index` but the subsequent payload-and-metadata deletion partially or fully fails. The accompanying response carries the metadata of the targeted files in `result` and the underlying backend error in `message`. The storage is then in a partial state — `binlog.index` no longer references the listed files, but the files still exist on disk or in the bucket. Percona Binary Log Server's startup validators detect the orphans and refuse to open the storage on the next run; recovery is manual deletion of the leftover files. The other commands return only `success` or `error`; `warning` is unique to `purge_binlogs`. See [Search, list, and purge response format](operational-behavior-reference.md#search-list-and-purge-response-format).
