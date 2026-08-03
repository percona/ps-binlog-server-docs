# Using Percona Binary Log Server with Percona Operators

Use Percona Binary Log Server when your database runs under [Percona Operator for MySQL (PS)](https://docs.percona.com/percona-operator-for-mysql/ps/). The tool acts as a replication client. The tool connects to a primary that has binary logging enabled and streams binlog data to local storage or to object storage.

From Operator 1.1.0, the PS operator can also run Percona Binary Log Server for you as part of its [point-in-time recovery (PITR)](https://docs.percona.com/percona-operator-for-mysql/ps/backups-pitr.html) workflow (tech preview). Deploy a standalone Percona Binary Log Server workload when you need capabilities that the operator integration does not expose. See the [decision matrix](#decision-matrix).

## Decision matrix

| Your goal | What to do |
|-----------|------------|
| I need point-in-time recovery (PITR) inside the operator workflow. | Enable PITR in the Custom Resource. The operator deploys a Percona Binary Log Server Pod, streams binlogs to the configured S3 prefix, and orchestrates restore with a base backup. See [Point-in-time recovery](https://docs.percona.com/percona-operator-for-mysql/ps/backups-pitr.html), [About backups](https://docs.percona.com/percona-operator-for-mysql/ps/backups.html), and [Restore with PITR](https://docs.percona.com/percona-operator-for-mysql/ps/backups-restore.html). |
| I need to stream binlogs to a third-party auditing tool, a custom data lake, or a pipeline that requires a continuous binlog feed. | Deploy Percona Binary Log Server as a separate workload. Stream to your chosen storage (S3, PVC, or file) and feed your pipeline from there. Use a storage location separate from the operator's PITR prefix if both run. |
| I need search by timestamp or GTID set (`search_by_timestamp`, `search_by_gtid_set`), `list`, `purge_binlogs`, or fine-grained checkpoint and rewrite control. | Deploy Percona Binary Log Server yourself. The operator-managed Binlog Server Pod does not expose these commands or configuration options. See [`backup.binlogServer`](https://docs.percona.com/percona-operator-for-mysql/ps/operator.html) in the Custom Resource reference. |

## When to use the Binary Log Server with the operator

[Percona Operator for MySQL (PS)](https://docs.percona.com/percona-operator-for-mysql/ps/) runs Percona Server for MySQL with group replication or asynchronous replication. The operator automates cluster lifecycle, [physical backups](https://docs.percona.com/percona-operator-for-mysql/ps/backups.html), backup [storage configuration](https://docs.percona.com/percona-operator-for-mysql/ps/backups-storage.html), and (from 1.1.0) [PITR](https://docs.percona.com/percona-operator-for-mysql/ps/backups-pitr.html) — including a managed Percona Binary Log Server Pod when `backup.pitr.enabled` is `true`.

Deploy Percona Binary Log Server as a **separate** workload when you need search commands, custom storage layouts, binlog rewriting, or a feed to systems outside the operator's restore workflow.

## Never share a bucket and prefix

Do not point two Percona Binary Log Server instances, or a Binary Log Server instance and another binlog archiver, at the same `storage.uri`. Each writer maintains its own `binlog.index` and per-file metadata JSON. Each writer chooses object keys that use sequential binlog names (`binlog.000001`, `binlog.000002`, and so on). Neither writer coordinates with the other. If you configure two writers with the same `s3://bucket/prefix`, the failure is silent until you try to restore.

The following problems occur when two writers share the same bucket and prefix:

* Overwritten manifests. Every checkpoint rewrites the prefix-level index and metadata files. The last writer wins. Earlier writes disappear from the catalog, even if the underlying object still exists in the bucket.

* Colliding object keys. Both writers often choose the same file name for different byte ranges. As a result, later uploads overwrite earlier uploads. You lose binlog data, not only metadata.

* Corrupted resume state. Percona Binary Log Server resumes from the flushed `size` that is recorded in the last file's `.json` metadata. If another writer rewrites that metadata, the next restart has two possible outcomes. Either the tool re-streams events that are already stored and produces duplicate-key errors on restore, or the tool skips events and leaves a silent gap.

* Unreplayable archive. A PITR-ready archive must be a continuous, append-only log. Two overlapping writers break this requirement. As a result, `mysqlbinlog` cannot replay the archive from start to end. The `search_by_timestamp` and `search_by_gtid_set` commands return files whose contents no longer match the metadata that indexed them.

* Lifecycle and retention conflicts. A conflict occurs when either writer deletes, expires, or moves files that the other writer still treats as live. The same problem occurs when an S3 lifecycle rule that targets the shared prefix performs any of those actions.

* Higher cost and throttling risk. Even when writes do not collide, you pay twice for storage and for PUT, LIST, and GET requests. The combined checkpoint traffic is also more likely to trigger S3 rate limits (HTTP 503 `SlowDown`).

Safe layouts:

* Separate buckets. Use one bucket per writer. Scope IAM so that a misconfiguration cannot cross the boundary between buckets.

* Same bucket with non-overlapping prefixes. For example, use `s3://archive/operator-pitr/` for the operator-managed Binlog Server and `s3://archive/custom-pipeline/` for a standalone deployment. The operator requires a dedicated binlog prefix for PITR and does not allow changing that prefix after configuration. Scope IAM per prefix. Make sure that any bucket lifecycle rules target each prefix explicitly and not the bucket root.

If you must migrate from one archive location to another, stop the first writer and let the first writer complete its final flush. Then configure the second writer with a new prefix. Do not reuse the old prefix.

## Connecting to the cluster

Percona Binary Log Server must connect to a MySQL or MySQL-compatible server that has binary logging enabled. In typical setups, this server is the primary.

Applications usually reach the cluster through HAProxy or MySQL Router. However, a replication client needs the primary's host and port directly. Use the service that targets the primary, for example the operator's primary-only service if one is exposed. The operator's [architecture](https://docs.percona.com/percona-operator-for-mysql/ps/architecture.html) page and [Custom Resource](https://docs.percona.com/percona-operator-for-mysql/ps/operator.html) page list the service names and ports (typically 3306). Set `connection.host` to the service name, for example `cluster1-mysql-primary.namespace.svc.cluster.local`. Set `connection.port` to the service port.

Create an account that has the `REPLICATION SLAVE` privilege. The `REPLICATION CLIENT` privilege is optional. Use the account in the Percona Binary Log Server configuration. The operator may already provide a replication user. If not, create one and store the credentials in a Kubernetes Secret. See [Manage users](https://docs.percona.com/percona-operator-for-mysql/ps/users.html) in the operator documentation.

## Deploying the Binary Log Server in Kubernetes

Run Percona Binary Log Server as a Deployment, or as a StatefulSet if you need a stable identity. You can run the workload in the same namespace as the database or in a different namespace.

1. Configuration. Build the JSON configuration file. Set `connection.host` and `connection.port` to the primary's service. Also set the `replication` and `storage` sections. Mount the configuration file from a ConfigMap. Do not put the database password in the ConfigMap. Keep the password in a Secret or inject the password at runtime.

2. Credentials. Two kinds of credentials apply, and both must end up inside the configuration file at startup:

   * **MySQL replication user.** Store the replication user's password in a Kubernetes `Secret`. Inject the password at startup, for example through an init container or an entrypoint script that writes the full configuration file (you can also supply the configuration file from a sidecar). Do not store the password in the image or in a ConfigMap.

   * **S3 credentials.** Percona Binary Log Server reads S3 credentials **only** from `storage.uri`. The upstream URI grammar (see the `README.md` in [Percona-Lab/percona-binlog-server](https://github.com/Percona-Lab/percona-binlog-server)) is `s3://[<access_key_id>:<secret_access_key>@]<bucket_name>[.<region>]/<path>` for AWS S3 and `http[s]://[<access_key_id>:<secret_access_key>@]<host>[:<port>]/<bucket_name>/<path>` for S3-compatible endpoints. The userinfo brackets make the credentials look syntactically optional, but they are practically required because the server does **not** consult the AWS default credential chain — `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY` environment variables, IRSA on EKS, instance profiles, IMDS, and `~/.aws/credentials` have no effect. Only publicly write-accessible buckets may omit the credentials, which is rare in production. Source the access key ID and secret from a Kubernetes `Secret` and assemble the full `storage.uri` at startup (init container or entrypoint script), percent-encoding any URI-reserved characters in the access key or secret. The most important case is `/` as `%2F` (common in AWS secret access keys). Also encode `+` as `%2B`, `=` as `%3D`, `@` as `%40`, and `:` as `%3A`. Treat the rendered configuration file as a secret.

3. Storage. Choose one of the following options:
   * File backend. Bind a PersistentVolumeClaim to the directory that holds the binlogs and metadata. Set `storage.uri` to `file:///data/binlogs`, or to the path where you mount the PVC.
   * S3 backend. Use the bucket and prefix options from [Storage Reference](storage-reference.md). For credentials, see step 2 above — they must be embedded in `storage.uri`.

4. Run the process. The container's main command should run `pull` for continuous streaming or `fetch` for a one-time run. For example: `binlog_server pull /config/config.json`. Let the orchestrator restart the process after a failure. The new process resumes from the last position in storage.

5. Logging. Set `logger.file` to `""` to log to stdout. Stdout output allows cluster logging, Datadog, ELK, or another pipeline to collect the logs. See [Operations](operations.md).

## Explanation

In operator-managed Kubernetes, Percona Binary Log Server usually runs as its own Deployment. The tool connects to the cluster primary and writes binlogs to the object storage that you configure. Common destinations include Amazon S3, Google Cloud Storage through an S3-compatible endpoint, and other S3-compatible backends. In each case, set `storage.backend: s3` with the correct `storage.uri`. The archived binlogs and metadata are stored outside the database pod and outside the pod's PVCs.

This separation keeps [point-in-time recovery (PITR)](glossary.md#point-in-time-recovery) possible after cluster accidents. You can still restore to a chosen moment after the original MySQL pod is deleted or after the pod's volume is lost. You need two things for the restore: the archive must still exist in the bucket, and you must have the base backup that the recovery procedure requires. When PITR is enabled in the operator, the [restore workflow](https://docs.percona.com/percona-operator-for-mysql/ps/backups-restore.html) reads base backups and archived binlogs from that off-cluster store automatically. A standalone Percona Binary Log Server deployment supplies the same kind of continuous binlog stream when you manage archiving outside the operator.

## Summary

The [PS operator](https://docs.percona.com/percona-operator-for-mysql/ps/) automates most database operations on Kubernetes: cluster deployment, [backups](https://docs.percona.com/percona-operator-for-mysql/ps/backups.html), [backup storage](https://docs.percona.com/percona-operator-for-mysql/ps/backups-storage.html), monitoring, and failover. From Operator 1.1.0, the operator also handles [point-in-time recovery](https://docs.percona.com/percona-operator-for-mysql/ps/backups-pitr.html) (tech preview) end to end — deploying a Percona Binary Log Server Pod, collecting binlogs to S3, and running the [restore workflow](https://docs.percona.com/percona-operator-for-mysql/ps/backups-restore.html) against a base backup. For operator-managed PITR, enable `backup.pitr` in the Custom Resource; a separate Percona Binary Log Server Deployment is not required.

Deploy Percona Binary Log Server yourself when you need search commands (`search_by_timestamp`, `search_by_gtid_set`, `list`, `purge_binlogs`), custom storage or checkpoint settings, binlog rewriting, or a continuous feed to systems outside the operator's restore path. Configure the standalone workload with the primary's Kubernetes service name and port (see [Connecting to the cluster](#connecting-to-the-cluster)), an account that has the `REPLICATION SLAVE` privilege, and either a PVC or S3 backend. Back the Deployment with a ConfigMap for the configuration file, a Secret for credentials, and storage isolated from the operator's PITR prefix.
