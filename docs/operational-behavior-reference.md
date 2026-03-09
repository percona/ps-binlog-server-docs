# Core behavior

This page is a reference for the following topics: transaction-safe writes, metadata, resume, graceful shutdown, reconnect logic, and the server's impact on the primary (memory, backpressure, and single-threaded flow). This page covers internal behavior and tuning, including timeouts, loops, and client-library details. This page is not an installation guide ([Install](install.md)) and is not a high-level mode summary ([Command Reference](command-reference.md)). Read this reference before you operate or recover production workloads when you need to know *how* the server implements `fetch` and `pull`.

Percona Binary Log Server connects to a MySQL or MySQL-compatible server as a [replication client](glossary.md#replication-client), reads [binary log](glossary.md#binary-log) events, and writes them to [storage](glossary.md#storage).

Collection modes:

* [fetch](glossary.md#fetch) for one-time collection

* [pull](glossary.md#pull) for continuous collection

## Transaction atomicity and partial writes

Percona Binary Log Server never writes partial transactions to storage. The server commits data to disk or to object storage only at [transaction boundary](glossary.md#transaction-boundary) points. As a result, each stored binlog file contains transactions that are complete up to the last commit, or the file ends before the next transaction begins. This rule keeps storage consistent for both recovery and resume. In GTID-based replication, the complete transactions in each binlog file correspond to the `added_gtids` field in the file's [companion metadata](#metadata-json-schema).

How partial writes are prevented:

* The server parses transaction boundaries in the binlog stream. The server uses GTID log events (`transaction_length` field values in particular). A flush happens only after a complete transaction has arrived.

* When `replication.verify_checksum` is enabled, the server verifies binlog event checksums before writing. The source controls the algorithm. The `binlog_checksum` variable defaults to `CRC32`; set the variable to `NONE` to disable checksums. The server verifies events with the same algorithm that the source uses. The application accepts only the two algorithms that the source exposes: `CRC32` and `NONE`. Before switching into replication, the client sets `@source_binlog_checksum` and `@master_binlog_checksum` to match `verify_checksum`. See `easymysql/connection.cpp` in [Percona-Lab/percona-binlog-server](https://github.com/Percona-Lab/percona-binlog-server). Verification detects corruption early and prevents the server from storing bad data.

* This public reference does not describe every implementation detail, such as temporary files and write-ahead buffers. The guarantee is that the state visible on storage is always transaction-consistent. No partial transaction remains in a binlog file.

If the process is killed mid-stream, for example with `kill -9`, the last visible data on storage ends at the last flushed transaction boundary. Any in-progress transaction is discarded. The next run resumes from that safe position.

## Where the resume position is stored

The server keeps no local database. The server uses no SQLite database and no hidden state file. All information that defines the resume position lives in the backend that you configure (a local directory or S3). This design provides a single source of truth. The backend holds the binlog data, the metadata that describes the resume position, and the search indexes.

Where each piece lives (see `storage.hpp` / `storage.cpp` in [Percona-Lab/percona-binlog-server](https://github.com/Percona-Lab/percona-binlog-server)):

* Top-level replication mode. A single `metadata.json` file at the storage root records the replication mode (`position` or `gtid`). The server loads `metadata.json` first when storage is not empty.

* List of binlog files. A single `binlog.index` file at the root lists the binlog file paths in order, one per line (for example, `./binlog.000001`). Lines always start with `./` and no subdirectories are allowed. The last line names the current file. The server uses the full list for validation.

* Per-file metadata (resume position and search index). Each binlog file has a companion `.json` file. For example, `binlog.000001` has the companion file `binlog.000001.json`. The companion file holds the following fields: `version`, `size`, `previous_gtids`, `added_gtids`, `min_timestamp`, `max_timestamp`, and `last_sequence_number`. The `size` field is the flushed size in bytes and marks the byte where the next event would be written. In position-based replication mode, the resume position is the pair `(current binlog file name, byte position)`. The server reads the file name from the last line of `binlog.index`. The server reads the byte position from the `size` field of the companion JSON file. In GTID-based replication mode, the resume position is the GTID set `previous_gtids ∪ added_gtids`. The set is computed from the most recent file's companion JSON. The `size` field is not used for resume in this mode.

All of these objects pass through the same backend abstraction (`put_object` and `get_object`). On a file backend, the objects are plain files under `storage.uri`, such as `metadata.json`, `binlog.index`, `binlog.000001`, and `binlog.000001.json`. On an S3 or S3-compatible backend, the objects are stored under the same bucket and prefix as the binlog files. No state is kept only on the local host. With an S3 backend, the resume position is stored in S3.

If the local server's SSD fails, a file backend loses both the state and the binlogs, unless you have another copy. An S3 backend keeps all data in the bucket. Configure a new instance with the same `storage.uri`. The new instance loads `metadata.json`, `binlog.index`, and every `*.json` file from S3, and then resumes from the saved position. You can rebuild the state from the S3 metadata and the binlog objects alone. You do not need a local SSD.

## Metadata files (JSON schema and how to use them)

Percona Binary Log Server keeps one JSON metadata file for each stored binlog. The metadata file uses the binlog file name plus a `.json` extension, for example `binlog.000001.json`. The metadata files record the contents of each binlog. As a result, search commands and resume logic do not need to scan the binary data.

### Metadata JSON schema

Each metadata file describes one binlog file. The binlog file name is encoded in the metadata file name itself (for example, `binlog.000001.json` describes `binlog.000001`) and is not stored as a JSON field. Percona Binary Log Server writes every field during normal operation. Operators read these files but do not modify the contents. The fields are:

* `version`: schema version of the metadata file (currently `1`)

* `size`: current size of the binlog file in bytes (the byte position used for resume in position-based replication mode; not used for resume in GTID mode)

* `min_timestamp`: earliest event timestamp in the file (ISO format)

* `max_timestamp`: latest event timestamp in the file (ISO format)

* `previous_gtids`: GTID set that was already present at the start of the binlog file (empty when not using GTID mode). For the first stored file, the field is normally empty. If the field is non-empty, the source MySQL had a non-empty `@@gtid_purged` at the time Percona Binary Log Server started. The `previous_gtids` value then reflects that purged set.

* `added_gtids`: GTID set added by events in the binlog file (empty when not using GTID mode)

* `last_sequence_number`: the `sequence_number` value of the last GTID-class event (`GTID_LOG`, `ANONYMOUS_GTID_LOG`, or `GTID_TAGGED_LOG`) written to this binlog file. The field is used internally to resume `replication.rewrite` correctly after restart, so that rewritten `sequence_number` and `last_committed` values stay monotonic across the restart boundary. The value is `0` when no qualifying GTID-class event has been written yet, or when storage was not created in GTID mode. The field is present in the on-disk `binlog.NNNNNN.json` file only; the `search_by_timestamp` and `search_by_gtid_set` JSON output does not expose it.

A non-empty `previous_gtids` on the first stored file means Percona Binary Log Server started after some events had been purged from the source. Those events are not in the archive. Point-in-time recovery from this archive cannot cover GTIDs that fall inside the first file's `previous_gtids`. To eliminate the gap, start Percona Binary Log Server before the source's `@@gtid_purged` advances past what you need to recover from. Alternatively, capture the purged window with a separate logical or physical backup.

The `search_by_timestamp` and `search_by_gtid_set` JSON output reuses these per-file fields (except `version` and `last_sequence_number`) but also adds two fields that the on-disk file does not contain:

* `name`: binlog file name (for example, `binlog.000001`)

* `uri`: full storage URI of the binlog file (for example, `file:///var/lib/binlog-server/data/binlog.000001` or `s3://bucket/prefix/binlog.000001`)

The search command output also wraps the per-file entries in a top-level object that carries its own `version`, a `status`, and a `result` array. See [Search, list, and purge response format](#search-list-and-purge-response-format).

Both the per-file metadata on disk (for example, `binlog.000001.json`) and the search command JSON output use the key `previous_gtids`. Search commands and resume logic need the timestamp and GTID information to select the relevant files for a given time or GTID set. The two search commands select files differently:

* `search_by_timestamp` walks binlog records in order from the oldest and returns every record up to and including the last one whose `min_timestamp` is less than or equal to the requested timestamp. As soon as it sees a record whose `min_timestamp` is greater than the requested timestamp, it stops. The result is therefore the first N records of the binlog metadata list, not a minimal cover. If even the oldest file's `min_timestamp` is greater than the requested timestamp, the command returns an error (`Timestamp is too old`).

* `search_by_gtid_set` returns a *minimal cover*. The command iterates binlog records in order. The command skips any record whose `added_gtids` does not intersect the still-uncovered GTID set. The command includes only the files that contribute to covering the requested set. The command stops as soon as the set is fully covered. The command returns an error (`The specified GTID set cannot be covered`) if the set cannot be covered. A common cause is that part of the requested set falls inside the first stored file's `previous_gtids`. See the preceding note for details.

### Using the metadata when you only have the files

If the server process is gone, but the binlog files and metadata files still exist on local disk or in S3, you can still use the storage. Your options are:

* Configure another Percona Binary Log Server instance with the same `storage.uri` and `storage.backend`. A subsequent run resumes from the position recorded in storage. The server reads the existing metadata for the last position and does not re-download data that the server already has.

* Run `search_by_timestamp` or `search_by_gtid_set` with a configuration that targets the same URI. The commands read the metadata files and return the binlog files that match your timestamp or GTID set without scanning the raw binlog data. `search_by_timestamp` returns the first N metadata records of files from the oldest up to the requested time. `search_by_gtid_set` returns the minimal cover for the requested GTID set. See [Metadata JSON schema](#metadata-json-schema) for the selection rules.

* For point-in-time recovery, run `search_by_timestamp` to get the files that cover the target time. Then pass those files, together with a full backup, to your server recovery procedure. For GTID-based recovery, use `search_by_gtid_set` instead.

The metadata files are the index that search and resume use. Keep the metadata files together with the binlogs. Without the metadata files, you would have to scan the binlogs manually to find either the right files or the resume position.

## Resume behavior

A later run continues from the position that the previous run saved, in every operation mode. The server reads that position from the storage backend. In position-based replication mode (`replication.mode: position`), the server reads the last binlog file name from `binlog.index`. The server reads the flushed byte position from the `size` field of the companion `.json` file. The server sends both values to the source. In GTID-based replication mode (`replication.mode: gtid`), the server computes the union `previous_gtids ∪ added_gtids` from the most recent binlog metadata file. The server sends this GTID set to the source. The GTID set indicates what Percona Binary Log Server already has. The `size` field is not used for resume in this mode. For details, see [Where the resume position is stored](#where-the-resume-position-is-stored). The server does not need manual bookkeeping, a local database, or hidden local state.

When `replication.rewrite` is enabled, the server also restores `last_sequence_number` from the most recent binlog metadata file on restart. The restored value seeds the rewrite logic so that `sequence_number` and `last_committed` in subsequent rewritten GTID-class events remain monotonic across the restart, which keeps the rewritten archive consumable by parallel-replication replicas.

## Graceful shutdown

Percona Binary Log Server supports graceful shutdown for `fetch` and `pull`.

Supported POSIX signals:

* `SIGINT`

* `SIGTERM`

Examples:

```bash
Ctrl+C
kill <pid>
```

Graceful shutdown keeps storage consistent. The server flushes buffered data and commits at a transaction boundary before the process exits.

`kill -9` does not provide this safety. A forced stop can leave buffered data unwritten and can lose recent progress. Under systemd, set `TimeoutStopSec` long enough for a graceful flush. Use at least `connection.read_timeout` plus a few seconds. For example, set `TimeoutStopSec` to 90 or 120 seconds when `read_timeout` is 60. Otherwise, systemd may send `SIGKILL` before the process finishes flushing.

`libmysqlclient` uses synchronous calls. As a result, the response to a stop signal can wait for:

* up to `connection.read_timeout` seconds in the read call.

* up to one additional second in the idle sleep.

## Network failure and reconnect behavior

The server's response to a network failure or an unreachable source depends on the operation mode. The response also depends on where the failure occurs. The behavior described in this section comes directly from the implementation. See [Percona-Lab/percona-binlog-server](https://github.com/Percona-Lab/percona-binlog-server).

Fetch mode. Any error stops the process. Errors include: a failed TCP connect, a failure to switch the session into replication mode, a connection loss or other error during the read, and non-network errors such as a full disk. The process exits, and storage stays consistent at the last flushed transaction boundary. Fetch mode never retries or reconnects within a single run. After a transient failure, you can re-run the tool in `fetch` mode against the same storage. The re-run resumes from the last flushed transaction.

Pull mode: failure during connect or replication switch. Two failures fall into this category:

* The server cannot open a TCP connection to the source.

* The connection opens, but the session cannot switch to replication mode (position or GTID).

In both cases, the application catches the client-library error. The application logs the error (for example, "unable to establish connection to mysql server" or "unable to switch to replication") and returns. The main pull loop then sleeps for `replication.idle_time` seconds and tries again. The delay is fixed. The retry loop applies no exponential backoff. During a partition or a source outage, the process retries at the same interval until the source returns.

Pull mode: failure while reading binlog events. The application reads events through the client library's binlog fetch API. If the fetch call fails, the server checks the error code. The server handles `CR_SERVER_LOST` (connection dropped) cleanly. The fetch call returns false, the current event buffer flushes at a transaction boundary, discards all data from the last partially downloaded transaction, and the read loop exits. Control returns to the main pull loop, which sleeps for `idle_time` seconds and then reconnects. This path is the same path that runs after a normal "no more events" timeout. The server then resumes from the last position in metadata. Any other error code during fetch, for example a protocol error or a server error, raises an exception that the read loop does not catch. As a result, the process exits and does not reconnect automatically.

Pull mode: non-recoverable errors. Any error that is not in the "retry after idle" class causes the process to exit. Non-recoverable errors include: an out-of-disk condition, a storage write failure, and any server-side error during read other than `CR_SERVER_LOST`. A new run, or a restart by a process manager, resumes from the last position in storage.

### Best practice: `idle_time`

In pull mode, `replication.idle_time` is the only delay between reconnect attempts. The retry loop applies no backoff. During a partition or a source outage, the process retries every `idle_time` seconds. A short value (the default is 10) produces a high rate of connection attempts. In cloud environments, a high rate of connection attempts can trigger rate limiting, connection caps, or circuit breakers on the source or on intermediate infrastructure such as load balancers, proxies, and security controls. The client may also be temporarily blocked. Choose an `idle_time` value that is high enough to avoid overloading the source during an outage. A typical value is 30 to 60 seconds or more when the source sits behind cloud infrastructure or rate limiters. The 10-second default is often too aggressive for production. Consider 30 seconds or 60 seconds unless you need faster retries for a specific reason. Monitor and alert on repeated reconnect cycles or process exits so that you can respond to source or network issues.

## Failover and topology awareness

Percona Binary Log Server has **no built-in failover handling, no topology awareness, and no node-role inspection**. The tool reconnects to whatever `connection.host`/`connection.port` (or `connection.dns_srv_name`) resolves to at the moment of the next retry, opens a replication session, and starts pulling whatever binlog stream that node is publishing. Operating the tool safely behind a failover-capable topology is therefore the operator's responsibility.

What the tool does and does not do at reconnect time:

* It does **not** issue `SELECT @@read_only`, `SELECT @@super_read_only`, `SHOW REPLICA STATUS`, or any other check to decide whether the node is a current primary, a current replica, or in read-only state.

* It does **not** integrate with Orchestrator, Patroni, MHA, ProxySQL, the Percona Operator's election logic, or any other topology manager.

* It does follow DNS resolution and virtual-IP swaps transparently, because the connect call re-resolves the host on every retry. A DNS or VIP swap performed by your topology manager will route the next retry to the new primary, but only if the resolved target is in fact the new primary.

* It does retry forever at a fixed `replication.idle_time` interval (see [Network failure and reconnect behavior](#network-failure-and-reconnect-behavior)).

Implications by replication mode:

* `replication.mode: gtid`. The stored cursor is a GTID set. After a failover, resuming against the promoted primary works correctly **as long as** that primary has executed every GTID up to the stored set and continues from there. However, GTID mode alone is not sufficient when Percona Binary Log Server can reconnect to a different node in the topology (a different cluster member, a promoted replica, or any source that does not share the previous node's binlog file sequence). By default, Percona Binary Log Server mirrors the source's binlog file names and rotation layout, and each node maintains its own. Without `replication.rewrite`, the stored archive's file names and rotation boundaries will jump or overlap across the failover. Enable `replication.rewrite` so that Percona Binary Log Server uses a server-side file name (`rewrite.base_file_name`) and rotation threshold (`rewrite.file_size`) instead. The stored archive then stays coherent regardless of the node the server reads from. For the event-level behavior the rewrite enables (file boundary events, offset rewriting, logical-clock fields, tagged-GTID transaction length, and checksum recalculation), see [Binlog rewriting internals](#binlog-rewriting-internals). Before enabling `replication.rewrite`, confirm that every source the failover topology can route to runs with `@@global.binlog_checksum = CRC32` — see [Source-side checksum requirement](#source-side-checksum-requirement). **The safe configuration for production behind a failover-capable topology is `replication.mode: gtid` together with `replication.rewrite`.**

* `replication.mode: position`. The stored cursor is `(binlog file name, byte position)` in the source's binlog namespace. Binlog file names and offsets are **not** portable across nodes after a failover (each node maintains its own binlog file sequence). Resuming against the wrong node can fail outright (the file does not exist on the new node), and in rare layouts can read data that does not belong to your historical stream. Do not rely on position mode behind a failover topology.

Recommendations:

1. Use `replication.mode: gtid` whenever the source can fail over. Also enable `replication.rewrite`. The `rewrite` setting decouples the stored archive's file layout from any individual node's binlog naming. Reserve `replication.mode: position` for single, never-promoted sources.

2. Point `connection.host` (or `connection.dns_srv_name`) at a **write-tracking endpoint**, never at a fixed node IP. Examples:

    * A proxy with health checks that always forwards to the current primary (ProxySQL, HAProxy with a custom check, MySQL Router).
    * A DNS SRV record managed by your topology manager.
    * The operator-managed primary `Service` in Kubernetes (for example, the Percona Operator's `*-haproxy` or `*-mysql-primary` service), not a per-pod service.

3. Ensure `log_bin=ON` and `log_replica_updates=ON` on **every node that could be promoted**, not only on the current primary. Without `log_replica_updates`, a promoted replica's binlog will not contain writes that originated on other nodes, so any archive you keep collecting after the failover will be incomplete.

4. Alert on the absence of stored progress, not on TCP reachability. The tool can reconnect successfully to a stale or read-only node and appear "healthy" while no new transactions are being archived. Use the `max_timestamp` of the latest stored binlog (or the staleness alert in [Setting an alert when "binlog lag" exceeds a threshold](operations.md#setting-an-alert-when-binlog-lag-exceeds-a-threshold)) as the source of truth for liveness.

Behavior described in this section comes directly from the implementation. See [Percona-Lab/percona-binlog-server](https://github.com/Percona-Lab/percona-binlog-server) for the connection and pull loop in `src/app.cpp` and `src/easymysql/connection.cpp`.

## Binlog rewriting internals

When [`replication.rewrite`](configuration-reference.md#replicationrewrite-optional) is enabled, Percona Binary Log Server takes over several event-level decisions. The server still consumes the source's binlog stream. The server rewrites events to fit its own file layout and to preserve parallel-replication ordering.

### Generated file boundary events

The server generates its own `ROTATE`, `FORMAT_DESCRIPTION`, and `PREVIOUS_GTIDS_LOG` events at file boundaries. The server discards the corresponding events from the source. Each rewritten file begins with a server-generated `FORMAT_DESCRIPTION`. The file contains a server-generated `PREVIOUS_GTIDS_LOG` that reflects the cumulative GTID set. The file ends with a server-generated `ROTATE` event. The `ROTATE` event names the next rewritten file based on `rewrite.base_file_name`. The server ignores all source-side `ROTATE` events.

### Common-header offset rewriting

The server splits files on its own rules: `rewrite.file_size` and `rewrite.base_file_name`. The source's `ROTATE` events no longer determine file boundaries. The byte offsets that the source attaches to each event no longer match the rewritten file. The server updates the `next_event_position` field in the common header of every incoming event. The new value reflects the event's position in the rewritten file.

### Logical-clock rewriting

The server rewrites the `sequence_number` and `last_committed` fields inside `GTID_LOG`, `ANONYMOUS_GTID_LOG`, and `GTID_TAGGED_LOG` events. The rewritten values satisfy two invariants:

* `sequence_number` values are monotonically increasing within a single rewritten file.

* `last_committed < sequence_number` for every rewritten event.

On restart, the server seeds the values from [`last_sequence_number`](#metadata-json-schema) in the most recent binlog metadata file. The invariants therefore hold across the restart boundary.

### Variable-length encoding for tagged GTID events

`GTID_TAGGED_LOG` uses a variable-length encoding for its body. Changing `sequence_number` or `last_committed` can therefore change the encoded size of the event. When that happens, the server also updates the `transaction_length` field in the event body. The updated value matches the actual on-disk event size.

### Recalculating checksum

For every generated or modified event, Percona Binary Log Server calculates or recalculates the CRC32 checksum. The server writes the checksum to the event footer.

### Source-side checksum requirement

`replication.rewrite` requires that every source binlog file Percona Binary Log Server reads was generated with `@@global.binlog_checksum = CRC32`. When `replication.rewrite` is enabled, Percona Binary Log Server inspects the `FORMAT_DESCRIPTION` event at the start of each source binlog file. If the file was generated on a source with `binlog_checksum = NONE`, the server logs `rewrite is supported in gtid replication mode only when all events received from the MySQL server have checksums` and exits with a non-zero status code.

The check fires per source binlog file. A history that mixes checksummed and unchecksummed files (for example, the operator switched `@@global.binlog_checksum` from `NONE` to `CRC32` between two source binlog files) is rejected the moment Percona Binary Log Server reaches the first no-checksum file. To avoid the failure mode, set `@@global.binlog_checksum = CRC32` and run `FLUSH BINARY LOGS` on the source before pointing Percona Binary Log Server at the source.

The constraint exists because the rewrite recomputes `transaction_length` based on the actual on-disk size of events. Adding a CRC32 footer to events that did not have one — or removing one from events that did — would change the encoded size of every event in the transaction. The rewrite stage does not buffer whole transactions before flush, so the stage cannot retroactively fix `transaction_length` if the encoded size changes within a transaction. Requiring CRC32 across the entire stream sidesteps the problem.

## Impact on the primary, memory footprint, and internal flow

DBAs want to know whether a slow or failing consumer can stall the primary. An example of a slow consumer is an S3 region that is temporarily degraded. The description in this section comes from the implementation. See [Percona-Lab/percona-binlog-server](https://github.com/Percona-Lab/percona-binlog-server).

Can the tool stall the primary? In pull mode, the client uses `libmysqlclient` in blocking replication mode (`BINLOG_DUMP_NON_BLOCK` is not set). A single thread runs a tight loop:

1. The thread performs a blocking read of one binlog event from the source.
2. The thread appends the event to an in-memory event buffer.
3. When a checkpoint condition is met, the thread flushes the buffer synchronously to the backend. The thread waits for the file write or S3 write to complete.

If the backend is slow (high S3 latency, an unreliable network to the storage region, or rate limiting), the thread spends more time in the write path and does not call fetch again. The client library stops draining the TCP socket, the receive buffer fills, and the primary's binlog dump thread blocks on the next send. So the answer is yes: a slow or stalled consumer can block the primary's dump thread. The primary as a whole is not stalled. Other clients and replicas continue to work. Only the dump thread that serves Percona Binary Log Server waits until the consumer reads again. In fetch mode, the client runs in non-blocking replication and reads until no events remain. Because fetch is typically a one-time operation, long-term backpressure on the primary is rarely a concern in fetch mode.

Memory footprint. The server keeps event data in a single in-memory `std::vector` until a flush. The buffer is reserved at 16,384 bytes (see `default_event_buffer_size_in_bytes` in the source). The implementation defines no documented hard cap. Flushes happen only at transaction boundaries, and only when both of these conditions are true:

1. At least one full transaction is present in the buffer.
2. One of these events occurs: the data that is ready to flush reaches `checkpoint_size`; the time since the last checkpoint reaches `checkpoint_interval`; or an end-of-file marker (`ROTATE` or `STOP`) arrives.

As a result, the buffer grows until the next transaction boundary and the next checkpoint. In the worst case, one very large transaction, such as a large batch insert, remains in the buffer until the transaction commits and a checkpoint condition triggers a flush. The process also depends on client-library buffers, for example the buffers that `mysql_binlog_fetch` uses. The library and the server size these buffers. Size your memory budget for your largest transaction between checkpoints, plus the base process and client-library overhead. `checkpoint_size` and `checkpoint_interval` directly control how often the buffer is flushed.

Internal flow and queueing. The server does not use a separate producer thread and consumer thread. One thread reads from the source and writes to storage. The flow is as follows. The thread performs a blocking read of one event, appends the event to the event buffer, and then, at a transaction boundary, flushes the buffer if a checkpoint condition is met. The flush is a blocking operation. The architecture uses no unbounded queue between read and write. The only buffers are the event buffer described under Memory footprint and the TCP receive buffer on the source connection. This design produces natural backpressure. When the backend slows, the thread blocks in the flush, stops reading, and stops draining the socket. As a result, the primary's send call can also block. This chain is the mechanism that stalls the primary's dump thread during storage slowdowns. If you cannot tolerate this behavior, run Binary Log Server where storage is fast and reliable. Use local disk or a nearby S3 region. Otherwise, accept that the dump thread on the primary can block during storage slowdowns.

## list mode

[`list`](command-reference.md#list) opens storage in querying-only mode. The mode reads `binlog.index` and the per-file `.json` metadata sidecars. The mode does not write to storage and does not lock storage against other processes. Running `list` against a storage that a `fetch` or `pull` process is currently writing is therefore safe; the snapshot reflects whichever entries `binlog.index` contained at the moment `list` opened the file.

`list` returns metadata for every stored binlog file in the order recorded in `binlog.index`, which matches the chronological order in which Percona Binary Log Server wrote the files. The output schema is the same one that `search_by_timestamp` and `search_by_gtid_set` use — see [Search, list, and purge response format](#search-list-and-purge-response-format).

Empty-storage behavior is the operational distinction between `list` and the search commands. `list` returns `status: success` with an empty `result` array. The two search commands raise `Binlog storage is empty` instead. Use `list` to distinguish a freshly initialized storage (the empty-result case) from a corrupted one (which fails to open and produces `status: error`).

## purge_binlogs mode

[`purge_binlogs`](command-reference.md#purge_binlogs) deletes a contiguous prefix of stored binlog files (and each file's `.json` metadata sidecar) from the storage backend. The target argument is a stored binlog file name. Every file with sequence number at or below the target is removed.

### Algorithm

The mode opens storage in purging mode. The mode runs three steps:

1. **Compute the victim prefix.** The mode validates the target name. The mode raises `status: error` and exits without touching storage if the target name is malformed (`binlog composite name is too short`), the storage is empty (`cannot purge: binlog storage is empty`), the target's base name does not match the stored files (`cannot purge: target binlog name has a different base name than the binlog records in the storage`), the target is not in the storage (`cannot purge: target binlog name is not present in the storage`), or the target is the current tail file (`cannot purge: target is the current tail binlog file; at least one binlog file must remain in the storage to preserve the resume position`).

2. **Rewrite `binlog.index`.** The mode writes a new `binlog.index` that contains only the surviving files. The backend writes the new file atomically (write-temp-and-rename for the file backend, single PUT for S3). The mode considers the purge committed once `binlog.index` is rewritten. The resume position now points at the first surviving file.

3. **Delete payloads and metadata.** The mode removes the payload (`binlog.NNNNNN`) and metadata sidecar (`binlog.NNNNNN.json`) for each victim in a single batch through the backend's `remove_objects` operation. The batch runs the backend's durability barrier once (one `fsync` on the file backend, no-op on S3) instead of per-file. A failure in this step is **not** propagated as an error to the caller, because the index has already been committed; the caller would otherwise believe that the purge itself failed and retry it on a state that no longer matches.

### Tail protection

`purge_binlogs` refuses to delete the current tail file (the most recent `binlog.NNNNNN` in `binlog.index`). Emptying storage would erase the resume position. The next `fetch` or `pull` would have nothing to anchor to and would re-stream from the source's earliest retained binlog. Operators who want to fully clear an archive should use the storage-level deletion path (delete the directory, drop the bucket prefix, or apply an S3 lifecycle policy) when Percona Binary Log Server is stopped, not `purge_binlogs`.

### Failure modes and recovery

`purge_binlogs` produces one of three response statuses:

* `status: "success"` — all three steps completed. Storage is consistent. `result` lists the deleted files.

* `status: "error"` — the mode raised before step 2 (the index commit). Storage is unchanged. The error message identifies the cause; see step 1 above for the enumerated cases.

* `status: "warning"` — step 2 succeeded, step 3 partially or fully failed. Storage now lists the deleted files in `result`. The underlying backend error appears in `message`. The storage is in a partial state: `binlog.index` no longer references the leftover files, but their payload or metadata objects still exist on disk or in the bucket. Percona Binary Log Server's startup validators detect that state on the next `fetch`, `pull`, `list`, `search_by_timestamp`, `search_by_gtid_set`, or `purge_binlogs` run and refuse to open the storage. Recovery is manual: delete the leftover files (named in `result`, with the corresponding `.json` sidecars) and restart Percona Binary Log Server.

### Concurrency requirements

Run `purge_binlogs` only when no `fetch` or `pull` process is writing to the same storage. The mode rewrites `binlog.index` from the current set of stored files, and a concurrent writer against the same storage rewrites the same file when it rotates a new binlog. Without a cross-process lock, the two writers race; the loser's update is lost, and the archive is left inconsistent.

The constraint is scoped to a single storage. A storage is identified by its `storage.uri` — an absolute filesystem path for the `file` backend, or the bucket-and-prefix pair for the `s3` backend. A separate Percona Binary Log Server instance that writes to a different `storage.uri` is unaffected by `purge_binlogs` against this storage and can keep running, even on the same host. See [Safe-deletion rules](operations.md#safe-deletion-rules) for the operational rule.

## Search, list, and purge response format

The `search_by_timestamp`, `search_by_gtid_set`, [`list`](#list-mode), and [`purge_binlogs`](#purge_binlogs-mode) commands all emit JSON on stdout. The JSON wraps a top-level object with one of three `status` values:

* `status: "success"` — the command completed normally. `result` contains the file metadata returned by the command (an empty array is permitted for `list` against an empty storage).

* `status: "error"` — the command failed before any storage change. `message` carries the error text. `result` is absent or empty.

* `status: "warning"` — produced only by `purge_binlogs`. Step 2 (the index rewrite) succeeded, but step 3 (the payload-and-metadata deletion) partially or fully failed. `result` lists the metadata of every file the command tried to delete. `message` carries the underlying backend error. Storage is in a partial state — see [`purge_binlogs` failure modes and recovery](#failure-modes-and-recovery).

A success or warning result usually contains a list of binlog file entries. Each entry uses the same schema as the [metadata JSON schema](#metadata-json-schema). Each entry contains the following fields:

* `name`

* `size`

* `uri`

* `min_timestamp`

* `max_timestamp`

* `previous_gtids`

* `added_gtids`
