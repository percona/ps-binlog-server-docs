# Command reference

This page lists the supported commands and arguments. Use the tables for a quick lookup. Each operational mode is a command: `fetch`, `pull`, `search_by_timestamp`, `search_by_gtid_set`, `list`, `purge_binlogs`, and `version`. [Install](install.md) only covers how to obtain the binary. [Core behavior](operational-behavior-reference.md) covers reconnect logic and timeouts.

## Commands and arguments

| Command | Arguments | Description |
|--------|-----------|-------------|
| `version` | (none) | Prints the semantic version and exits with status 0. |
| `fetch` | `<json_config_file>` | Runs a one-time collection. Reads all available binlog events from the source, writes the events to storage, and then exits. |
| `pull` | `<json_config_file>` | Runs continuous collection. Reads binlog events, waits for more events, reconnects when needed, and runs until you stop the process. |
| `search_by_timestamp` | `<json_config_file>` `<timestamp>` | Returns the metadata of stored binlog files, from the oldest up to and including the last file whose `min_timestamp` is at or before the given ISO timestamp. Returns `Timestamp is too old` if even the oldest file's `min_timestamp` is greater than the target. Not a minimal cover. |
| `search_by_gtid_set` | `<json_config_file>` `<gtid_set>` | Returns the metadata of the smallest set of stored binlog files that cover the given GTID set. Supported only in GTID mode. |
| `list` | `<json_config_file>` | Returns the metadata of every stored binlog file in chronological order. Returns `status: success` with an empty `result` array when storage is empty. |
| `purge_binlogs` | `<json_config_file>` `<binlog_name>` | Removes every stored binlog file with a sequence number at or below the given name. Refuses to remove the current tail file. Run with Percona Binary Log Server stopped. |

| Argument | Description |
|----------|-------------|
| `<json_config_file>` | Path to the JSON configuration file. |
| `<timestamp>` | ISO timestamp (for example, `2026-02-10T14:30:00`). |
| `<gtid_set>` | GTID set (for example, `11111111-aaaa-1111-aaaa-111111111111:1:3,22222222-bbbb-2222-bbbb-222222222222:1-6`). |
| `<binlog_name>` | Stored binlog file name without a path (for example, `binlog.000002`). |

## Operation modes summary

| Mode | When to use | Behavior |
|------|-------------|----------|
| `version` | Check the installed version. | Prints the version and exits with status 0. |
| `fetch` | One-time or on-demand archive. | Connects to the source, reads all current events, writes the events to storage, and exits. Stops on any error. |
| `pull` | Continuous binlog collection. | Connects to the source, reads events, and waits for more events. Reconnects after a timeout or network error. Runs until you stop the process or until a fatal error occurs. |
| `search_by_timestamp` | Find files for point-in-time recovery by time. | Reads storage and returns the metadata of stored files (from the oldest) selected by `min_timestamp`. |
| `search_by_gtid_set` | Find a minimal cover of files for a GTID set. | Reads storage and returns the metadata of a minimal cover of stored files for the GTID set. Requires GTID-based storage. |
| `list` | Enumerate the archive without a filter. | Reads storage and returns the metadata of every stored binlog file in chronological order. Returns `status: success` with an empty `result` array when storage is empty (use to distinguish empty storage from a corrupted archive). |
| `purge_binlogs` | Free space by deleting older files. | Removes every stored binlog file at or below the supplied target name (a contiguous prefix). Refuses to remove the current tail. Atomic at the index level. May return `status: warning` if payload deletion fails after the index commit (manual cleanup required). Running while `fetch` or `pull` is in progress on the same archive may corrupt the archive. |

## Command syntax

```bash
./binlog_server version
./binlog_server fetch <json_config_file>
./binlog_server pull <json_config_file>
./binlog_server search_by_timestamp <json_config_file> <timestamp>
./binlog_server search_by_gtid_set <json_config_file> <gtid_set>
./binlog_server list <json_config_file>
./binlog_server purge_binlogs <json_config_file> <binlog_name>
```

## `version`

`version` prints the semantic version that is embedded in the binary and then exits with status `0`.

Example:

```bash
./binlog_server version
```

Example output:

```text
0.4.1
```

## `fetch`

`fetch` connects to the MySQL or MySQL-compatible source, copies every [binary log](glossary.md#binary-log) event available on the source to storage, and then exits.

Use `fetch` for a one-time archive run.

Behavior summary:

* Reads existing binlogs from the source.

* Exits after the last available event is written.

* Stops on the first error, for example a network failure or a storage failure.

* Resumes from storage on re-run. After an error, re-run `fetch` against the same storage to continue from the last flushed transaction. The tool does not retry within a run.

## `pull`

`pull` connects to the MySQL or MySQL-compatible source and follows the live binlog stream. The tool writes events to your configured storage until you stop the process or a non-recoverable error occurs. When the stream pauses or the connection fails, the server reconnects and resumes from the last position saved in storage.

Use `pull` for continuous collection.

Behavior summary:

* Produces an archive that follows the source. Network speed and storage speed affect how closely the archive follows the source.

* Retries transient failures. The timing is controlled by `connection.read_timeout`, `replication.idle_time`, and related settings. For details, see [Network failure and reconnect behavior](operational-behavior-reference.md#network-failure-and-reconnect-behavior) and [Best practice: idle_time](operational-behavior-reference.md#best-practice-idle_time).

* Exits on a fatal error, for example a full volume or an unrecoverable protocol error. For details, see Core behavior.

## `search_by_timestamp`

`search_by_timestamp` walks the stored binlog records in order from the oldest and returns every record up to and including the last one whose `min_timestamp` is at or before the timestamp that you supply. As soon as the command encounters a record whose `min_timestamp` is greater than your timestamp, the walk stops. The result is therefore the first N records of the binlog metadata list, not a minimal cover. If even the oldest record's `min_timestamp` is greater than the requested timestamp, the command returns `Timestamp is too old`.

Example:

```bash
./binlog_server search_by_timestamp config.json 2026-02-10T14:30:00
```

Example successful output:

```json
{
  "status": "success",
  "result": [
    {
      "name": "binlog.000001",
      "size": 134217728,
      "uri": "s3://binsrv-bucket/storage/binlog.000001",
      "min_timestamp": "2026-02-09T17:22:01",
      "max_timestamp": "2026-02-09T17:22:08",
      "previous_gtids": "",
      "added_gtids": "11111111-aaaa-1111-aaaa-111111111111:1-123456"
    },
    {
      "name": "binlog.000002",
      "size": 134217728,
      "uri": "s3://binsrv-bucket/storage/binlog.000002",
      "min_timestamp": "2026-02-09T17:22:08",
      "max_timestamp": "2026-02-09T17:22:09",
      "previous_gtids": "11111111-aaaa-1111-aaaa-111111111111:1-123456",
      "added_gtids": "11111111-aaaa-1111-aaaa-111111111111:123457-246912"
    }
  ]
}
```

Possible error messages include:

* `Invalid timestamp format`

* `Binlog storage is empty`

* `Timestamp is too old`

## `search_by_gtid_set`

`search_by_gtid_set` returns the smallest set of stored binlog metadata records that cover the GTID set that you supply. The command requires storage that was created in GTID-based replication mode.

Example:

```bash
./binlog_server search_by_gtid_set config.json 11111111-aaaa-1111-aaaa-111111111111:10-20
```

Example successful output:

```json
{
  "status": "success",
  "result": [
    {
      "name": "binlog.000001",
      "size": 134217728,
      "uri": "s3://binsrv-bucket/storage/binlog.000001",
      "min_timestamp": "2026-02-09T17:22:01",
      "max_timestamp": "2026-02-09T17:22:08",
      "previous_gtids": "",
      "added_gtids": "11111111-aaaa-1111-aaaa-111111111111:1-123456"
    }
  ]
}
```

Possible error messages include:

* `cannot parse GTID set`

* `Binlog storage is empty`

* `The specified GTID set cannot be covered`

* `GTID set search is not supported in storages created in position-based replication mode`

## `list`

`list` reads stored metadata and returns every binlog file currently in storage, in chronological order. The output JSON uses the same per-file schema as `search_by_timestamp` and `search_by_gtid_set` (`name`, `size`, `uri`, `previous_gtids`, `added_gtids`, `min_timestamp`, `max_timestamp`, and optional `encryption`). Unlike the search commands, `list` returns `status: success` with an empty `result` array on an empty storage instead of returning an error. Use `list` to enumerate the archive without applying a filter, and to distinguish an empty storage from a corrupted one.

`list` opens storage in querying-only mode. The command does not write to storage, does not block other readers, and is safe to run while a `fetch` or `pull` process is active.

Example:

```bash
./binlog_server list config.json
```

Example successful output:

```json
{
  "status": "success",
  "result": [
    {
      "name": "binlog.000001",
      "size": 134217728,
      "uri": "s3://binsrv-bucket/storage/binlog.000001",
      "min_timestamp": "2026-02-09T17:22:01",
      "max_timestamp": "2026-02-09T17:22:08",
      "previous_gtids": "",
      "added_gtids": "11111111-aaaa-1111-aaaa-111111111111:1-123456"
    },
    {
      "name": "binlog.000002",
      "size": 134217728,
      "uri": "s3://binsrv-bucket/storage/binlog.000002",
      "min_timestamp": "2026-02-09T17:22:08",
      "max_timestamp": "2026-02-09T17:22:09",
      "previous_gtids": "11111111-aaaa-1111-aaaa-111111111111:1-123456",
      "added_gtids": "11111111-aaaa-1111-aaaa-111111111111:123457-246912"
    }
  ]
}
```

Example empty-storage output:

```json
{
  "status": "success",
  "result": []
}
```

The `previous_gtids` and `added_gtids` fields are emitted as empty strings on storage created in position-based replication mode.

When storage has encryption metadata, each per-file entry also includes an optional `encryption` object.

That object matches the sidecar metadata shape (`file_key_envelope` and `file_data_envelope`).

Storage without encryption metadata omits the field.

See [Binlog storage encryption](binlog-encryption.md#command-json-output).

Example per-file `encryption` fragment:

```json
"encryption": {
  "file_key_envelope": {
    "kek_id": "<KEK_ID>",
    "data_hex": "<WRAPPED_FILE_KEY_HEX>",
    "iv_hex": "<IV_HEX>",
    "tag_hex": "<TAG_HEX>"
  },
  "file_data_envelope": {
    "cipher": "AES-256-CTR",
    "iv_hex": "<IV_HEX>"
  }
}
```

## `purge_binlogs`

`purge_binlogs` removes every binlog file with a sequence number less than or equal to the target name, together with each file's metadata sidecar. The target is a stored binlog file name without a path (for example, `binlog.000002`). The current tail file (the most recent one) cannot be purged, because emptying storage would lose the resume position and force the next `fetch` or `pull` to re-stream from the source's earliest retained binlog.

Run `purge_binlogs` only when no `fetch` or `pull` process is writing to the same storage. The mode rewrites `binlog.index`, and a concurrent writer against the same storage races with that rewrite and can corrupt the archive. The constraint is per-storage: a separate Percona Binary Log Server instance that writes to a different `storage.uri` (a different absolute path for the `file` backend, or a different bucket-and-prefix pair for the `s3` backend) is safe to leave running. See [Safe-deletion rules](operations.md#safe-deletion-rules) in Operations.

Example:

```bash
./binlog_server purge_binlogs config.json binlog.000002
```

If storage contains `binlog.000001`, `binlog.000002`, and `binlog.000003`, the example above deletes `binlog.000001` and `binlog.000002` and leaves `binlog.000003` in storage.

Example successful output:

```json
{
  "status": "success",
  "result": [
    {
      "name": "binlog.000001",
      "size": 134217728,
      "uri": "s3://binsrv-bucket/storage/binlog.000001",
      "min_timestamp": "2026-02-09T17:22:01",
      "max_timestamp": "2026-02-09T17:22:08",
      "previous_gtids": "",
      "added_gtids": "11111111-aaaa-1111-aaaa-111111111111:1-123456"
    },
    {
      "name": "binlog.000002",
      "size": 134217728,
      "uri": "s3://binsrv-bucket/storage/binlog.000002",
      "min_timestamp": "2026-02-09T17:22:08",
      "max_timestamp": "2026-02-09T17:22:09",
      "previous_gtids": "11111111-aaaa-1111-aaaa-111111111111:1-123456",
      "added_gtids": "11111111-aaaa-1111-aaaa-111111111111:123457-246912"
    }
  ]
}
```

The `result` array lists the metadata of every binlog file that the command removed.

Possible error messages (returned with `status: error`; no files were touched):

* `binlog composite name is too short`

* `cannot purge: binlog storage is empty`

* `cannot purge: target binlog name has a different base name than the binlog records in the storage`

* `cannot purge: target binlog name is not present in the storage`

* `cannot purge: target is the current tail binlog file; at least one binlog file must remain in the storage to preserve the resume position`

Partial-success warning. The command rewrites `binlog.index` first, then deletes the underlying payload and metadata files in a best-effort batch. If the index rewrite succeeds but one or more deletions fail, the command returns `status: warning` with the metadata of the targeted files in `result` and the underlying error in `message`. The storage is then in a partial state: the index says the files are gone, but their payload or metadata sidecars still exist on disk. Percona Binary Log Server's startup validators detect that state and refuse to open the storage on the next run. Manually delete the leftover files (named in `result`) before restarting Percona Binary Log Server.

Example partial-success output:

```json
{
  "status": "warning",
  "result": [
    {
      "name": "binlog.000001",
      "size": 134217728,
      "uri": "s3://binsrv-bucket/storage/binlog.000001",
      "min_timestamp": "2026-02-09T17:22:01",
      "max_timestamp": "2026-02-09T17:22:08",
      "previous_gtids": "",
      "added_gtids": "11111111-aaaa-1111-aaaa-111111111111:1-123456"
    },
    {
      "name": "binlog.000002",
      "size": 134217728,
      "uri": "s3://binsrv-bucket/storage/binlog.000002",
      "min_timestamp": "2026-02-09T17:22:08",
      "max_timestamp": "2026-02-09T17:22:09",
      "previous_gtids": "11111111-aaaa-1111-aaaa-111111111111:1-123456",
      "added_gtids": "11111111-aaaa-1111-aaaa-111111111111:123457-246912"
    }
  ],
  "message": "cannot delete binlog.000001"
}
```

For the algorithm and recovery details, see [`purge_binlogs` mode](operational-behavior-reference.md#purge_binlogs-mode) in Core behavior.
