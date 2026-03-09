# Get Started With Percona Binary Log Server

This page shows a basic first run with local filesystem storage.

Transaction safety: The server writes to storage only at [transaction boundary](glossary.md#transaction-boundary) points. Stored binlog files do not contain half-written transactions. If the process stops (gracefully or not), the last visible data ends at the last flushed transaction and a new run [resumes](glossary.md#resume) from there. See [Core behavior](operational-behavior-reference.md) for details.

Before starting, make sure the following requirements are met:

* having access to a Percona Binary Log Server binary or Docker deployment (see [Install Percona Binary Log Server](install.md))

* having access to a MySQL server that exposes binary logs

* having a MySQL account with [REPLICATION SLAVE](glossary.md#replication-slave) privilege

## Create A Configuration File

Create a file named `config.json` with content similar to the following example:

```json
{
  "logger": {
    "level": "info",
    "file": "binsrv.log"
  },
  "connection": {
    "host": "127.0.0.1",
    "port": 3306,
    "user": "rpl_user",
    "password": "rpl_password",
    "connect_timeout": 20,
    "read_timeout": 60,
    "write_timeout": 60
  },
  "replication": {
    "server_id": 42,
    "idle_time": 10,
    "verify_checksum": true,
    "mode": "position"
  },
  "storage": {
    "backend": "file",
    "uri": "file:///var/lib/binlog-server"
  }
}
```

## Run A One-Time Collection

Use [fetch](glossary.md#fetch) when a single archive run is needed:

```bash
./binlog_server fetch config.json
```

`fetch` reads all currently available binary log events from the source server, stores the data, then exits.

## Run Continuous Collection

Use [pull](glossary.md#pull) when ongoing collection is needed:

```bash
./binlog_server pull config.json
```

`pull` reads available binary log events, waits for new events, reconnects when needed, and continues until a user or service stops the process.

## Next Steps

Use the following pages for deeper detail:

* [Core behavior](operational-behavior-reference.md) — transaction-safe writes, metadata, resume, graceful shutdown

* [Operations](operations.md) — logging, monitoring, and alerting for production

* [Configuration Reference](configuration-reference.md)

* [Command Reference](command-reference.md)

* [Storage Reference](storage-reference.md)
