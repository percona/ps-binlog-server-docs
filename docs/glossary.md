# Glossary

Terms used in Percona Binary Log Server documentation.

### added_gtids

GTID set that was added by events in a given binary log file. Search result output and metadata files can include this field.

### backend

Storage type used by Percona Binary Log Server. Supported values are `file` (local filesystem) and `s3` (Amazon S3 or S3-compatible storage).

### binary log

File on a MySQL server that records data changes (events) in a format suitable for replication or point-in-time recovery. Percona Binary Log Server reads binary logs from a remote server and writes copies to configured storage.

### binary log event

Single record in a binary log, such as a row change or transaction boundary. Percona Binary Log Server streams events from the source server and writes them to storage.

### checkpoint

Point at which Percona Binary Log Server flushes buffered data to permanent storage. Checkpointing can be triggered by accumulated size (`checkpoint_size`) or by elapsed time (`checkpoint_interval`).

### checkpoint_interval

Configuration value that sets a time-based flush threshold. After this interval, buffered data is written to storage. Expressed as a string with an optional suffix (for example, `30s`, `5m`, `1h`).

### checkpoint_size

Configuration value that sets a size-based flush threshold. After buffered data reaches this size, the data is written to storage. Expressed as a string with an optional suffix (for example, `128M`, `1G`).

### connection

Configuration section that defines how Percona Binary Log Server connects to the source MySQL server. Includes host, port or DNS SRV name, user, password, timeouts, and optional SSL or TLS settings.

### DNS SRV

DNS record type used to discover host names and ports for a service. The `connection.dns_srv_name` option uses DNS SRV for host discovery instead of a fixed host and port.

### fetch

Operation mode that connects to the source MySQL server, reads all currently available binary log events, stores the data, then exits. Suited to one-time or on-demand collection.

### fs_buffer_directory

Configuration option that specifies a local directory for buffering partial data before writing to non-file storage (for example, S3). Helps avoid writing incomplete data to object storage.

### graceful shutdown

Stopping the Percona Binary Log Server process in a way that flushes buffered data and leaves storage consistent. Triggered by signals such as SIGINT or SIGTERM. Contrast with a forced stop (for example, `kill -9`), which can lose recent progress.

### GTID

Global Transaction Identifier. A unique identifier for a transaction in MySQL replication. GTIDs allow replication to track which transactions have been applied across servers.

### GTID set

Set of one or more GTIDs or GTID ranges. Used when configuring GTID-based replication and when running `search_by_gtid_set` to find binary log files that cover a given set of transactions.

### GTID-based replication

Replication mode in which the server and client track progress by GTID set rather than by file name and position. Enables `search_by_gtid_set` and more flexible failover and topology changes.

### initial_gtids

GTID set that was already present at the start of a binary log file (for example, carried over from a previous file). Search result output and metadata files can include this field. In the per-file metadata JSON (for example, `binlog.000001.json`), the upstream uses the key `previous_gtids` for this value.

### MinIO

Object storage server that exposes an S3-compatible API. Percona Binary Log Server can store binary logs in MinIO by using an HTTP or HTTPS storage URI.

### metadata file

JSON file that Percona Binary Log Server maintains alongside each stored binary log file. Stores information such as event timestamps and GTID sets to support search operations.

### mysqlbinlog

MySQL client utility that can read binary logs from a file or from a remote server. Percona Binary Log Server provides similar remote-reading behavior with added features such as reconnection, resume, and direct storage to S3.

### object storage

Storage model that stores data as objects in buckets or containers, accessed by API (for example, Amazon S3 or S3-compatible services). Percona Binary Log Server can write binary log files directly to object storage.

### idle_time

Configuration value (`replication.idle_time`) that sets the number of seconds to wait between reconnect attempts in pull mode. No exponential backoff; the delay is always this many seconds. A short value during an outage can produce many connection attempts and trigger rate limits or circuit breakers in cloud environments.

### point-in-time recovery

Restoring a database to a chosen moment in time by applying a full backup plus binary log events up to that moment. Percona Binary Log Server supports point-in-time recovery by archiving binary logs and by search commands that return the minimal file set for a given timestamp or GTID set. Often abbreviated PITR.

### PITR

Abbreviation for [point-in-time recovery](#point-in-time-recovery). The Percona Operator for MySQL (PXC) exposes a native PITR feature (`backup.pitr`) that uploads binlogs to S3 or Azure.

### position-based replication

Replication mode in which the client tracks progress by binary log file name and byte position. Produces stored files that are physically aligned with the source server’s binary log files.

### pull

Operation mode that connects to the source MySQL server, reads binary log events, waits for new events, and reconnects as needed. Runs continuously until stopped. Suited to ongoing collection.

### REPLICATION SLAVE

MySQL privilege required for a user that will act as a replication client (reading binary logs from the server). The account used in the Percona Binary Log Server `connection` section must have this privilege.

### replication client

Role played by Percona Binary Log Server when connecting to a MySQL server: the server streams binary log events to the client. The MySQL user must have the REPLICATION SLAVE privilege.

### resume

Behavior where a new run of Percona Binary Log Server continues from the position where a previous run stopped. Avoids re-downloading or re-reading events that are already stored.

### S3

Amazon Simple Storage Service. Object storage that Percona Binary Log Server can use as a storage backend via an `s3://` URI.

### S3-compatible storage

Object storage service that offers an API compatible with Amazon S3 (for example, MinIO). Percona Binary Log Server can use such services via an `http://` or `https://` storage URI.

### search_by_gtid_set

Command that returns the minimal set of stored binary log files needed to cover a given GTID set. Requires storage that was created with GTID-based replication.

### search_by_timestamp

Command that returns the list of stored binary log files that contain at least one event with a timestamp less than or equal to a given timestamp.

### server_id

Numeric identifier that a replication client presents to the MySQL server. Required by the replication protocol. Set in the `replication.server_id` configuration option.

### storage

Configuration section that defines where Percona Binary Log Server writes binary log files. Includes the storage backend type and URI, optional buffer directory, and optional checkpoint settings.

### transaction boundary

Point in a binary log that marks the start or end of a transaction. Percona Binary Log Server writes data at transaction boundaries when possible, so stored files remain usable for recovery and resume.

### URI

Uniform Resource Identifier. In Percona Binary Log Server, the storage URI specifies the destination for binary log files (for example, `file:///path`, `s3://bucket/path`, or `https://host/bucket/path`).
