# Command Reference

Percona Binary Log Server supports the following commands. Use the tables in this section to find a command or argument quickly.

## Commands and arguments

| Command | Arguments | Description |
|--------|-----------|-------------|
| `version` | (none) | Prints the semantic version and exits with status 0. |
| `fetch` | `<json_config_file>` | One-time collection: reads all available binlog events from the source, writes to storage, then exits. |
| `pull` | `<json_config_file>` | Continuous collection: reads binlog events, waits for more, reconnects as needed, runs until stopped. |
| `search_by_timestamp` | `<json_config_file>` `<timestamp>` | Returns stored binlog files that contain events with timestamp ≤ the given ISO timestamp. |
| `search_by_gtid_set` | `<json_config_file>` `<gtid_set>` | Returns the minimal set of stored binlog files that cover the given GTID set (GTID mode only). |

| Argument | Description |
|----------|-------------|
| `<json_config_file>` | Path to the JSON configuration file. |
| `<timestamp>` | ISO timestamp (for example, `2026-02-10T14:30:00`). |
| `<gtid_set>` | GTID set (for example, `11111111-aaaa-1111-aaaa-111111111111:1:3,22222222-bbbb-2222-bbbb-222222222222:1-6`). |

## Operation modes summary

| Mode | When to use | Behavior |
|------|-------------|----------|
| `version` | Check installed version. | Prints version, exits 0. |
| `fetch` | One-time or on-demand archive. | Connects, reads all current events, writes to storage, exits. Stops on any error. |
| `pull` | Continuous binlog collection. | Connects, reads events, waits for more; reconnects after timeout or network error. Runs until stopped or fatal error. |
| `search_by_timestamp` | Find files for point-in-time recovery by time. | Reads metadata, returns list of stored files with events up to the given timestamp. |
| `search_by_gtid_set` | Find minimal file set for a GTID set. | Reads metadata, returns minimal set of stored files covering the GTID set. Requires GTID-based storage. |

## Command syntax

```bash
./binlog_server version
./binlog_server fetch <json_config_file>
./binlog_server pull <json_config_file>
./binlog_server search_by_timestamp <json_config_file> <timestamp>
./binlog_server search_by_gtid_set <json_config_file> <gtid_set>
```

## `version`

`version` prints the semantic version embedded in the binary and exits with status code `0`.

Example:

```bash
./binlog_server version
```

Example output:

```text
0.1.0
```

## `fetch`

`fetch` connects to the remote MySQL server, reads all binary log events currently available on that server, stores the data, then exits.

Use `fetch` when a one-time archive run is needed.

Behavior summary:

* reading existing binary logs from the source server

* exiting after the last available event

* stopping immediately on errors such as network loss or storage failure

## `pull`

`pull` connects to the remote MySQL server, reads binary log events, waits for more events, disconnects after `connection.read_timeout`, sleeps for `replication.idle_time`, then reconnects and continues.

Use `pull` when continuous collection is needed.

Behavior summary:

* following new binary log events over time

* retrying after network-related failures

* stopping on serious failures such as storage problems

## `search_by_timestamp`

`search_by_timestamp` returns the list of saved binary log files that contain at least one event with a timestamp less than or equal to the supplied timestamp.

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
      "initial_gtids": "",
      "added_gtids": "11111111-aaaa-1111-aaaa-111111111111:1-123456"
    },
    {
      "name": "binlog.000002",
      "size": 134217728,
      "uri": "s3://binsrv-bucket/storage/binlog.000002",
      "min_timestamp": "2026-02-09T17:22:08",
      "max_timestamp": "2026-02-09T17:22:09",
      "initial_gtids": "11111111-aaaa-1111-aaaa-111111111111:1-123456",
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

`search_by_gtid_set` returns the minimum set of saved binary log files required to cover the supplied GTID set. This mode requires storage created with GTID-based replication.

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
      "initial_gtids": "",
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
