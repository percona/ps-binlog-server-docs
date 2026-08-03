# Install Percona Binary Log Server with Docker

Run Percona Binary Log Server from the prebuilt image on Docker Hub. This page shows how to pull the image, prepare a configuration file, and run each operational mode: `fetch`, `pull`, `search_by_timestamp`, `search_by_gtid_set`, and `version`. For the JSON schema, see [Configuration Reference](configuration-reference.md). For the product overview, see [Percona Binary Log Server](index.md).

## Prerequisites

* A working Docker engine, such as Docker Desktop, Docker CE, or a compatible runtime.

* A network path from the container to the MySQL or MySQL-compatible source on its listening port (typically `3306`).

* A JSON configuration file on the host. See [Configuration Reference](configuration-reference.md) and [Get Started](get-started.md).

* For an `s3` backend: AWS credentials (an access key and a secret key) and a reachable S3 or S3-compatible endpoint.

## Prepare the source server

Percona Binary Log Server connects to the source as a replication client. Before you start the container, make sure that the source server can stream [binary logs](glossary.md#binary-log) and that you have created a dedicated replication account.

### Enable binary logging

Binary logging must be on. Check binary logging on the source:

```sql
SHOW VARIABLES LIKE 'log_bin';
```

`log_bin` must be `ON`. If `log_bin` is not `ON`, enable binary logging in the source's configuration (for example, `log_bin = mysql-bin` in `my.cnf`) and restart the server.

If you plan to use `replication.mode: gtid`, also confirm `gtid_mode = ON` and `enforce_gtid_consistency = ON` on the source. Position mode (`replication.mode: position`) does not require GTID.

### Create a replication account

Create an account that has the `REPLICATION SLAVE` privilege. Use the account credentials in `connection.user` and `connection.password`. The `REPLICATION CLIENT` privilege is not required.

```sql
CREATE USER 'rpl_user'@'%' IDENTIFIED BY 'rpl_password';
GRANT REPLICATION SLAVE ON *.* TO 'rpl_user'@'%';
FLUSH PRIVILEGES;
```

Restrict the host pattern (`'%'`) so that the pattern matches only the host where the container will run.

### Keep binlogs long enough to resume

When the container stops or the connection fails, Percona Binary Log Server resumes from the last flushed position after the next restart. Resume fails if the source rotated and removed binlog files past that position while the server was stopped. Set the source's retention to cover your maximum expected downtime plus a safety margin. For example, on MySQL 8.0:

```sql
SHOW VARIABLES LIKE 'binlog_expire_logs_seconds';
```

The default value is 2,592,000 seconds (30 days). If you shorten this value, make sure the new retention still covers your restart SLO.

### Replication server ID

`binlog_server` uses `replication.server_id` from the JSON configuration as its replication client ID. Choose a value that does not match the source's own `server_id`. The value must also differ from the `server_id` of every other replica that is attached to the source. See [`replication.server_id`](configuration-reference.md#replication).

## Image

The image is published on Docker Hub as [`perconalab/percona-binlog-server`](https://hub.docker.com/r/perconalab/percona-binlog-server). You can pull the `latest` tag, a major-minor tag (for example, `0.4`), or an exact patch tag (for example, `0.4.1`). Multi-architecture manifests cover both `amd64` and `arm64`.

```bash
docker pull perconalab/percona-binlog-server:latest
```

```bash
docker pull perconalab/percona-binlog-server:0.4.1
```

## In-container paths used in this page

The examples in this section assume the in-container paths listed here. The paths in your configuration file must match the mount points that you pass to `docker run`.

| Purpose | In-container path | Typical config key |
|---------|-------------------|--------------------|
| JSON configuration file | `/etc/binlog-server/config.json` | (command-line argument) |
| File-backend storage directory | `/var/lib/binlog-server/data` | `storage.uri = file:///var/lib/binlog-server/data` |
| S3 buffer directory | `/var/lib/binlog-server/buffer` | `storage.fs_buffer_directory` |
| Log file | `/var/log/binlog-server/binsrv.log` | `logger.file` |
| TLS/SSL certificates | `/etc/mysql/ssl/` | `connection.ssl.ca`, `cert`, `key`, and so on |
| Keyring JSON file | `/var/lib/pbs/keyring/keyring_data.json` | `keyring.uri = file:///var/lib/pbs/keyring/keyring_data.json` |

## Container user and host volume ownership

The container runs as the non-root `pbs` user (UID 1001). The image pre-creates `/var/lib/binlog-server/data`, `/var/lib/binlog-server/buffer`, and `/var/log/binlog-server` with `1001:1001` ownership and mode `0775`.

A named Docker volume inherits those permissions on first attach and needs no extra setup. A bind mount replaces the in-container directory with a host directory whose ownership is set by the host, which is rarely UID 1001. Set the host directory's ownership before the **first run** that uses the bind mount:

```bash
chown 1001:1001 /srv/binlogs /var/log/binlog-server
```

The requirement applies to every command that writes to a bind-mounted path, starting with the first `fetch`. Without the `chown`, the run fails with a permission error. If you override the container user with `--user`, set the host ownership to match the user you specify.

## Verify the image (`version`)

`version` prints the semantic version built into the image and exits.

```bash
docker run --rm perconalab/percona-binlog-server:latest binlog_server version
```

You can also use the `version` command as a lightweight health check in CI or in an orchestration system.

## One-time collection (`fetch`) with file backend

`fetch` connects to the source, copies every binlog event available to storage, and then exits. Mount the configuration file as read-only and the storage directory as read-write.

```bash
docker run --rm \
  -v "$(pwd)/config.json:/etc/binlog-server/config.json:ro" \
  -v /srv/binlogs:/var/lib/binlog-server/data \
  -v /var/log/binlog-server:/var/log/binlog-server \
  perconalab/percona-binlog-server:latest \
  binlog_server fetch /etc/binlog-server/config.json
```

The archived files are written to the host path `/srv/binlogs`. Set `storage.uri` in `config.json` to `file:///var/lib/binlog-server/data` so that the in-container path matches the mount point. The log mount lets you inspect the run's log output on the host after the container exits.

## Continuous collection (`pull`) with file backend

`pull` runs until you stop the container. Run the container in detached mode with an explicit restart policy. Set a stop timeout that is long enough to cover the graceful-shutdown window. For details, see [Graceful shutdown](operational-behavior-reference.md#graceful-shutdown) in Core behavior.

```bash
docker run -d --name binlog-server \
  --restart unless-stopped \
  --stop-signal SIGTERM \
  --stop-timeout 120 \
  -v "$(pwd)/config.json:/etc/binlog-server/config.json:ro" \
  -v /srv/binlogs:/var/lib/binlog-server/data \
  -v /var/log/binlog-server:/var/log/binlog-server \
  perconalab/percona-binlog-server:0.4.1 \
  binlog_server pull /etc/binlog-server/config.json
```

Set `--stop-timeout` to at least `connection.read_timeout` plus a small buffer of one to two seconds. If your `read_timeout` is larger, raise `--stop-timeout` to match.

## Continuous collection (`pull`) with S3 backend

When you set `backend: "s3"`, the archive is stored in S3. Always set `storage.fs_buffer_directory` explicitly in containers — do not rely on the default. When omitted, the server creates a UUID-named subdirectory under the OS temporary directory (`$TMPDIR`, or `/tmp` on Linux when unset) inside the container, and removes that subdirectory at clean shutdown. The path lives in the container's writable layer unless a volume is mounted at `$TMPDIR`, which means the buffer is ephemeral and any in-flight upload data is lost when the container is removed. `storage.fs_buffer_directory` is staging for S3 uploads, not a buffer for unflushed events, and the server does not read this directory back during recovery (the resume position lives in S3 metadata). Set `storage.fs_buffer_directory` to a path on a mounted volume that provides predictable ownership and **adequate free space**: the per-stream temporary file accumulates the flushed bytes for the current binlog file and can grow as large as one rotated binlog (controlled by `replication.rewrite.file_size` in `gtid` mode, or the source's binlog file size when mirroring). A `fs_buffer_directory` set explicitly is never deleted by the server.

AWS credentials must be embedded in `storage.uri` itself, for example `s3://<access_key_id>:<secret_access_key>@<bucket>.<region>/<path>`. See [Storage Reference](storage-reference.md) for URI formats. Any URI-reserved characters in the access key or secret must be percent-encoded before being embedded. The most important case is `/` as `%2F` (common in AWS secret access keys). Also encode `+` as `%2B`, `=` as `%3D`, `@` as `%40`, and `:` as `%3A`. Percona Binary Log Server uses these URI credentials directly and does **not** consult the AWS default credential chain. Setting `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, or `AWS_REGION` in the container environment has no effect. Relying on an instance profile, IRSA on EKS, IMDS, or `~/.aws/credentials` has no effect either. Because `storage.uri` contains the secret, treat `config.json` as a secret file. Mount `config.json` from a Docker secret or a Kubernetes `Secret`. Do not commit `config.json` to a source repository.

```bash
docker run -d --name binlog-server \
  --restart unless-stopped \
  --stop-signal SIGTERM \
  --stop-timeout 120 \
  -v "$(pwd)/config.json:/etc/binlog-server/config.json:ro" \
  -v binlog-buffer:/var/lib/binlog-server/buffer \
  -v /var/log/binlog-server:/var/log/binlog-server \
  perconalab/percona-binlog-server:latest \
  binlog_server pull /etc/binlog-server/config.json
```

The `config.json` mounted above must contain the credentials inside `storage.uri`. Set `storage.fs_buffer_directory` in `config.json` to `/var/lib/binlog-server/buffer` so that the path matches the named-volume mount. Set `logger.file` to `/var/log/binlog-server/binsrv.log` so you can inspect the logs on the host.

## Search stored binlogs

Search commands only read existing metadata. Mount the storage directory as read-only.

Search by timestamp:

```bash
docker run --rm \
  -v "$(pwd)/config.json:/etc/binlog-server/config.json:ro" \
  -v /srv/binlogs:/var/lib/binlog-server/data:ro \
  perconalab/percona-binlog-server:latest \
  binlog_server search_by_timestamp /etc/binlog-server/config.json 2026-02-10T14:30:00
```

Search by GTID set (requires storage created with `replication.mode: gtid`):

```bash
docker run --rm \
  -v "$(pwd)/config.json:/etc/binlog-server/config.json:ro" \
  -v /srv/binlogs:/var/lib/binlog-server/data:ro \
  perconalab/percona-binlog-server:latest \
  binlog_server search_by_gtid_set /etc/binlog-server/config.json \
  11111111-aaaa-1111-aaaa-111111111111:1-200
```

For expected output and error messages, see [Command Reference](command-reference.md).

## TLS and SSL

Mount your certificate directory as read-only. Set the `connection.ssl.*` keys in `config.json` to the in-container paths.

```bash
docker run -d --name binlog-server \
  --restart unless-stopped \
  --stop-signal SIGTERM \
  --stop-timeout 120 \
  -v "$(pwd)/config.json:/etc/binlog-server/config.json:ro" \
  -v /etc/mysql/ssl:/etc/mysql/ssl:ro \
  -v /srv/binlogs:/var/lib/binlog-server/data \
  perconalab/percona-binlog-server:latest \
  binlog_server pull /etc/binlog-server/config.json
```

The `connection.ssl.ca`, `connection.ssl.cert`, `connection.ssl.key`, and related fields must point to paths under `/etc/mysql/ssl/`, or under whichever directory you use as the mount point for your certificates. See [`connection.ssl`](configuration-reference.md#connectionssl) and [SSL and TLS connections](ssl-tls-connections.md).

To use storage encryption inside the container, mount a keyring file, set `keyring.uri` to that path, and set `storage.encryption` when new files must be encrypted.

See [Binlog storage encryption](binlog-encryption.md).

## Networking

* When the source runs outside the Docker host, set `connection.host` to the routable IP address or hostname of the source. Do not use `127.0.0.1` or `localhost` inside a container, because these addresses resolve to the container itself.

* When the source runs on the Docker host, choose one of two options. Either add `--add-host host.docker.internal:host-gateway` and set `connection.host` to `host.docker.internal`. On Linux, you can also run the container with `--network host` and set `connection.host` to the host IP address.

* You do not need to publish any ports. Percona Binary Log Server only makes outbound connections.

## Graceful stop

`docker stop` sends SIGTERM to the `binlog_server` process. The process runs as PID 1 in the image. The signal handler flushes data through the last completed transaction and then exits. Storage remains consistent. See [Graceful shutdown](operational-behavior-reference.md#graceful-shutdown).

```bash
docker stop binlog-server
```

!!! warning "Avoid `docker kill -s SIGKILL`"
    Do not force-kill the container. A force-kill happens when you send `SIGKILL`, or when the container runs past the `--stop-timeout` value. A force-kill can interrupt a flush and drop unwritten data. See [Graceful termination](index.md#transaction-safe-writes) and [Core behavior](operational-behavior-reference.md#transaction-atomicity-and-partial-writes).

## Inspect logs

When `logger.file` is an empty string, the tool writes logs to the container's stdout. You can view the logs through `docker logs`.

```bash
docker logs -f binlog-server
```

When `logger.file` is a path such as `/var/log/binlog-server/binsrv.log`, the tool writes logs to that file inside the container. Mount a host directory on the parent directory so that you can read the log file from the host.

## Upgrade to a different image

Pull the target tag, stop and remove the container, and then start the container again with the same volumes and command. The subsequent run uses the storage metadata to continue from the position where the previous run stopped.

```bash
docker pull perconalab/percona-binlog-server:0.4.1
docker stop binlog-server
docker rm binlog-server
docker run -d --name binlog-server \
  --restart unless-stopped \
  --stop-signal SIGTERM \
  --stop-timeout 120 \
  -v "$(pwd)/config.json:/etc/binlog-server/config.json:ro" \
  -v /srv/binlogs:/var/lib/binlog-server/data \
  -v /var/log/binlog-server:/var/log/binlog-server \
  perconalab/percona-binlog-server:0.4.1 \
  binlog_server pull /etc/binlog-server/config.json
```

For how resume works, see [Resume](operational-behavior-reference.md) in Core behavior.

## Docker Compose example (`pull` + S3)

AWS credentials must live inside `config.json` (in `storage.uri`) — see the prose above. The Compose service therefore does not declare any AWS-related environment variables, because the server does not read them.

```yaml
services:
  binlog-server:
    image: perconalab/percona-binlog-server:0.4.1
    command: ["binlog_server", "pull", "/etc/binlog-server/config.json"]
    restart: unless-stopped
    stop_signal: SIGTERM
    stop_grace_period: 2m
    volumes:
      - ./config.json:/etc/binlog-server/config.json:ro
      - binlog-buffer:/var/lib/binlog-server/buffer

volumes:
  binlog-buffer:
```

Treat `config.json` as a secret: use Compose secrets, a sealed Kubernetes `Secret`, or another secret-management workflow rather than committing the file to a source repository.

## Troubleshooting

For interactive debugging, run `docker run --rm -it perconalab/percona-binlog-server:latest` to get a shell inside the container. The image's default command is `/bin/bash`, so no arguments are needed. Use the shell to inspect paths, permissions, the installed `binlog_server` version, or any other in-container state.

* Configuration path not found. The path that you pass after the subcommand is resolved inside the container. Confirm that the `-v .../config.json:/etc/binlog-server/config.json:ro` mount is present and that the command argument matches the in-container path.

* Permission denied on a host volume. The container runs as the non-root `pbs` user (UID 1001). Host-mounted directories must be writable by UID 1001 — set ownership with `chown 1001:1001 <dir>` before the first run. If you override the container user with `--user`, adjust the host ownership to match the user you specify.

* Cannot connect to the source server. Verify that `connection.host` is reachable from inside the container. The `ping` command is not available inside the image, so start a temporary debug container on the same network. Also check the source's bind address and firewall rules.

* SSL errors. Confirm that the certificate paths under `connection.ssl.*` resolve inside the container after the mount. Also confirm that `connection.ssl.mode` matches the mode that the source requires.

* The container exits on `docker stop` and then restarts. The `--restart unless-stopped` policy restarts the container after a non-graceful exit by design. For a permanent stop, run `docker stop` followed by `docker rm`, or remove the restart policy.

* Shutdown takes a minute or more. This delay is expected. The process can wait up to `connection.read_timeout` plus one second before it exits cleanly. See [Graceful shutdown](operational-behavior-reference.md#graceful-shutdown).

## Next steps

* [Get Started With Percona Binary Log Server](get-started.md) — build a minimal config and run `fetch` or `pull`.

* [Command Reference](command-reference.md) — full command and argument reference.

* [Configuration Reference](configuration-reference.md) — every JSON field.

* [Core behavior](operational-behavior-reference.md) — reconnect logic, idle timing, and graceful shutdown details.
