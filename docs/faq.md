# Frequently asked questions

Common questions about Percona Binary Log Server.

## What is Percona Binary Log Server?

Percona Binary Log Server is a CLI tool that attaches to a MySQL or MySQL-compatible server as a replication client, streams [binary log](glossary.md#binary-log) events, and writes them to local disk or S3-compatible storage. After an interruption the tool reconnects and resumes from the last saved position. The tool is built for [point-in-time recovery](glossary.md#point-in-time-recovery) (PITR) and for search by timestamp or [GTID](glossary.md#gtid) set. See [Abbreviations](glossary.md#abbreviations) in the [Glossary](glossary.md).

## When should I use fetch instead of pull?

Use `fetch` for a one-time or on-demand copy. `fetch` reads every event available on the source, writes the events to storage, and then exits. Use `pull` for continuous collection. `pull` waits for incoming events and reconnects after timeouts or network errors. `pull` stops only when you stop the process or when a non-recoverable error occurs. See [Command Reference](command-reference.md).

## Can a slow storage backend (for example, S3 in another region) stall my primary?

Yes. In `pull` mode, Percona Binary Log Server reads from the source and writes to storage on a single stream. If the backend is slow because of high latency, throttling, or a distant region, the server cannot read the binlog events as fast as the source produces them. The replication connection then fills up. The dump thread on the source blocks when it tries to send the next event. Other clients and other replicas are usually not affected.

### Details

Memory use can grow when large transactions occur between checkpoints. For an explanation of how single-threaded reads, buffering, and flushes interact with the primary, including socket backpressure, see [Impact on the primary, memory footprint, and internal flow](operational-behavior-reference.md#impact-on-the-primary-memory-footprint-and-internal-flow) in Core behavior.

## What happens when the network fails or the source server goes down?

In `fetch` mode, any error stops the process. This includes a dropped connection during a read. Storage stays consistent at the last flushed transaction. The tool does not retry or reconnect. However, after a network error you can re-run the tool in `fetch` mode and resume from the last flushed transaction in storage.

In `pull` mode, transient failures trigger a reconnect. The tool resumes from the saved position in storage. Non-recoverable errors, such as an out-of-disk condition or a storage write failure, cause the process to exit.

### Details

In `pull` mode, the behavior depends on where the failure occurs. Two cases cause the process to sleep for `replication.idle_time` seconds and then reconnect. The first is a failure during connect or during the start of the replication session. Examples include an unreachable source or a replication user that lacks `REPLICATION SLAVE`. The second is a `CR_SERVER_LOST` error during a read: the connection drops once events are flowing. The tool discards any partially-downloaded transaction and re-fetches the transaction on reconnect. After the reconnect, the tool resumes from the last position in storage. Any other server error during a read causes the process to exit without an automatic reconnect. See [Network failure and reconnect behavior](operational-behavior-reference.md#network-failure-and-reconnect-behavior) in Core behavior.

## What is the difference between position and GTID mode?

Position mode tracks progress by binlog file name and byte offset. The stored files match the source's binlog layout. GTID mode tracks progress by GTID set. The stored files can use different file names or layouts. GTID mode supports both `search_by_timestamp` and `search_by_gtid_set`. Position mode does not support `search_by_gtid_set`. See [`replication.mode`](configuration-reference.md#replication).

## What does replication.rewrite require from the MySQL source?

`replication.rewrite` is GTID-mode only and also requires that every source binlog file was generated with `@@global.binlog_checksum = CRC32` on the source. If Percona Binary Log Server reads a source binlog file generated with `binlog_checksum = NONE` while `replication.rewrite` is enabled, the server logs `rewrite is supported in gtid replication mode only when all events received from the MySQL server have checksums` and exits with a non-zero status code.

Set `@@global.binlog_checksum = CRC32` on the source and rotate the source binlogs (`FLUSH BINARY LOGS`) before starting Percona Binary Log Server. Make `binlog_checksum = CRC32` part of the source's persistent configuration so that the setting survives a server restart, and verify that no later binlog file is generated with `binlog_checksum = NONE`. For the reason behind the constraint, see [Source-side checksum requirement](operational-behavior-reference.md#source-side-checksum-requirement) in Core behavior.

## Can I run Percona Binary Log Server from Docker?

Yes. The Docker image gives you a ready-to-run deployment. Build from source when you need local compilation, debugging, or code changes. See [Install Percona Binary Log Server](install.md).

## Where are the binlog files stored?

You set storage in the `storage` section of the configuration file. The `backend` key accepts `file` for a local directory or `s3` for Amazon S3 or S3-compatible storage. The `uri` key sets the exact path, or the bucket and prefix. See [Configuration Reference](configuration-reference.md) and [Storage Reference](storage-reference.md).

## Where is the resume position stored? Can I reconstruct from S3 alone if I lose the local server?

The server does not use SQLite or a local-only database. The resume state is stored in the same backend that you configure. The resume position is the last binlog file name in `binlog.index`, plus the `size` field from that file's `.json` metadata.

### What is written for each backend

For a file backend, the directory in `storage.uri` holds these files: `metadata.json` (the replication mode), `binlog.index` (one binlog file name per line), and one pair of files per binlog — for example, `binlog.000001` (the binlog data) and `binlog.000001.json` (the metadata sidecar holding the flushed size, GTID sets in GTID mode, timestamps, and `last_sequence_number` when `replication.rewrite` is enabled). An S3 backend stores the same objects under the bucket and prefix.

If you lose the host that runs Percona Binary Log Server, recovery depends on the backend:

* **File backend.** If the archive directory in `storage.uri` was on the failed host's disk, the archive is gone. Recovery requires an external backup; Percona Binary Log Server itself does not replicate file-backend data anywhere.

* **S3 backend.** The archive lives in the S3 bucket, not on the failed host. Configure a new Percona Binary Log Server instance with the same `storage.uri`. The new instance loads `metadata.json`, `binlog.index`, and the per-binlog `.json` sidecars from S3, then resumes from the last saved position.

See [Where the resume position is stored](operational-behavior-reference.md#where-the-resume-position-is-stored) in Core behavior.

## How do I resume after stopping the server?

A new run continues from the position where the previous run stopped. You do not need any extra steps. Stop the process gracefully with Ctrl+C or `kill <pid>`, so that buffered data is flushed. `kill -9` can leave recent data unwritten.

## What privilege does the connection user need?

The account that you set under `connection` needs the `REPLICATION SLAVE` privilege. This privilege allows the user to connect as a replication client and to read binlog events.

## Do I need log_replica_updates when connecting to a PXC node?

Yes. When the source is a Percona XtraDB Cluster (PXC) node, the primary must have `log_replica_updates` set to `ON`. When `log_replica_updates` is `OFF`, the node's binlog records only writes that started on that node. As a result, Binary Log Server captures only part of the cluster traffic. Any recovery or audit that is built on the archive loses the transactions that were applied from other nodes. See [Using with Percona Operators](use-with-operators.md#connecting-to-the-cluster) for the full requirement and for how to verify the setting.

## Why not use mysqlbinlog in a loop instead?

Percona Binary Log Server handles reconnection and resume for you. A stopped run continues from the last saved position. You do not need custom scripting. The server also writes directly to S3 or S3-compatible storage. The server respects transaction boundaries, so storage stays consistent. The server includes the `search_by_timestamp` and `search_by_gtid_set` commands: `search_by_timestamp` returns the first N metadata records of stored files from the oldest up to the requested time (based on `min_timestamp`), and `search_by_gtid_set` returns a minimal cover of stored files for a requested GTID set. A `mysqlbinlog` loop requires you to build reconnection, upload, and search logic yourself.

## Can I use localhost for the connection to the server?

No. When you require a TCP connection, use `127.0.0.1`, a real host name, or an IP address. The client library `libmysqlclient` often treats `localhost` as a request for a Unix socket connection.

## Is fs_buffer_directory required for S3 storage?

No. `fs_buffer_directory` is optional. When the backend is `s3` and you omit `fs_buffer_directory`, the server creates a UUID-named subdirectory under the OS temporary directory (`$TMPDIR`, or `/tmp` on Linux when unset). The auto-created directory is removed at clean shutdown. The path changes on every run. A `fs_buffer_directory` set explicitly is never deleted by the server. Set `fs_buffer_directory` explicitly in production so that the buffer lives in a stable, predictable, and disk-safe location, and so that any unfinished uploads remain available for diagnostics across restarts.

## Why does S3 storage upload more data than the binlog size?

S3 does not support append operations for existing objects. As a result, each checkpoint flush can re-upload the object. A small `checkpoint_size` or a short `checkpoint_interval` increases the total bytes transferred far above the final binlog size. Choose the checkpoint values with care. See [Storage Reference](storage-reference.md).

## What happens if my IAM role or S3 credentials expire?

The server does not manage credentials or IAM on your behalf. When the role or the credentials expire or are revoked, S3 writes fail. The server logs errors. The process may exit, depending on the error. Renew the credentials or the role and then restart the server. The server resumes from the last position that is recorded in the metadata. See [Operations](operations.md) for monitoring and alerting.

## How do I embed S3 credentials that contain special characters?

Percona Binary Log Server reads S3 credentials only from the userinfo portion of `storage.uri`. Any URI-reserved characters in the access key or secret must be percent-encoded before being embedded. The most common example is `/` (which appears frequently in AWS secret access keys) and must be written as `%2F`. Other reserved characters that need encoding when they occur: `+` as `%2B`, `=` as `%3D`, `@` as `%40`, and `:` as `%3A`. For the full URI grammar, see [Storage Reference](storage-reference.md#amazon-s3-uri-format).

## What if the S3 bucket or endpoint hits rate limits?

The server does not run its own S3 retry loop. The AWS SDK retries some throttling errors automatically. You should still monitor failures. You can also increase the checkpoint values to reduce the upload frequency, or you can raise your endpoint's limits. See [Storage Reference](storage-reference.md).

## How do I migrate from a standard replica to Percona Binary Log Server?

Percona Binary Log Server is not a direct replacement for a replica. The tool acts as a replication client that reads binlogs and writes them to storage. The tool does not apply events to a downstream database.

### Migration steps (archiving-only replica)

To replace an archive-only replica with Binary Log Server:

1. Stop or repurpose the existing replica.
2. Create a `REPLICATION SLAVE` account on the source.
3. Configure Binary Log Server to connect to the source and to write to your chosen storage.
4. Run `pull` for continuous collection, or run `fetch` for a one-time copy.

The server streams from the source and writes to local disk or to S3.

If you need read scaling or failover, choose a different tool. Percona Binary Log Server only archives binlogs.

## How do I use Percona Binary Log Server with the Percona Operator for MySQL (PS or PXC)?

Run Percona Binary Log Server as a separate Kubernetes workload that connects to the primary of your operator-managed cluster. Set `connection.host` to the primary's Kubernetes service, for example `cluster1-mysql-primary.namespace.svc.cluster.local`. Set `connection.port` to `3306`. Use an account that has the `REPLICATION SLAVE` privilege. Keep the password in a Secret and store the rest of the configuration in a ConfigMap. For storage, attach a PVC for the file backend, or use S3 with credentials embedded directly in `storage.uri` (the server does not consult the AWS default credential chain, so IRSA, instance profiles, or `AWS_*` environment variables have no effect). Source the S3 credentials from a Kubernetes `Secret` and render the full `storage.uri` at startup.

### Full operator guide

For the decision matrix, the PXC `log_replica_updates` requirement, the deployment steps, and the relationship between Binary Log Server and the operator's built-in PITR under [Percona Operator for MySQL (PS)](https://docs.percona.com/percona-operator-for-mysql/ps/) or [PXC](https://docs.percona.com/percona-operator-for-mysql/pxc/), see [Using Percona Binary Log Server With Percona Operators](use-with-operators.md).

## Can I use Percona Binary Log Server to feed a Snowflake pipe or another data warehouse?

The server writes raw binlog files to local disk or to S3. The server does not parse events into rows and does not send them to Snowflake, BigQuery, or any other warehouse. Treat the stored binlogs as input to a separate pipeline. For example, use a CDC tool or a custom job that reads the files from disk or from S3, parses the events, and loads the events into Snowflake. Percona Binary Log Server handles the first stage, which is the binlogs in S3. The rest of the pipeline runs in a separate system.

## How do I find which stored files to use for point-in-time recovery?

Call `search_by_timestamp` with the target time in ISO format. The command returns the first N metadata records of stored binlog files, from the oldest up to and including the last file whose `min_timestamp` is at or before that timestamp. If even the oldest file's `min_timestamp` is greater than your target, the command returns `Timestamp is too old`. Pass the returned files, together with a full backup, to your point-in-time recovery procedure. For GTID-based recovery, call `search_by_gtid_set` with the target GTID set. The command returns a minimal cover of files for those transactions, or `The specified GTID set cannot be covered` when the set is not fully present in storage. If the cover fails because the source had purged GTIDs before Percona Binary Log Server started, the archive does not contain the corresponding events — see [Metadata JSON schema](operational-behavior-reference.md#metadata-json-schema) in Core behavior.

## How do I know which documentation version I am viewing?

When the site is built with multiple versions, for example with the `mike` tool, a version switcher appears in the header. Choose the version that matches your deployment. Options and flags can change between versions. The version switcher keeps you on the documentation for the version that you run.

## Where can I get more help?

See [Get help from Percona](get-help.md) for community forums and support options. For configuration and command details, use the [Configuration Reference](configuration-reference.md), [Command Reference](command-reference.md), and [Glossary](glossary.md).
