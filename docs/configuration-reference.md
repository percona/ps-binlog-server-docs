# Configuration Reference

Percona Binary Log Server uses a JSON configuration file with four top-level sections:

* `logger`

* `connection`

* `replication`

* `storage`

## Production-ready template

The following template includes every supported variable. The application expects standard JSON. A commented (JSONC) version is provided for reference; strip comments before use with Percona Binary Log Server.

```jsonc
{
  "logger": {
    "level": "info",           // minimum log severity: trace | debug | info | warning | error | fatal
    "file": "/var/log/binlog-server/binsrv.log"  // log file path; use "" for stdout
  },
  "connection": {
    "host": "127.0.0.1",       // MySQL host; use 127.0.0.1 for TCP, not localhost
    "port": 3306,              // MySQL port
    "user": "rpl_user",         // user with REPLICATION SLAVE privilege
    "password": "rpl_password",
    "connect_timeout": 20,     // seconds to establish connection
    "read_timeout": 60,        // seconds to wait for read; affects graceful shutdown
    "write_timeout": 60,       // seconds to wait for write
    "ssl": {
      "mode": "verify_identity",  // disabled | preferred | required | verify_ca | verify_identity
      "ca": "/etc/mysql/ssl/ca.pem",
      "capath": "/etc/mysql/ssl/cadir",
      "crl": "/etc/mysql/ssl/crl.pem",
      "crlpath": "/etc/mysql/ssl/crldir",
      "cert": "/etc/mysql/ssl/client-cert.pem",
      "key": "/etc/mysql/ssl/client-key.pem",
      "cipher": "ECDHE-RSA-AES128-GCM-SHA256"
    },
    "tls": {
      "ciphersuites": "TLS_AES_256_GCM_SHA384",  // TLS 1.3 ciphersuites
      "version": "TLSv1.3"                        // allowed TLS versions
    }
  },
  "replication": {
    "server_id": 42,           // client server ID (required by replication protocol)
    "idle_time": 10,           // seconds between reconnect attempts in pull mode
    "verify_checksum": true,   // verify binlog event checksums
    "mode": "position",        // position | gtid
    "rewrite": {               // optional; for GTID mode rewritten binlog layout
      "base_file_name": "binlog",
      "file_size": "128M"
    }
  },
  "storage": {
    "backend": "file",         // file | s3
    "uri": "file:///var/lib/binlog-server",
    "fs_buffer_directory": "/var/lib/binlog-server/buffer",  // optional; for S3 buffer
    "checkpoint_size": "128M",    // optional; flush after this size; 0 = disabled
    "checkpoint_interval": "30s" // optional; flush after this interval; 0 = disabled
  }
}
```

Variable reference (production-ready template):

| Section | Variable | Type | Default | Description |
|---------|----------|------|---------|-------------|
| logger | `level` | String | `info` | Minimum log severity: `trace`, `debug`, `info`, `warning`, `error`, `fatal`. Use `info` or `warning` in production. |
| logger | `file` | String | `""` | Log file path, or `""` for stdout. |
| connection | `host` | String | `127.0.0.1` | MySQL server host (IP or hostname). Use `127.0.0.1` for TCP, not `localhost`. |
| connection | `port` | Int | `3306` | MySQL server port (for example 3306). |
| connection | `user` | String | — | MySQL user with REPLICATION SLAVE privilege. |
| connection | `password` | String | — | Password for `user`. |
| connection | `connect_timeout` | Int | `20` | Connection timeout in seconds. |
| connection | `read_timeout` | Int | `60` | Read timeout in seconds; affects graceful shutdown delay. |
| connection | `write_timeout` | Int | `60` | Write timeout in seconds. |
| connection | `dns_srv_name` | String | — | Alternative to host+port: DNS SRV record name for host discovery. |
| connection.ssl | `mode` | String | — | SSL mode: `disabled`, `preferred`, `required`, `verify_ca`, `verify_identity`. |
| connection.ssl | `ca` | String | — | Path to trusted CA certificate file. |
| connection.ssl | `capath` | String | — | Path to directory of trusted CA certificates. |
| connection.ssl | `crl` | String | — | Path to certificate revocation list file. |
| connection.ssl | `crlpath` | String | — | Path to directory of CRL files. |
| connection.ssl | `cert` | String | — | Path to client certificate file. |
| connection.ssl | `key` | String | — | Path to client private key file. |
| connection.ssl | `cipher` | String | — | Allowed SSL cipher list. |
| connection.tls | `ciphersuites` | String | — | Allowed TLS 1.3 ciphersuites. |
| connection.tls | `version` | String | — | Allowed TLS protocol versions (for example TLSv1.3). |
| replication | `server_id` | Int | — | Replication client server ID (required by protocol). |
| replication | `idle_time` | Int | `10` | Seconds to wait between reconnect attempts in `pull` mode. Default can be too aggressive in cloud environments; see [Best practice: idle_time](operational-behavior-reference.md#best-practice-idle_time). |
| replication | `verify_checksum` | Boolean | `true` | When true, request CRC32 and verify event checksums; when false, NONE. Only CRC32 and NONE supported (same as MySQL `binlog_checksum`). See upstream `easymysql/connection.cpp`. |
| replication | `mode` | String | `position` | `position` or `gtid`; see the replication section in this page. |
| replication.rewrite | (optional) | — | unset | When set, GTID mode uses rewritten binlog file layout; see replication.rewrite in this page. |
| replication.rewrite | `base_file_name` | String | — | Base name for rewritten binlog files (for example, `binlog`). |
| replication.rewrite | `file_size` | String | — | Target size per rewritten file (for example, `128M`). |
| storage | `backend` | String | `file` | `file` or `s3`. |
| storage | `uri` | String | — | Storage URI; format depends on backend (see Storage Reference). |
| storage | `fs_buffer_directory` | String | OS temp dir | (Optional) Local buffer directory for S3. |
| storage | `checkpoint_size` | String | unset (disabled) | (Optional) Flush after this many bytes (for example 128M); 0 disables. |
| storage | `checkpoint_interval` | String | unset (disabled) | (Optional) Flush after this interval (for example 30s); 0 disables. |

Full example (with optional SSL/TLS):

```json
{
  "logger": {
    "level": "debug",
    "file": "binsrv.log"
  },
  "connection": {
    "host": "127.0.0.1",
    "port": 3306,
    "user": "rpl_user",
    "password": "rpl_password",
    "connect_timeout": 20,
    "read_timeout": 60,
    "write_timeout": 60,
    "ssl": {
      "mode": "verify_identity",
      "ca": "/etc/mysql/ca.pem",
      "capath": "/etc/mysql/cadir",
      "crl": "/etc/mysql/crl-client-revoked.crl",
      "crlpath": "/etc/mysql/crldir",
      "cert": "/etc/mysql/client-cert.pem",
      "key": "/etc/mysql/client-key.pem",
      "cipher": "ECDHE-RSA-AES128-GCM-SHA256"
    },
    "tls": {
      "ciphersuites": "TLS_AES_256_GCM_SHA384",
      "version": "TLSv1.3"
    }
  },
  "replication": {
    "server_id": 42,
    "idle_time": 10,
    "verify_checksum": true,
    "mode": "position"
  },
  "storage": {
    "backend": "s3",
    "uri": "https://key_id:secret@192.168.0.100:9000/binsrv-bucket/vault",
    "fs_buffer_directory": "/tmp/binsrv",
    "checkpoint_size": "128M",
    "checkpoint_interval": "30s"
  }
}
```

## `logger`

`logger.level` controls the minimum severity written to the log output.

* Type: String. Default: `info`.

Allowed values:

* `trace`

* `debug`

* `info`

* `warning`

* `error`

* `fatal`

`logger.file` controls the log destination.

* Type: String. Default: `""` (stdout).

* Using a file path writes logs to a local file; using an empty string `""` writes logs to standard output.

Severity notes:

* `fatal`: currently unused

* `error`: caught exceptions and failure messages

* `warning`: currently unused

* `info`: normal progress messages

* `debug`: exception function names and parsed event data

* `trace`: source file and line details for exceptions, plus raw event hex dumps

## `connection`

`connection` defines how Percona Binary Log Server connects to the source MySQL server.

Common fields (Type; Default):

* `host`: String; `127.0.0.1`. MySQL host name or IP address.

* `port`: Int; `3306`. MySQL port, usually `3306`.

* `dns_srv_name`: String; —. DNS SRV record name for host discovery.

* `user`: String; —. MySQL account with `REPLICATION SLAVE` privilege.

* `password`: String; —. Password for that MySQL account.

* `connect_timeout`: Int; `20`. Connection timeout in seconds.

* `read_timeout`: Int; `60`. Read timeout in seconds.

* `write_timeout`: Int; `60`. Write timeout in seconds.

Use either:

* `host` and `port`

* `dns_srv_name`

Do not use `localhost` for TCP access. `libmysqlclient` may treat `localhost` as a Unix socket request. Use `127.0.0.1` when TCP is required.

## `connection.ssl`

`connection.ssl` configures SSL settings for the MySQL client connection.

Fields (Type; Default):

* `mode`: String; —. One of `disabled`, `preferred`, `required`, `verify_ca`, or `verify_identity`.

* `ca`: String; —. Path to trusted CA file.

* `capath`: String; —. Path to trusted CA directory.

* `crl`: String; —. Path to certificate revocation list file.

* `crlpath`: String; —. Path to certificate revocation list directory.

* `cert`: String; —. Path to client certificate.

* `key`: String; —. Path to private key for the client certificate.

* `cipher`: String; —. Allowed SSL cipher list.

## `connection.tls`

`connection.tls` configures TLS 1.3 details. The JSON key for ciphersuites is `ciphersuites` (not `ca`).

Fields (Type; Default):

* `ciphersuites`: String; —. List of permissible TLS 1.3 ciphersuites for encrypted connections.

* `version`: String; —. List of permissible TLS protocols for encrypted connections.

## `replication`

`replication` controls replication behavior.

Fields (Type; Default):

* `server_id`: Int; —. Client server ID used during replication (required by protocol).

* `idle_time`: Int; `10`. Sleep time in seconds between reconnect attempts in `pull` mode. The default (10s) can be too aggressive when the source is behind cloud load balancers or rate limiters; a short interval during a network partition can trigger blacklisting or circuit breakers. Prefer 30s or 60s in production unless you need faster retries. See [Best practice: idle_time](operational-behavior-reference.md#best-practice-idle_time) in Core behavior.

* `verify_checksum`: Boolean; `true`. When true, the client requests CRC32 and the server verifies event checksums before writing; when false, the client requests NONE. The application supports only these two algorithms (same as MySQL `binlog_checksum`: CRC32 or NONE). See [Percona-Lab/percona-binlog-server](https://github.com/Percona-Lab/percona-binlog-server) `easymysql/connection.cpp` (`set_binlog_checksum`).

* `mode`: String; `position`. `position` or `gtid`.

The `mode` value selects how Percona Binary Log Server tracks replication progress and requests events from the source MySQL server. The choice affects how stored binary log files are organized and which search commands are available.

Mode values:

* `position`: position-based replication. The server tracks progress by binary log file name and byte position on the source. Stored files are aligned with the source server’s binary log files and can be used where a byte-for-byte copy of the source binlogs is required. Use `position` when the source uses position-based replication or when stored files must match the source layout. The `search_by_gtid_set` command is not supported for storage created in this mode.

* `gtid`: GTID-based replication. The server tracks progress by GTID set. Stored files may not match the source server’s file names or layout but contain the same transactions. Use `gtid` when the source uses GTID-based replication and when you need `search_by_gtid_set` to find the minimal set of files for a given GTID set. Both `search_by_timestamp` and `search_by_gtid_set` are supported.

### `replication.rewrite` (optional)

When `replication.mode` is `gtid`, you can set an optional `rewrite` object to control how the server writes binlog files: the server can rewrite events into a layout with a chosen base file name and target file size instead of mirroring the source file names. If `rewrite` is not set, behavior is implementation-defined (the server may still rewrite with internal defaults). Fields (Type; Default):

* `base_file_name`: String; —. Base name for rewritten binlog files (for example, `binlog` produces `binlog.000001`, `binlog.000002`, and so on).

* `file_size`: String; —. Target size per rewritten binlog file, with optional suffix (for example, `128M`, `1G`). The server rotates to a new file when the current file reaches this size.

Defined in the upstream [replication_config.hpp](https://github.com/Percona-Lab/percona-binlog-server/blob/main/src/binsrv/replication_config.hpp) and [rewrite_config.hpp](https://github.com/Percona-Lab/percona-binlog-server/blob/main/src/binsrv/rewrite_config.hpp).

## `storage`

`storage` defines where Percona Binary Log Server writes binary log files and how often buffered data is flushed to that destination.

Fields (Type; Default):

* `backend`: String; `file`. Storage type. Must be `file` for a local directory or `s3` for Amazon S3 or an S3-compatible service. The backend determines the format of `uri`.

* `uri`: String; —. Destination for saved binary log files. For `backend: "file"`, use a `file://` URI with an absolute path. For `backend: "s3"`, use an `s3://` URI for Amazon S3 or an `http://` or `https://` URI for an S3-compatible endpoint. See [Storage Reference](storage-reference.md) for URI formats and examples.

* `fs_buffer_directory`: String; OS temp dir. (Optional) Local directory used to buffer partial data before writing to non-file storage. Meaningful when `backend` is `s3`. Partially written binlog data is held here until a checkpoint flushes to object storage. If not set, the default OS temporary directory is used (for example, `/tmp` on Linux).

* `checkpoint_size`: String; unset (disabled). (Optional) Size of buffered data after which the server flushes to storage. Value is a string with an optional suffix (for example, `128M`, `1G`). If unset or zero, size-based checkpointing is disabled.

* `checkpoint_interval`: String; unset (disabled). (Optional) Time interval after which the server flushes buffered data to storage. Value is a string with an optional suffix (for example, `30s`, `5m`). If unset or zero, time-based checkpointing is disabled.

Backend values:

* `file`: local filesystem storage. Binary log files are written directly to the path given in `uri`. No extra buffer directory or checkpoint settings are required for correctness, but checkpoint options can still reduce memory use during large writes.

* `s3`: Amazon S3 or S3-compatible storage (for example, MinIO). Binary log data is buffered and then uploaded according to `checkpoint_size` and `checkpoint_interval`. S3 does not support appending to objects; each flush re-uploads the object. A small `checkpoint_interval` on a high-traffic server can cause very high S3 PUT cost and network load. See [Cost and Performance Warning (S3)](storage-reference.md#cost-and-performance-warning-s3) and [Cost Optimization (S3)](storage-reference.md#cost-optimization-s3) in Storage Reference; a typical `checkpoint_size` of 50MB–100MB (for example, `64M` or `128M`) balances data loss risk and PUT cost.
