# Frequently Asked Questions

Common questions about Percona Binary Log Server.

## What is Percona Binary Log Server?

Percona Binary Log Server is a command-line utility that connects to a MySQL server as a replication client, reads binary log events from the server, and writes those events to a local directory or to S3-compatible object storage. The server can reconnect after a stop and resume from the last saved position. The design supports point-in-time recovery and search by timestamp or GTID set.

## When should I use fetch instead of pull?

Use `fetch` when a one-time or on-demand copy of the current binary logs is enough. `fetch` reads all events available on the source, writes them to storage, then exits. Use `pull` when binary logs must be collected continuously. `pull` keeps running, waits for new events, reconnects after timeouts or network errors, and only stops when the process is stopped or a non-recoverable error occurs.

## Can a slow storage backend (for example, S3 in another region) stall my primary?

Yes. In pull mode the application uses blocking reads from the MySQL connection and synchronous writes to the storage backend. The main thread runs: fetch one event → append to an in-memory event buffer → when a checkpoint is reached at a transaction boundary, flush the buffer to storage (and block until the write completes). If storage is slow (high latency, flaky network, or rate limiting), the thread blocks in the flush and does not read the next event from MySQL. The MySQL client then does not drain the TCP socket, so the primary’s binlog dump thread for this client can block when sending. Other clients and replicas are unaffected, but the dump thread serving Percona Binary Log Server will block until the consumer reads again. Memory use is driven by an in-memory event buffer that has no documented hard cap; the buffer can grow up to the size of the largest transaction between checkpoints. See [Impact on the primary, memory footprint, and internal flow](operational-behavior-reference.md#impact-on-the-primary-memory-footprint-and-internal-flow) in Core behavior.

## What happens when the network fails or the source MySQL server goes down?

In fetch mode, any error (including connection failure or connection lost during read) terminates the process. Storage remains consistent at the last flushed transaction; there is no retry or reconnect.

In pull mode, behavior depends on where the failure occurs. If the server cannot connect or cannot switch the session to replication mode, the process logs the error, sleeps for `replication.idle_time` seconds, and tries again; the delay between attempts is always `idle_time` (no exponential backoff). If the connection is lost while reading events and the MySQL client reports `CR_SERVER_LOST`, the process flushes buffered data at a transaction boundary, then sleeps `idle_time` and reconnects, resuming from the last position in storage. If a different MySQL error occurs during read (for example, a protocol or server error), the process exits and does not reconnect automatically. Non-recoverable errors (out of disk, storage write failure) also cause exit. Full details and tuning guidance: [Network failure and reconnect behavior](operational-behavior-reference.md#network-failure-and-reconnect-behavior) in Core behavior.

## What is the difference between position and GTID mode?

In position mode, progress is tracked by binary log file name and byte position. Stored files match the source server’s binary log layout. In GTID mode, progress is tracked by GTID set; stored files may have different names or layout but contain the same transactions. Position mode does not support `search_by_gtid_set`. GTID mode supports both `search_by_timestamp` and `search_by_gtid_set`. Choose the mode that matches the source server and the search or recovery workflow you need.

## Can I run Percona Binary Log Server from Docker?

Yes. The latest version is available on Docker. Use Docker for a ready-to-run deployment. Use a source build when local compilation, debugging, or code changes are required. See [Install Percona Binary Log Server](install.md).

## Where are the binary log files stored?

Storage is set in the configuration file under the `storage` section. The `backend` can be `file` (local directory) or `s3` (Amazon S3 or S3-compatible storage). The `uri` value gives the exact path or bucket and prefix. See [Configuration Reference](configuration-reference.md) and [Storage Reference](storage-reference.md).

## Where is the resume position stored? Can I reconstruct from S3 alone if I lose the local server?

The server does not use SQLite or any local-only database. Resume state is stored in the same backend you configure. For a file backend, that is the directory in `storage.uri`: the server writes `metadata.json` (replication mode), `binlog.index` (list of binlog file names, one per line), and for each binlog file a `<name>.json` file containing that file’s flushed size (the byte position), GTID sets (in GTID mode), and timestamps. For an S3 backend, the same objects are stored in the bucket/prefix. So the resume position is: the last binlog file name in `binlog.index` plus the `size` field from that file’s `.json`. If you lose the local server’s SSD: with a file backend you lose the storage (the storage was on that disk). With an S3 backend, everything is in the bucket; point a new instance at the same `storage.uri` and the new instance will load metadata and resume from S3. See [Where the resume position is stored](operational-behavior-reference.md#where-the-resume-position-is-stored) in Core behavior.

## How do I resume after stopping the server?

A new run resumes from the position where the previous run stopped. No extra steps are required. Ensure the process is stopped gracefully (for example, with Ctrl+C or `kill <pid>`) so that buffered data is flushed. Using `kill -9` can leave recent data unwritten.

## What MySQL privilege does the connection user need?

The MySQL user in the `connection` section must have the REPLICATION SLAVE privilege. That privilege allows the user to connect as a replication client and read binary log events from the server.

## Do I need log_slave_updates when connecting to a PXC node?

Yes. If the source is a Percona XtraDB Cluster (PXC) node, the primary must have `log_slave_updates` (or `log_replica_updates`) enabled. If it is OFF, that node's binlog contains only writes that originated on that node, not writes applied from other cluster nodes, so the Binlog Server would capture only a subset of cluster traffic and recovery or auditing would fail. See [Using with Percona Operators](use-with-operators.md#connecting-to-the-cluster) for the full requirement and how to verify.

## Why not use mysqlbinlog in a loop instead?

Percona Binary Log Server adds reconnection and resume, so a stopped run can continue from the last position without manual scripting. The server also writes directly to S3 or S3-compatible storage, keeps transaction boundaries so storage stays consistent, and provides search commands (`search_by_timestamp`, `search_by_gtid_set`) to find the minimal set of files for a given time or GTID set. Using `mysqlbinlog` in a loop typically requires custom logic for reconnection, upload to storage, and search.

## Can I use localhost for the MySQL connection?

Do not use `localhost` when a TCP connection is required. The MySQL client library often treats `localhost` as a request for a Unix socket. Use `127.0.0.1` (or the correct host name or IP) for TCP.

## Is fs_buffer_directory required for S3 storage?

No. `fs_buffer_directory` is optional. When the backend is S3 and the option is not set, the default OS temporary directory (for example, `/tmp` on Linux) is used for buffering partial data before upload.

## Why does S3 storage upload more data than the binlog size?

S3 does not support appending to an existing object. Each checkpoint flush can re-upload the object. So with a small `checkpoint_size` or frequent `checkpoint_interval`, total uploaded data can be much larger than the final binlog size. Choose checkpoint values with care; see [Storage Reference](storage-reference.md) for details.

## What happens if my IAM role or S3 credentials expire?

The server does not manage credentials or IAM. If the role or credentials used for S3 (in the URI or environment) expire or are revoked, S3 writes will fail. The process will log errors and may exit depending on the error. Fix the credentials or role, then restart the process; the process will resume from the last position stored in metadata. Set up credential expiry alerts and rotation so that expiration does not catch you by surprise.

## What if the S3 bucket or endpoint hits rate limits?

If the S3 API returns throttling or rate-limit errors, the server may retry (behavior is implementation-dependent). Repeated failures will appear in logs. Monitor logs for S3 errors and alert on them. If you hit sustained rate limits, increase checkpoint size or interval to reduce upload frequency, or scale your S3 endpoint/bucket limits. See [Storage Reference](storage-reference.md) for checkpoint behavior.

## How do I migrate from a standard MySQL replica to Percona Binary Log Server?

Percona Binary Log Server is not a drop-in replacement for a replica. The server is a replication client that reads binlogs and writes them to storage; the server does not apply events to a MySQL instance. To “migrate” from a replica that you used only for binlog archiving: stop the replica (or repurpose the replica), create a MySQL user with REPLICATION SLAVE on the source, point the Binary Log Server config at the source and your chosen storage, then run `pull` (or `fetch` for a one-time copy). The server will stream from the source and write to local disk or S3. If you were using the replica for read scaling or failover, you need a different solution for those; Percona Binary Log Server only archives binlogs.

## How do I use Percona Binary Log Server with the Percona Operator for MySQL (PS or PXC)?

Run Percona Binary Log Server as a separate Kubernetes workload that connects to your operator-managed cluster’s primary. Set `connection.host` to the primary’s Kubernetes service (for example, `cluster1-mysql-primary.namespace.svc.cluster.local`) and `connection.port` to 3306. Use a MySQL user with REPLICATION SLAVE; store the password in a Secret and the rest of the config in a ConfigMap. For storage, use a PVC (file backend) or S3 (with IRSA or credentials). For full steps and when to use the Binary Log Server with [Percona Operator for MySQL (PS)](https://docs.percona.com/percona-operator-for-mysql/ps/) or [PXC](https://docs.percona.com/percona-operator-for-mysql/pxc/) (including how the Binary Log Server relates to the operator’s built-in PITR), see [Using Percona Binary Log Server With Percona Operators](use-with-operators.md).

## Can I use Percona Binary Log Server to feed a Snowflake pipe or another data warehouse?

The server writes raw binary log files to local disk or S3. The server does not parse events into rows or push to Snowflake, BigQuery, or any warehouse. To feed a Snowflake pipe (or similar), you would use the stored binlogs as input to a separate pipeline: for example, a CDC tool or custom job that reads the binlog files (or a copy in S3), parses events, and loads into Snowflake. Percona Binary Log Server can be the first stage (binlogs in S3); the rest of the pipeline is outside Percona Binary Log Server.

## How do I find which stored files to use for point-in-time recovery?

Use `search_by_timestamp` with the target time (ISO format). The command returns the list of stored binary log files that contain events up to that timestamp. Use those files (and a full backup) for point-in-time recovery. For GTID-based recovery, use `search_by_gtid_set` with the target GTID set to get the minimal set of files that cover those transactions.

## How do I know which documentation version I am viewing?

When the site is built with multiple versions (for example, using mike), a version switcher appears in the header. Use the switcher to select the product version that matches your deployment. Options and flags can change or be deprecated between versions (for example, a flag deprecated in v0.2.0); the version selector ensures you see the docs for the version you are using.

## Where can I get more help?

See [Get help from Percona](get-help.md) for community forums and support options. For configuration and command details, use the [Configuration Reference](configuration-reference.md), [Command Reference](command-reference.md), and [Glossary](glossary.md).
