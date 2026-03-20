# Core Behavior

This page describes how Percona Binary Log Server works: transaction-safe writes, metadata files, resume behavior, graceful shutdown, network failure and reconnect behavior, and impact on the primary (memory, backpressure, and internal flow). Understanding the behavior described in the present page is essential for operating and recovering the server.

Percona Binary Log Server connects to a remote MySQL server as a [replication client](glossary.md#replication-client). During an active session, the process reads [binary log](glossary.md#binary-log) events and writes those events to configured [storage](glossary.md#storage).

Two common collection workflows exist:

* [fetch](glossary.md#fetch) for one-time collection

* [pull](glossary.md#pull) for continuous collection

## Transaction Atomicity and Partial Writes

Percona Binary Log Server avoids writing partial transactions to storage. Data is committed to disk or object storage only at [transaction boundary](glossary.md#transaction-boundary) points. So each stored binlog file never contains a half-written transaction: either a transaction is fully present up to its commit, or the next transaction has not started. That keeps storage consistent for recovery and for resume.

How partial writes are avoided:

* The server parses transaction boundaries in the binary log stream (for example, using GTID log events and transaction size information). Writes are flushed only when a complete transaction has been received.

* When `replication.verify_checksum` is enabled in the configuration file, the server verifies binlog event checksums before writing. The source controls the checksum algorithm (for example, MySQL `binlog_checksum` is `CRC32` by default or `NONE` to disable). When the source has checksums enabled (such as CRC32), the server verifies each event’s checksum; when the source has checksums disabled (`binlog_checksum=NONE`), there are no checksums to verify. The application supports only the same two algorithms as MySQL: CRC32 and NONE. Before switching to replication the client sets `@source_binlog_checksum` and `@master_binlog_checksum` to CRC32 or NONE per `verify_checksum` (see [Percona-Lab/percona-binlog-server](https://github.com/Percona-Lab/percona-binlog-server) `easymysql/connection.cpp`). Verification helps detect corruption early and avoids persisting bad data.

* Implementation details such as the use of temporary files or write-ahead buffers are not fully documented in the public reference. The guarantee is that the visible state on storage is always transaction-consistent: no partial transaction is left in a binlog file.

If the process is killed mid-stream (for example, with `kill -9`), the last visible data on storage ends at the last transaction boundary that was flushed. Any in-progress transaction is not written; a new run resumes from that last safe position.

## Where the resume position is stored

The server does not use a local database (no SQLite or similar). All state that defines “where to resume” is stored in the same storage backend you configure (local directory or S3). So you have a full audit trail: the same backend holds both the binlog data and the metadata that describes resume position and search indexes.

Exactly where (see [Percona-Lab/percona-binlog-server](https://github.com/Percona-Lab/percona-binlog-server), `storage.hpp` / `storage.cpp`):

* Top-level replication mode. One object named `metadata.json` in the storage root. The object contains the replication mode (`position` or `gtid`). The server loads `metadata.json` first when the storage is not empty.

* List of binlog files. One object named `binlog.index` in the storage root. The object is a text file: one line per binlog file, each line a path like `./binlog.000001`. The order of lines is the order of binlog files. The server uses `binlog.index` to know which file is the “current” one (the last line) and the full list for validation.

* Per-file metadata (resume position and search index). For each binlog file there is a companion JSON object with the same base name and the extension `.json`. For example, for `binlog.000001` the object is `binlog.000001.json`. That JSON holds: `size` (flushed size of the binlog file in bytes, that is the byte position at which the next event would be written), `previous_gtids`, `added_gtids`, `min_timestamp`, `max_timestamp`. The resume position is: (current binlog file name, byte position). The current binlog file is the last entry in `binlog.index`. The byte position is the `size` value from that file’s `.json` (the last flushed position in that file). So resume state is: last line of `binlog.index` + `size` (and for GTID mode, GTID sets) from the corresponding `.json` file.

All of these objects are written and read through the same backend abstraction (`put_object` / `get_object`). So for a file backend, they are regular files under the directory you set in `storage.uri` (for example, `metadata.json`, `binlog.index`, `binlog.000001`, `binlog.000001.json`). For an S3 (or S3-compatible) backend, they are objects in the same bucket and prefix as the binlog files (for example, `metadata.json`, `binlog.index`, `binlog.000001`, `binlog.000001.json`). There is no separate “local only” state: if the backend is S3, everything (including resume position) is in S3.

If you lose the local server’s SSD: with a file backend, the storage is that local directory, so you lose the state and the binlogs unless you have another copy. With an S3 backend, all state and binlogs live in the bucket; you can point a new instance at the same `storage.uri` and the new instance will load `metadata.json`, `binlog.index`, and each `*.json` from S3 and resume from the position stored there. So you can reconstruct state from the S3 metadata (and binlog objects) alone; no local SSD is required.

## Metadata Files (JSON Schema and How to Use Them)

Percona Binary Log Server keeps one JSON metadata file per stored binary log file. The metadata file has the same name as the binlog file with the extension `.json` (for example, `binlog.000001.json`). These files record what is inside each binlog file so that search commands and resume logic do not need to scan the binary data.

### Metadata JSON schema

Each metadata file describes one binlog file. The fields match the structure returned by `search_by_timestamp` and `search_by_gtid_set`. The following fields are used:

* `name`: binary log file name (for example, `binlog.000001`)

* `size`: current size of the binlog file in bytes

* `uri`: full storage URI of the binlog file (for example, `file:///var/lib/binlog-server/binlog.000001` or `s3://bucket/prefix/binlog.000001`)

* `min_timestamp`: earliest event timestamp in the file (ISO format)

* `max_timestamp`: latest event timestamp in the file (ISO format)

* `initial_gtids` (in search output) / `previous_gtids` (in stored per-file JSON): GTID set that was already present at the start of this file (empty for the first file, or when not using GTID mode)

* `added_gtids`: GTID set added by events in this file (empty when not using GTID mode)

The per-file metadata files on disk (for example, `binlog.000001.json`) use the key `previous_gtids`; search command output may use `initial_gtids` for the same value. Exact key names and any extra implementation-specific fields may vary. The search commands and resume logic rely on the presence of timestamp and GTID information to find the minimal set of files for a given time or GTID set.

### Using the metadata when you have only the files

If the server is lost but the binlog files and their metadata files are still available (on local disk or in S3), you can reconstruct how to use the storage:

* Point a new Percona Binary Log Server instance at the same storage (same `storage.uri` and `storage.backend`). A new run resumes from the position recorded in that storage; the server reads the existing metadata to determine the last position and does not re-download or re-read from the source for already-stored data.

* Run `search_by_timestamp` or `search_by_gtid_set` against that storage (with a config that points at the same URI). The commands read the metadata files to return the minimal set of binlog files for the given timestamp or GTID set. You do not need to scan the raw binlog files yourself.

* For point-in-time recovery, use `search_by_timestamp` to get the list of files that cover the target time, then use those files (and a full backup) with your MySQL recovery procedure. For GTID-based recovery, use `search_by_gtid_set` to get the minimal set of files that cover the target GTID set.

So: the metadata files are the index that makes search and resume possible. Keep the metadata files together with the binlog files; without them, you would have to scan binlogs manually to find the right files or the resume position.

## Resume Behavior

A later run resumes from the position saved by the previous run. This behavior applies across operation modes. The server reads that position from the storage backend: the last binlog file name from `binlog.index` and the flushed byte position (`size`) from that file’s `.json` metadata (see [Where the resume position is stored](#where-the-resume-position-is-stored)). No manual bookkeeping is required; no local database or hidden local state is used.

## Graceful Shutdown

Percona Binary Log Server supports graceful shutdown for `fetch` and `pull`.

Supported POSIX signals:

* `SIGINT`

* `SIGTERM`

Examples:

```bash
Ctrl+C
kill <pid>
```

Graceful shutdown helps keep storage consistent. The server flushes buffered data and commits at a transaction boundary before exiting.

`kill -9` does not provide the same safety. A forced stop can leave buffered data unwritten and can lose recent progress. If you run the server under systemd, set `TimeoutStopSec` long enough to allow a graceful flush; otherwise systemd may send SIGKILL before the process has finished flushing. Set `TimeoutStopSec` to at least `connection.read_timeout` plus a few seconds (for example, 90 or 120 seconds when `read_timeout` is 60).

Due to synchronous MySQL client behavior, response to a stop signal may take up to:

* waiting for `connection.read_timeout` seconds

* waiting for one additional second during idle sleep timing

## Network failure and reconnect behavior

What happens when the network fails or the source MySQL server becomes unreachable depends on the operation mode and where the failure occurs. The following behavior is implemented in the application (see [Percona-Lab/percona-binlog-server](https://github.com/Percona-Lab/percona-binlog-server)).

Fetch mode. Any error terminates the process. That includes failure to connect, failure to switch the connection to replication mode, connection loss or other errors while reading events, and non-network errors (for example, out of disk space). The process exits; storage is left consistent at the last transaction boundary that was flushed. There is no retry or reconnect in fetch mode.

Pull mode: failure during connect or when switching to replication. If the server cannot establish a TCP connection to the source MySQL server, or the connection is established but switching the session to replication mode (position or GTID) fails, the application catches the MySQL client error, logs a message (for example, “unable to establish connection to mysql server” or “unable to switch to replication”), and returns. The main pull loop then sleeps for `replication.idle_time` seconds and tries again. The application uses a fixed delay only; there is no exponential backoff. The delay between attempts is always `idle_time` seconds, so during a network partition or source outage the process will retry at that interval until the source is reachable again.

Pull mode: failure while reading binlog events. The application reads events by calling the MySQL client’s binlog fetch API. If that call fails, the application checks the MySQL error code. If the error is `CR_SERVER_LOST` (connection lost to the server), the application does not throw; the fetch returns false, the current event buffer is flushed to storage at a transaction boundary, and the read loop exits. Control returns to the main pull loop, which sleeps for `idle_time` seconds and then reconnects (same as after a normal “no more events” timeout). So a connection-lost failure during the read stream is treated like a clean disconnect: the server reconnects after one idle interval and resumes from the last position stored in metadata. If the MySQL error code is anything other than `CR_SERVER_LOST` during fetch (for example, a protocol or server error), the application throws; the exception is not caught inside the read loop, so the process exits. In that case the process does not reconnect automatically.

Pull mode: non-recoverable errors. Errors that are not treated as “retry after idle” cause the process to exit. That includes out-of-disk or storage write failures, and any MySQL error during read that is not `CR_SERVER_LOST`. After exit, a new run (or a process manager restart) resumes from the last position in storage.

### Best practice: `idle_time`

In pull mode the only delay between reconnect attempts is `replication.idle_time`; there is no backoff. During a network partition or when the source is down, the process will therefore attempt to reconnect every `idle_time` seconds. A short `idle_time` (the default is 10 seconds) can produce a high rate of connection attempts. In cloud environments, that can trigger rate limiting, connection limits, or circuit breakers on the source or on intermediate infrastructure (load balancers, proxies, or security controls), and may lead to the client being temporarily blacklisted. Set `idle_time` high enough that reconnect attempts during an outage do not storm the source: for example, 30 to 60 seconds or more when the source is behind cloud infrastructure or rate limiters. The default of 10 seconds is often too aggressive for production; consider 30s or 60s unless you have a specific reason to retry more frequently. Use monitoring and alerting to detect repeated reconnect cycles or process exits so you can respond to source or network issues.

## Impact on the primary, memory footprint, and internal flow

DBAs need to know whether a slow or failing consumer (for example, S3 in another region having a bad day) can stall the primary MySQL server. The following is derived from the application implementation (see [Percona-Lab/percona-binlog-server](https://github.com/Percona-Lab/percona-binlog-server)).

Can the tool stall the primary? In pull mode, the application uses the MySQL client in blocking replication mode (the client does not set `BINLOG_DUMP_NON_BLOCK`). The main thread runs a tight loop: fetch one binlog event from the MySQL connection (blocking read), then call the storage layer to append that event to an in-memory event buffer and, when a checkpoint condition is met, flush the buffer to the backend (file or S3). The flush is synchronous: the thread blocks until the backend has accepted the data (for example, until the S3 upload completes). So if the storage backend is slow (high latency to S3, a flaky network to the storage region, or rate limiting), the thread spends more time in the write path and does not call the MySQL client’s fetch again. The MySQL client therefore does not read from the TCP socket. The socket’s receive buffer fills, and the primary’s binlog dump thread can block when sending the next event. So yes: a slow or stalled consumer (for example, S3 in Virginia having a bad day while the primary is elsewhere) can cause the primary’s binlog dump thread to block. The primary is not fully “stalled” (other clients and replicas are unaffected), but the dump thread serving this replication client will block until the consumer reads again. In fetch mode the client uses non-blocking replication mode and reads until no more events; fetch is typically used for one-off runs, so long-term backpressure on the primary is less of a concern.

Memory footprint. The application maintains an in-memory event buffer (a single `std::vector`) that holds binlog event data until a flush is triggered. The buffer is initially reserved at 16,384 bytes (`default_event_buffer_size_in_bytes` in the source). There is no documented hard cap on the buffer size. Data is flushed only at transaction boundaries; a flush is triggered when (1) there is at least one complete transaction in the buffer and (2) either the size of data ready to flush has reached `checkpoint_size` (if configured) or the time since the last checkpoint has reached `checkpoint_interval` (if configured), or the event is a special end-of-file marker (ROTATE/STOP). So the buffer can grow until the next transaction boundary and the next checkpoint. In the worst case, one very large transaction (for example, a large batch insert) can sit entirely in the event buffer until the transaction completes and a checkpoint condition is met. The process also uses the MySQL client library’s own buffers (for example, the buffer used by `mysql_binlog_fetch`); their size is determined by the client library and the server. Plan for memory usage that can reach at least the size of your largest transaction between checkpoints, plus base process and MySQL client overhead. Tuning `checkpoint_size` and `checkpoint_interval` affects how often data is flushed and thus how much data can accumulate in the event buffer between flushes.

Internal flow and queueing. There is no separate producer thread and consumer thread. A single thread reads from MySQL and writes to storage. The flow is: read one event (blocking) → append to event buffer → if checkpoint condition at transaction boundary, flush buffer to backend (blocking). So there is no unbounded queue between “read” and “write”: the only buffering is the event buffer (described in the Memory footprint section) and the TCP receive buffer on the MySQL connection. Backpressure is natural: when the backend is slow, the thread blocks in the flush, so the thread does not read the next event, so the MySQL client does not drain the socket, so the primary’s send can block. That is the same mechanism that can stall the primary’s binlog dump thread when storage is slow. If you need to avoid blocking the primary when storage is slow, run the Binary Log Server in a context where storage is fast and reliable (for example, local disk or a nearby S3 region), or accept that the dump thread for the Binary Log Server client may block during storage slowdowns.

## Search Command Output

Search commands return JSON with one of two top-level states:

* `status: "success"`

* `status: "error"`

A success result usually contains a list of binlog file entries; each entry has the same shape as the [metadata JSON schema](#metadata-json-schema-and-how-to-use-them) in this page:

* `name`

* `size`

* `uri`

* `min_timestamp`

* `max_timestamp`

* `initial_gtids`

* `added_gtids`
