# Get started with Percona Binary Log Server

This page walks you through your first run with local filesystem storage. You need one configuration file and one command.

Before you start, make sure you have:

* A Percona Binary Log Server binary or Docker image ([Install](install.md))

* A MySQL or MySQL-compatible server with binary logging enabled

* An account with [REPLICATION SLAVE](glossary.md#replication-slave) on that server

## Create a configuration file

Save the following as `config.json`:

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
    "uri": "file:///var/lib/binlog-server/data"
  }
}
```

## Run a one-time collection

For a single archive run, use [fetch](glossary.md#fetch):

```bash
./binlog_server fetch config.json
```

`fetch` copies every [binary log](glossary.md#binary-log) event available on the source, writes each event to storage, and then exits.

## Run continuous collection

For ongoing collection, use [pull](glossary.md#pull):

```bash
./binlog_server pull config.json
```

`pull` streams binlog events as the source produces them. `pull` reconnects after a transient failure and keeps running until you stop the process.

## Next steps

For more detail, see:

* [Core behavior](operational-behavior-reference.md) — transaction-safe writes, automatic storage recovery, metadata, resume, graceful shutdown

* [Operations](operations.md) — logging, monitoring, and alerting for production

* [Configuration Reference](configuration-reference.md)

* [Command Reference](command-reference.md)

* [Storage Reference](storage-reference.md)
