# Using Percona Binary Log Server With Percona Operators

This page describes how to use Percona Binary Log Server when your MySQL source is managed by [Percona Operator for MySQL based on Percona Server for MySQL (PS)](https://docs.percona.com/percona-operator-for-mysql/ps/) or [Percona Operator for MySQL based on Percona XtraDB Cluster (PXC)](https://docs.percona.com/percona-operator-for-mysql/pxc/). The Binary Log Server runs as a replication client; the server connects to a MySQL instance that has binary logs enabled and streams those logs to local storage or S3.

The PXC operator already includes a built-in binlog collector (PITR). Using Percona Binary Log Server alongside it for the same purpose is redundant and can lead to two archivers writing to the same destination. Use the [decision matrix](#decision-matrix) on this page to choose.

## Decision matrix

| Your goal | Operator | What to do |
|-----------|----------|------------|
| I just want point-in-time recovery (PITR). | PXC | Use the operator’s native [backup.pitr](https://docs.percona.com/percona-operator-for-mysql/pxc/backups-pitr.html) flag. Do not deploy Percona Binary Log Server for PITR; the operator’s built-in collector is sufficient. |
| I just want point-in-time recovery (PITR). | PS | The PS operator has no built-in binlog archiver. Use Percona Binary Log Server (or another solution) if you need PITR. |
| I need to stream binlogs to a third-party auditing tool, a custom data lake, or a pipeline that requires continuous binlog feed. | PXC or PS | Use Percona Binary Log Server as a sidecar or separate Deployment. Stream to your chosen storage (S3, PVC, or file) and feed your auditing or data-lake pipeline from there. If using PXC, either disable the operator’s PITR or use a different bucket/path so you do not run two archivers to the same destination. |
| I need search by timestamp or GTID set (`search_by_timestamp`, `search_by_gtid_set`) or configurable checkpoint behavior. | PXC or PS | Use Percona Binary Log Server. The operator’s PITR (PXC) does not expose these. If using PXC, disable PITR or use a different bucket/path. |

Do not guess: if you only need PITR and you use PXC, use the operator’s native PITR. Add Percona Binary Log Server only when you have a requirement it fulfills (streaming to a third party, data lake, or search/configurable checkpoints).

## When NOT to use the Binary Log Server (PXC)

If you are using Percona Operator for MySQL based on Percona XtraDB Cluster (PXC) v2.x or later, use the operator’s native [point-in-time recovery (PITR)](https://docs.percona.com/percona-operator-for-mysql/pxc/backups-pitr.html) feature (`backup.pitr`) unless you have a specific requirement the Binary Log Server fulfills: for example, continuous streaming with configurable checkpoints, search by timestamp or GTID set (`search_by_timestamp`, `search_by_gtid_set`), or a different retention or recovery workflow. Do not run Percona Binary Log Server and the operator’s PITR agent against the same bucket and prefix; that runs two archivers against the same source and the same destination. If you do use the Binary Log Server with PXC, either disable the operator’s PITR or use a different bucket or path for the Binary Log Server.

## When to use the Binary Log Server with the operators

* Percona Operator for MySQL (PS). The operator deploys Percona Server for MySQL with group replication or asynchronous replication. The operator does not include a dedicated binlog-archiving pod that streams to S3. To archive binlogs from the cluster to object storage (or to a PVC) with resume and search, run Percona Binary Log Server as a separate workload that connects to the primary.

* Percona Operator for MySQL (PXC). The operator can enable [point-in-time recovery (PITR)](https://docs.percona.com/percona-operator-for-mysql/pxc/backups-pitr.html), which runs a separate PITR pod that uploads binlogs to S3 or Azure on an interval. You can use Percona Binary Log Server instead of or alongside that:
  * Instead of operator PITR. Run the Binary Log Server as a replication client that streams binlogs to S3 (or file). You get continuous streaming, configurable checkpoints, and `search_by_timestamp` / `search_by_gtid_set`. Disable the operator’s PITR so you do not have two writers to the same bucket (or use a different bucket or path for the Binary Log Server).
  * Alongside operator PITR. Use a different bucket or path for the Binary Log Server so both the operator’s PITR and the Binary Log Server can run (for example, different recovery or retention goals). Do not point both at the same prefix without coordination; layout and metadata differ.

## Connecting to the cluster

The Binary Log Server must connect to a MySQL instance that has binary logs enabled and is the source of the stream (the primary, in typical setups).

!!! danger "PXC: enable log_slave_updates"
    If you connect Percona Binary Log Server to a Percona XtraDB Cluster (PXC) node, the primary must have `log_slave_updates` (or `log_replica_updates`) enabled. If it is OFF (the default in some older configs), that node's binary log contains only writes that originated on that specific node, not writes applied from other cluster nodes. The Binlog Server will then capture only a subset of cluster traffic, and point-in-time recovery or auditing will miss transactions that were applied from other nodes. Consequence: total failure of your recovery strategy. Before deploying the Binary Log Server against PXC, verify on the primary: `SHOW VARIABLES LIKE 'log_slave_updates';` (or `log_replica_updates`) must be `ON`. Enable it in the PXC or operator configuration if it is not already set.

* PS operator. Applications usually connect through HAProxy or MySQL Router. For a replication client, you need the primary’s host and port. Use the service that targets the primary (for example, a primary-only service if the operator exposes one). Check the operator’s [architecture](https://docs.percona.com/percona-operator-for-mysql/ps/architecture.html) and [Custom Resource](https://docs.percona.com/percona-operator-for-mysql/ps/operator.html) for the exact service names and ports (typically 3306). Set `connection.host` to that service name (for example, `cluster1-mysql-primary.namespace.svc.cluster.local`) and `connection.port` to the MySQL port.

* PXC operator. Similarly, use the service that reaches the primary node. The operator exposes cluster and per-pod services. For replication, connect to the primary; the operator documentation describes [how to expose the cluster](https://docs.percona.com/percona-operator-for-mysql/pxc/expose.html) and which service to use. If you run the Binary Log Server inside the same Kubernetes cluster, use the internal service DNS name and port 3306.

Create a MySQL user with `REPLICATION SLAVE` (and optionally `REPLICATION CLIENT`) and use that user in the Binary Log Server config. The operator may create a replication user; otherwise create one and store the credentials in a Kubernetes Secret.

## Deploying the Binary Log Server in Kubernetes

Run the Binary Log Server as a Deployment (or StatefulSet if you prefer a stable identity) in the same or a different namespace.

1. Configuration. Build the JSON config with the correct `connection.host` and `connection.port` for the primary service, plus `replication` and `storage`. Put the JSON in a ConfigMap, or mount a file from a ConfigMap. Do not put the MySQL password in the ConfigMap; use a Secret or inject the password at runtime.

2. Credentials. Store the replication user’s password in a Kubernetes Secret. Either inject the password into the config at startup (init container or entrypoint that writes the config with the password) or use a sidecar that provides the config. Avoid committing passwords to the config file in the image.

3. Storage. Choose one:
   * File backend. Use a PersistentVolumeClaim for the directory that will hold the binlogs (and metadata). Set `storage.uri` to `file:///data/binlogs` (or the path you mount the PVC at).
   * S3 backend. Use the same S3 bucket/prefix options as in [Storage Reference](storage-reference.md). Provide credentials via the URI, environment variables, or IAM role (for example, IRSA on EKS). Ensure the pod’s service account or node has the right permissions.

4. Run the process. The container’s main command should run `pull` (for continuous streaming) or `fetch` (for one-time). Example: `binlog_server pull /config/config.json`. Use a process manager or restart policy so the process restarts on failure; the process will resume from the last position in storage.

5. Logging. Set `logger.file` to `""` to log to stdout so your log pipeline (for example, cluster logging, Datadog, ELK) can collect logs. See [Operations](operations.md).

## Summary

| Operator | Use Binary Log Server when |
|----------|----------------------------|
| PS       | You want to archive binlogs to S3 or a PVC; the operator has no built-in binlog streaming. |
| PXC      | You want streaming archiving or search by timestamp/GTID instead of (or in addition to) the operator’s PITR pod; use a different bucket/path if both run. |

Connect the Binary Log Server to the primary’s Kubernetes service and port, use a user with REPLICATION SLAVE, and deploy the Binary Log Server as a separate Deployment with a ConfigMap (config) and Secret (password), plus a PVC or S3 for storage.
