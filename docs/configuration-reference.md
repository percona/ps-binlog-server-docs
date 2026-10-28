# Configuration reference

Percona Binary Log Server uses a JSON configuration file with five top-level sections:

* `logger`

* `connection`

* `replication`

* `keyring` (optional)

* `storage`

## Production-ready template

Every supported field appears in the template that follows. The binary expects plain JSON. The template uses JSONC comments for annotation. Remove the comments before you run Percona Binary Log Server.

```jsonc
{
  "logger": {
    "level": "info",           // required; trace | debug | info | warning | error | fatal
    "file": "/var/log/binlog-server/binsrv.log"  // required; use "" to log to stdout
  },
  "connection": {
    "host": "127.0.0.1",       // optional (pair with port, or replace with dns_srv_name); use 127.0.0.1 for TCP, not localhost
    "port": 3306,              // optional (pair with host, or replace with dns_srv_name)
    "user": "rpl_user",        // required; user with REPLICATION SLAVE privilege
    "password": "rpl_password",// required
    "connect_timeout": 20,     // required; seconds to establish connection
    "read_timeout": 60,        // required; seconds to wait for read; affects graceful shutdown
    "write_timeout": 60,       // required; seconds to wait for write
    "ssl": {                   // optional section
      "mode": "verify_identity",  // required within ssl; disabled | preferred | required | verify_ca | verify_identity
      "ca": "/etc/mysql/ssl/ca.pem",
      "capath": "/etc/mysql/ssl/cadir",
      "crl": "/etc/mysql/ssl/crl.pem",
      "crlpath": "/etc/mysql/ssl/crldir",
      "cert": "/etc/mysql/ssl/client-cert.pem",
      "key": "/etc/mysql/ssl/client-key.pem",
      "cipher": "<SSL_CIPHER_LIST>"
    },
    "tls": {                   // optional section
      "ciphersuites": "<TLS_CIPHERSUITES>",  // TLS 1.3 ciphersuites
      "version": "<TLS_VERSION>"             // allowed TLS versions
    }
  },
  "replication": {
    "server_id": 42,           // required; client server ID (required by replication protocol)
    "idle_time": 10,           // required; seconds between reconnect attempts in pull mode
    "verify_checksum": true,   // required; verify binlog event checksums
    "mode": "gtid",            // required; position | gtid
    "rewrite": {               // optional; only valid when mode is "gtid". When omitted, the utility mirrors the source server's binlog file names and rotation layout.
      "base_file_name": "binlog",
      "file_size": "128M"
    }
  },
  "keyring": {                 // optional; required when storage already has encrypted files, or when storage.encryption is present
    "uri": "file:///var/lib/pbs/keyring/keyring_data.json"
  },
  "storage": {
    "backend": "file",         // required; file | s3
    "uri": "file:///var/lib/binlog-server/data",  // required
    "fs_buffer_directory": "/var/lib/binlog-server/buffer",  // optional; local staging directory for S3 uploads (used only on flush, not for unflushed events); when omitted, a UUID-named subdirectory under $TMPDIR (or /tmp on Linux when unset) is created and removed at clean shutdown
    "checkpoint_size": "128M",    // optional; flush after configured size threshold; 0 or omitted disables
    "checkpoint_interval": "30s", // optional; flush when a new event is processed and the interval since the last flush has elapsed; 0 or omitted disables
    "encryption": {            // optional section; omit to write new binlogs without encryption
      "format": "generic",
      "kek_id": "<KEK_ID>",
      "cipher": "AES-256-CTR"
    }
  }
}
```

Variable reference (production-ready template):

The configuration schema has no built-in defaults. Every variable is either Required or Optional. A Required variable means the JSON key must be present. An Optional variable means you can omit the key. The values in the template and in the Example column are examples only. If you omit an Optional key, the example value is not used as a default. For the authoritative definitions, see the upstream headers `src/binsrv/logger_config.hpp`, `src/easymysql/connection_config.hpp`, `src/binsrv/replication_config.hpp`, `src/binsrv/rewrite_config.hpp`, `src/binsrv/keyring_config.hpp`, `src/binsrv/encryption_config.hpp`, and `src/binsrv/storage_config.hpp`.

| Section | Variable | Type | Required | Example | Description |
|---------|----------|------|----------|---------|-------------|
| logger | `level` | String | Yes | `info` | Minimum log severity: `trace`, `debug`, `info`, `warning`, `error`, `fatal`. Use `info` or `warning` in production. |
| logger | `file` | String | Yes | `""` | Log file path. Use `""` to log to stdout. |
| connection | `host` | String | No (use `host`+`port` or `dns_srv_name`) | `127.0.0.1` | Source server host (IP or hostname; MySQL or MySQL-compatible). Use `127.0.0.1` for TCP, not `localhost`. |
| connection | `port` | Int | No (use `host`+`port` or `dns_srv_name`) | `3306` | Source server port (for example 3306). |
| connection | `dns_srv_name` | String | No (use `host`+`port` or `dns_srv_name`) | — | Alternative to `host`+`port`: DNS SRV record name for host discovery. |
| connection | `user` | String | Yes | `rpl_user` | Account with REPLICATION SLAVE privilege. |
| connection | `password` | String | Yes | `rpl_password` | Password for `user`. |
| connection | `connect_timeout` | Int | Yes | `20` | Connection timeout in seconds. |
| connection | `read_timeout` | Int | Yes | `60` | Read timeout in seconds; affects graceful shutdown delay. |
| connection | `write_timeout` | Int | Yes | `60` | Write timeout in seconds. |
| connection.ssl | (section) | Object | No | — | Optional section; omit the whole `ssl` object when TLS is not configured. |
| connection.ssl | `mode` | String | Yes (within `ssl`) | `verify_identity` | SSL mode: `disabled`, `preferred`, `required`, `verify_ca`, `verify_identity`. |
| connection.ssl | `ca` | String | No | `/etc/mysql/ca.pem` | Path to trusted CA certificate file. |
| connection.ssl | `capath` | String | No | `/etc/mysql/cadir` | Path to directory of trusted CA certificates. |
| connection.ssl | `crl` | String | No | `/etc/mysql/crl.pem` | Path to certificate revocation list file. |
| connection.ssl | `crlpath` | String | No | `/etc/mysql/crldir` | Path to directory of CRL files. |
| connection.ssl | `cert` | String | No | `/etc/mysql/client-cert.pem` | Path to client certificate file. |
| connection.ssl | `key` | String | No | `/etc/mysql/client-key.pem` | Path to client private key file. |
| connection.ssl | `cipher` | String | No | `<SSL_CIPHER_LIST>` | Allowed SSL cipher list. |
| connection.tls | (section) | Object | No | — | Optional section; omit the whole `tls` object when TLS 1.3 is not configured. |
| connection.tls | `ciphersuites` | String | No | `<TLS_CIPHERSUITES>` | Allowed TLS 1.3 ciphersuites. |
| connection.tls | `version` | String | No | `<TLS_VERSION>` | Allowed TLS protocol versions. |
| replication | `server_id` | Int | Yes | `42` | Replication client server ID (required by protocol). |
| replication | `idle_time` | Int | Yes | `10` | Seconds to wait between reconnect attempts in `pull` mode. For tuning guidance, see [Best practice: idle_time](operational-behavior-reference.md#best-practice-idle_time). |
| replication | `verify_checksum` | Boolean | Yes | `true` | When `true`, the client requests CRC32 and verifies event checksums; when `false`, the client requests NONE. Only CRC32 and NONE are supported (same as `binlog_checksum` on the source). See upstream `src/easymysql/connection.cpp`. |
| replication | `mode` | String | Yes | `gtid` | `position` for position-based replication or `gtid` for GTID-based replication. The upstream sample `main_config.json` uses `gtid`. This setting also determines the resume cursor — see [Resume behavior](operational-behavior-reference.md#resume-behavior). |
| replication.rewrite | (section) | Object | No | — | Optional section; requires `replication.mode: gtid`. When the section is omitted, the utility writes binlog files using the source server's file names and rotation layout. |
| replication.rewrite | `base_file_name` | String | Yes (within `rewrite`) | `binlog` | Base name for rewritten binlog files. |
| replication.rewrite | `file_size` | String | Yes (within `rewrite`) | `128M` | Target size per rewritten file. |
| keyring | (section) | Object | No | — | Optional section; required when storage already has encrypted files, or when `storage.encryption` is present. See [Binlog storage encryption](binlog-encryption.md). |
| keyring | `uri` | String | Yes (within `keyring`) | `file:///var/lib/pbs/keyring/keyring_data.json` | URI of the keyring JSON file. The only supported scheme is `file://` on the local filesystem. |
| storage | `backend` | String | Yes | `file` | `file` or `s3`. |
| storage | `uri` | String | Yes | `file:///var/lib/binlog-server/data` | Storage URI; format depends on backend (see [Storage Reference](storage-reference.md)). |
| storage | `fs_buffer_directory` | String | No | `/var/lib/binlog-server/buffer` | Local staging directory for S3 uploads (not the checkpointing buffer for unflushed events, which live in the in-memory event buffer). Data enters this directory only when a flush occurs: the server writes the flushed bytes to a UUID-named temporary file and immediately uploads the cumulative S3 object from that file. When omitted, the server creates a UUID-named subdirectory under the OS temporary directory (`$TMPDIR`, or `/tmp` on Linux when unset) and removes that subdirectory at clean shutdown. A `fs_buffer_directory` set explicitly is never deleted by the server. Set this field explicitly to choose a stable, predictable location. |
| storage | `checkpoint_size` | String | No | `128M` | Flush after the configured byte threshold. When omitted or set to `0`, size-based checkpointing is disabled. |
| storage | `checkpoint_interval` | String | No | `30s` | Time threshold that triggers a flush when a new event is processed. Evaluated only on event arrival; without incoming events the buffer is not flushed even after the interval elapses. When omitted or set to `0`, time-based checkpointing is disabled. |
| storage.encryption | (section) | Object | No | — | Optional section; omit the whole `encryption` object to write new files without encryption. Keep `keyring` if existing files are encrypted. See [Binlog storage encryption](binlog-encryption.md). |
| storage.encryption | `format` | String | Yes (within `encryption`) | `generic` | Encryption format. The only supported value is `generic`. |
| storage.encryption | `kek_id` | String | Yes (within `encryption`) | — | ID of the key-encryption key (KEK) in the keyring. The ID must exist in the keyring file. |
| storage.encryption | `cipher` | String | Yes (within `encryption`) | `AES-256-CTR` | Cipher name for binlog file data encryption. Must be a CTR mode cipher. |

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
      "cipher": "<SSL_CIPHER_LIST>"
    },
    "tls": {
      "ciphersuites": "<TLS_CIPHERSUITES>",
      "version": "<TLS_VERSION>"
    }
  },
  "replication": {
    "server_id": 42,
    "idle_time": 10,
    "verify_checksum": true,
    "mode": "position"
  },
  "keyring": {
    "uri": "file:///var/lib/pbs/keyring/keyring_data.json"
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

`logger.level` sets the minimum severity written to the log.

* Type: String. Required.

Allowed values:

* `trace`

* `debug`

* `info`

* `warning`

* `error`

* `fatal`

`logger.file` sets the log destination.

* Type: String. Required.

* A file path writes logs to that file; an empty string `""` sends logs to stdout.

Severity notes:

* `fatal`: reserved (no messages emitted at this level).

* `error`: caught exceptions and failure messages.

* `warning`: storage recovery messages, for example leftover `*.tmp` objects or a size mismatch on the current binlog file. See [Automatic storage recovery](operational-behavior-reference.md#automatic-storage-recovery).

* `info`: normal progress messages.

* `debug`: exception function names and parsed event data.

* `trace`: source file and line for exceptions, plus raw event hex dumps.

## `connection`

`connection` defines how Percona Binary Log Server reaches the MySQL or MySQL-compatible source.

Common fields (Type; Required):

* `host`: String; optional (pair with `port`, or replace with `dns_srv_name`). Source server host name or IP address.

* `port`: Int; optional (pair with `host`, or replace with `dns_srv_name`). Source server port, usually `3306`.

* `dns_srv_name`: String; optional. DNS SRV record name for host discovery; use instead of `host`+`port`.

* `user`: String; required. Account with `REPLICATION SLAVE` privilege on the source server.

* `password`: String; required. Password for that account.

* `connect_timeout`: Int; required. Connection timeout in seconds.

* `read_timeout`: Int; required. Read timeout in seconds.

* `write_timeout`: Int; required. Write timeout in seconds.

Use either:

* `host` and `port`

* `dns_srv_name`

Do not use `localhost` for a TCP connection. `libmysqlclient` often treats `localhost` as a request for a Unix socket connection. When you require TCP, use `127.0.0.1`, a real host name, or an IP address.

## `connection.ssl`

`connection.ssl` configures SSL for the client connection. The whole `ssl` section is optional, but when present, `mode` is required and the rest are optional.

For configuration examples and recommended practices, see [SSL and TLS connections](ssl-tls-connections.md).

Fields (Type; Required):

* `mode`: String; required (when `ssl` is present). One of `disabled`, `preferred`, `required`, `verify_ca`, or `verify_identity`.

* `ca`: String; optional. Path to trusted CA file.

* `capath`: String; optional. Path to trusted CA directory.

* `crl`: String; optional. Path to certificate revocation list file.

* `crlpath`: String; optional. Path to certificate revocation list directory.

* `cert`: String; optional. Path to client certificate.

* `key`: String; optional. Path to private key for the client certificate.

* `cipher`: String; optional. Allowed SSL cipher list.

## `connection.tls`

`connection.tls` configures TLS 1.3. The JSON key for ciphersuites is `ciphersuites` (not `ca`). The whole `tls` section is optional.

For configuration examples and recommended practices, see [SSL and TLS connections](ssl-tls-connections.md).

Fields (Type; Required):

* `ciphersuites`: String; optional. List of permissible TLS 1.3 ciphersuites for encrypted connections.

* `version`: String; optional. List of permissible TLS protocols for encrypted connections.

## `replication`

`replication` controls replication behavior.

Fields (Type; Required):

* `server_id`: Int; required. Client server ID used during replication (required by protocol).

* `idle_time`: Int; required. Sleep time in seconds between reconnect attempts in `pull` mode. For tuning guidance, see [Best practice: idle_time](operational-behavior-reference.md#best-practice-idle_time) in Core behavior.

* `verify_checksum`: Boolean; required. When `true`, the client requests CRC32 and the server verifies event checksums before writing; when `false`, the client requests NONE. The application supports only these two algorithms (same as `binlog_checksum` on the source: CRC32 or NONE). See [Percona-Lab/percona-binlog-server](https://github.com/Percona-Lab/percona-binlog-server) `src/easymysql/connection.cpp` (`set_binlog_checksum`).

* `mode`: String; required. `position` or `gtid`. The upstream sample `main_config.json` uses `gtid`.

`mode` selects how Percona Binary Log Server tracks replication progress and requests events. The value that you choose controls how stored binlog files are organized and which search commands you can use.

Mode values:

* `position`: position-based replication. The server tracks progress by source binlog file name and byte offset. Stored files match the source's binlogs, so the stored files can be byte-for-byte copies. Use `position` when the source uses position-based replication, or when stored files must mirror the source layout. `search_by_gtid_set` is not supported for storage that was created in `position` mode.

* `gtid`: GTID-based replication. The server tracks progress by GTID set. Stored files do not need to match the source file names or layout, but the stored files contain the same transactions. Use `gtid` when the source uses GTID replication and you need `search_by_gtid_set` to find the smallest file set that covers a GTID set. Both `search_by_timestamp` and `search_by_gtid_set` are supported.

### `replication.rewrite` (optional)

`replication.rewrite` is optional, and valid only when `replication.mode` is `gtid`. Enable `replication.rewrite` for safe operation behind a failover-capable topology — see [Failover and topology awareness](operational-behavior-reference.md#failover-and-topology-awareness) in Core behavior.

When the `rewrite` section is present, the utility ignores the source's binlog file boundaries. The utility generates its own file name sequence from `base_file_name` and rotates to a new file when the current file reaches `file_size`. When the `rewrite` section is absent, the utility mirrors the source's file names and rotation layout. In that case, the utility writes one stored file for each source binlog file.

!!! warning "Source must run with `binlog_checksum = CRC32`"
    `replication.rewrite` requires that every source binlog file Percona Binary Log Server reads was generated with `@@global.binlog_checksum = CRC32` on the source. The server inspects the `FORMAT_DESCRIPTION` event at the start of each source binlog file and refuses to start (or stops mid-stream) when it reaches a file generated with `binlog_checksum = NONE`. The error log line is `rewrite is supported in gtid replication mode only when all events received from the MySQL server have checksums`, and the process exits with a non-zero status code. Set `@@global.binlog_checksum = CRC32` and run `FLUSH BINARY LOGS` on the source before pointing Percona Binary Log Server at the source. For the reason behind the constraint, see [Source-side checksum requirement](operational-behavior-reference.md#source-side-checksum-requirement) in Core behavior.

The rewrite logic preserves the logical-clock fields that downstream parallel replication relies on. The utility recomputes `sequence_number`, `last_committed`, and `transaction_length` in `GTID_LOG`, `ANONYMOUS_GTID_LOG`, and `GTID_TAGGED_LOG` events, recalculates the per-event checksum, and persists `last_sequence_number` in each binlog metadata file so that the values remain monotonic across server restarts. A replica reading the rewritten archive can therefore apply transactions in the same order and parallelism class as the source. For the event-class breakdown, see [Binlog rewriting internals](operational-behavior-reference.md#binlog-rewriting-internals) in Core behavior.

Fields (Type; Required):

* `base_file_name`: String; required within `rewrite`. Base name for rewritten binlog files (for example, `binlog` produces `binlog.000001`, `binlog.000002`, and so on).

* `file_size`: String; required within `rewrite`. Target size per rewritten file, with optional suffix (for example, `128M`, `1G`). The server rotates to a new file once the current one reaches `file_size`. Minimum accepted value is 1024 bytes.

Defined in the upstream [replication_config.hpp](https://github.com/Percona-Lab/percona-binlog-server/blob/main/src/binsrv/replication_config.hpp) and [rewrite_config.hpp](https://github.com/Percona-Lab/percona-binlog-server/blob/main/src/binsrv/rewrite_config.hpp).

## `keyring` (optional)

`keyring` points at the local JSON file that holds encryption keys.

The whole `keyring` section is optional.

The section is required when storage already contains at least one encrypted binlog file, or when `storage.encryption` is present.

Fields (Type; Required):

* `uri`: String; required (when `keyring` is present). URI of the keyring JSON file. The only supported scheme is `file://` on the local filesystem.

Example:

```json
"keyring": {
  "uri": "file:///var/lib/pbs/keyring/keyring_data.json"
}
```

Defined in the upstream [keyring_config.hpp](https://github.com/Percona-Lab/percona-binlog-server/blob/main/src/binsrv/keyring_config.hpp).

For the keyring file format, permissions, and validation rules, see [Binlog storage encryption](binlog-encryption.md).

## `storage`

`storage` defines where Percona Binary Log Server writes binlog files and how often the server flushes buffered data to that destination.

Fields (Type; Required):

* `backend`: String; required. Use `file` for a local directory or `s3` for Amazon S3 or an S3-compatible service. The `backend` value determines the format of `uri`.

* `uri`: String; required. Destination for stored binlog files. For `backend: "file"`, use `file://` with an absolute path. For Amazon S3, use `s3://`. For an S3-compatible endpoint, use `http://` or `https://`. See [Storage Reference](storage-reference.md) for URI formats and examples.

* `fs_buffer_directory`: String; optional. Local directory used to stage S3 (or S3-compatible) uploads. This setting applies when `backend` is `s3`. The directory is not the checkpointing buffer for unflushed events — unflushed events are held in the in-memory event buffer (see [Impact on the primary, memory footprint, and internal flow](operational-behavior-reference.md#impact-on-the-primary-memory-footprint-and-internal-flow)). Data enters `fs_buffer_directory` only when a flush occurs: the server writes the flushed bytes into a UUID-named temporary file under this directory and immediately uploads the cumulative S3 object from that file. The temporary file lives only while the corresponding binlog stream is open and is removed when the stream closes (for example, on rotation or graceful shutdown). When you omit the setting, the server creates a UUID-named subdirectory under the OS temporary directory (`$TMPDIR`, or `/tmp` on Linux when unset) and removes that subdirectory at clean shutdown. The path therefore changes on every run. A `fs_buffer_directory` set explicitly is used as-is and is never deleted by the server. Set this field explicitly in production so the buffer lives in a stable, predictable, and disk-safe location (see [Percona-Lab/percona-binlog-server](https://github.com/Percona-Lab/percona-binlog-server) `src/binsrv/s3_storage_backend.cpp`).

* `checkpoint_size`: String; optional. Buffered byte threshold that triggers a flush. Accepts a string with an optional suffix, for example `128M` or `1G`. Omit the key, or set the value to `0`, to disable size-based checkpointing.

* `checkpoint_interval`: String; optional. Time threshold, since the last flush, that triggers a flush when a new event is processed. Accepts a string with an optional suffix, for example `30s` or `5m`. The threshold is evaluated only on event arrival; if no new events are received, the buffer is not flushed even after the interval elapses. Omit the key, or set the value to `0`, to disable time-based checkpointing.

* `encryption`: Object; optional. When present, encrypts **new** binlog files and records per-file encryption envelopes. Omit the section to write new files without encryption. Keep [`keyring`](#keyring-optional) if existing files still have encryption metadata. See [`storage.encryption`](#storageencryption-optional) and [Binlog storage encryption](binlog-encryption.md).

Backend values:

* `file`: local filesystem storage. The tool writes binlog files directly to the path in `uri`. The `fs_buffer_directory` and checkpoint settings are not required for correctness. Checkpoints can still reduce memory use during large writes.

* `s3`: Amazon S3 or S3-compatible storage, for example MinIO. The tool buffers binlog data locally and then uploads the data according to `checkpoint_size` and `checkpoint_interval`. S3 does not support append, so each flush re-uploads the full object. See [S3 checkpointing behavior](storage-reference.md#s3-checkpointing-behavior) in Storage Reference.

## `storage.encryption` (optional)

`storage.encryption` configures encryption for **new** binlog files and the per-file encryption envelopes those files receive.

The whole `encryption` section is optional.

When the section is present, all three fields are required, and `keyring` must also be present.

The section applies to both `file` and `s3` backends.

Storage encryption settings differ from [TLS for the MySQL connection](ssl-tls-connections.md).

For keyring format, mixed encrypted and unencrypted files, and KEK rotation, see [Binlog storage encryption](binlog-encryption.md).

Fields (Type; Required):

* `format`: String; required (when `encryption` is present). Encryption format. The only supported value is `generic`.

* `kek_id`: String; required (when `encryption` is present). ID of the key-encryption key (KEK) in the keyring. The ID must exist in the keyring file.

* `cipher`: String; required (when `encryption` is present). Cipher name for binlog file data encryption. Must be a CTR mode cipher, for example `AES-256-CTR`. Configuration validation rejects other modes.

Example:

```json
"encryption": {
  "format": "generic",
  "kek_id": "<KEK_ID>",
  "cipher": "AES-256-CTR"
}
```

Omit `storage.encryption` when new files must be written without encryption.

Keep `keyring` when existing files in that storage still have encryption metadata.
