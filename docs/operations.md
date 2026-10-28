# Operations

This page covers how to run Percona Binary Log Server in production. The page covers logging, monitoring, and alerting. The tool runs as a single process. The tool requires no agent or sidecar. You control the server through a JSON configuration file, log routing, and monitoring of the process and its storage.

## Logging

### Where logs go

Configure logging under the `logger` section of the configuration file:

* `logger.file`: the path to a log file, or `""` to log to stdout.

* `logger.level`: the minimum severity. Allowed values are `trace`, `debug`, `info`, `warning`, `error`, and `fatal`. In production, use `info` or `warning`. Use `debug` or `trace` only when you diagnose an issue.

When you set `"file": ""`, all log output goes to stdout. You can then send the output to your existing log pipeline without extra steps.

### Piping to a log pipeline

Capture stdout and stderr with your logging stack. Your options are:

* Systemd. Let journald capture stdout and stderr. Then ship the log messages from the journal to your pipeline, for example Fluentd, Filebeat, a Datadog agent, or an ELK agent. Set `TimeoutStopSec` long enough for a graceful flush. Use at least `connection.read_timeout` plus a few seconds. Otherwise, systemd may send `SIGKILL` before the process finishes flushing. For details, see [Graceful shutdown](operational-behavior-reference.md#graceful-shutdown).

* Docker. Do not redirect stdout. Let your orchestrator or a sidecar collect the container logs and forward the logs to ELK, Datadog, Splunk, or a similar system.

* Bare process. Redirect stdout and stderr to a file or pipe. For example: `./binlog_server pull config.json >> /var/log/binlog-server/binsrv.log 2>&1`. Then read the file with your log shipper. Alternatively, set `logger.file: ""` and redirect stdout from the launcher, such as systemd, supervisord, or a custom wrapper.

The server does not provide a syslog integration or a custom log API. Send stdout or the log file through your normal logging stack.

## Monitoring

### What to observe

* Process health. The process must be running when you expect continuous collection with `pull`. Use your process manager to restart the process when it exits. Examples are systemd, Kubernetes, and Docker health checks. The server exits on non-recoverable errors, for example when the disk is full or when storage errors are not recoverable. A restart resumes from the last position. Monitor the exit codes and restart counts.

* Log output. At the `info` level, the server logs progress messages such as "configuration loaded," "storage opened," and "connection established." The server also logs errors such as connection failures, write failures, and checksum errors. At the `warning` level, the server logs automatic storage recovery events, for example leftover `*.tmp` objects or a size mismatch on the current binlog file. Use the log level and message content to detect connection loops, repeated write failures, checksum mismatches, and recovery after a hard kill.

* Storage growth and lag. The server does not provide a built-in "binlog lag" metric. You can calculate lag by comparing the latest event timestamp in storage with the current time, or with the source server's binlog position. Read the latest event timestamp from `search_by_timestamp` output or from the metadata files. Some teams run a scheduled job that calls `search_by_timestamp` with the current time. The job then reads the `max_timestamp` from the returned files to estimate how far the storage is behind.

* Disk and S3. For local storage, monitor the disk space on the volume that holds the storage URI. If you set `fs_buffer_directory`, monitor the disk space on that volume as well. For S3, monitor the logs for upload errors. Also monitor any S3 or API rate limits and throttling events that your cloud provider or endpoint reports.

### Setting an alert when "binlog lag" exceeds a threshold

The server does not expose a "lag in seconds" metric. To alert when stored data falls too far behind, an implementation needs:

* A measurable definition of lag. For example, "the latest event timestamp in storage is more than five minutes before the current time."

* A periodic script or job. The script calls `search_by_timestamp` with a recent timestamp, or reads the latest metadata file to get `max_timestamp`. The script then compares that timestamp with the current time and fires an alert when the difference is greater than your threshold.

* A schedule driven by your monitoring system. Examples are a cron job that returns a non-zero exit code to your alerting system, or a Prometheus custom check that reports a metric or an event.

### Notes on lag measurement

This method measures lag against the event timestamps in storage. The method does not compare against the source's current position. For stricter alignment, compare the source binlog position (for example, from `SHOW BINARY LOG STATUS`) with the stored metadata. That approach is outside the scope of this page.

## Alerting

Do not rely on log scraping alone. Alert on anomalies such as stalled streaming, a stopped process, and storage or connection failures. The Prometheus rules in this section are starting points for your Prometheus or Alertmanager configuration. The metric names assume that the server, or an exporter that you run, exposes a last-flush timestamp. If your setup does not, write an exporter that reads the latest flush time from the storage metadata. Alternatively, generate the metric from the [binlog lag script](#setting-an-alert-when-binlog-lag-exceeds-a-threshold).

### Prometheus alert rule: streaming stalled

Fire an alert when no flush has succeeded for more than 10 minutes. A long gap usually means that streaming has stalled or the process is stuck.

```yaml
groups:
  - name: binlog_server
    rules:
      - alert: BinlogServerStalled
        expr: time() - binlog_server_last_flush_timestamp_seconds > 600
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Binlog streaming has stalled for more than 10 minutes."
          description: "No flush to storage in 600+ seconds. Check process liveness, source connectivity, and storage (disk/S3) errors."
```

Adjust the threshold value (600), the `for` duration, and the labels for your environment. `binlog_server_last_flush_timestamp_seconds` must be the Unix timestamp of the last successful checkpoint flush. The application itself does not emit this metric. Run a sidecar or a cron job that reads the storage metadata and exposes the metric through a Prometheus exporter or a pushgateway. For the metric value, use the modification time of the current binlog's `.json` file, or the `max_timestamp` of the latest file converted to Unix seconds.

### Other alerts to consider

* Process down. The Binary Log Server process or pod is not running. For example, `up == 0` on the scrape target, or the Kubernetes pod is not ready.
* Repeated restarts. The process or container restart count rises quickly. This pattern usually indicates a crash loop.
* Disk full or S3 write failures. Log patterns or metrics show storage write errors.

## Retention

Percona Binary Log Server has **no built-in retention or purging**. The tool only appends — it never deletes a stored binlog, a metadata file, or an entry in `binlog.index`. Storage therefore grows without bound. Disk-full or bucket-quota exhaustion is a real failure mode if you do not plan deletion externally; once the storage backend rejects a write, the process exits (see [Network failure and reconnect behavior](operational-behavior-reference.md#network-failure-and-reconnect-behavior)).

Lifecycle management is your responsibility. Pick the path that matches your backend:

* `storage.backend: s3`. Use an [S3 Object Lifecycle](https://docs.aws.amazon.com/AmazonS3/latest/userguide/object-lifecycle-mgmt.html) policy (or the equivalent in your S3-compatible service, for example MinIO's lifecycle rules) on the bucket and prefix you write to. Expire objects after the retention window required by your recovery policy. Keep the policy aware of the safe-deletion rules below.

* `storage.backend: file`. Schedule a job (cron, systemd timer, Kubernetes `CronJob`, etc.) that enforces your retention window. Volume-level quotas, alerts on free space, or a dedicated volume help you fail loudly rather than silently corrupting the archive.

### Safe-deletion rules

The stored archive is an indexed structure, not a heap of independent files. Deletion must respect that structure or it will break search and resume. Apply these rules whether the deletion runs as an S3 lifecycle action or a local script:

1. **Never delete the current binlog file or its companion.** The current file is named in the last line of `binlog.index`. Both the binlog and the matching `binlog.NNNNNN.json` metadata file are required for resume. See [Where the resume position is stored](operational-behavior-reference.md#where-the-resume-position-is-stored).

2. **Never delete `metadata.json` or `binlog.index`.** These are required for the server to bootstrap against an existing archive. An S3 lifecycle rule that targets `*.json` indiscriminately will eat both.

3. **Delete `(binlog.NNNNNN, binlog.NNNNNN.json)` as a pair.** A binlog file without its `.json` companion is opaque to search and breaks resume validation. A `.json` companion without its binlog wastes space and confuses search. Use a manifest list of complete pairs, not glob deletion.

4. **In GTID mode, respect the `previous_gtids` chain.** A binlog file's `previous_gtids` set is the set already executed at the start of that file; the file's own contribution is in `added_gtids`. If you intend to support resume or `search_by_gtid_set` for a transaction T, every file whose `(previous_gtids ∪ added_gtids)` is needed to cover T must still be present. If your retention window is purely time-based, this rule is usually satisfied automatically, because newer files are kept and older files are dropped contiguously from the head; do not punch holes in the middle of the sequence. Percona Binary Log Server keeps `previous_gtids` and `added_gtids` current in each metadata file as incoming events arrive. Manual edits to these values rarely serve any operational purpose.

5. **Use `max_timestamp` (not file modification time) as the retention horizon.** The `max_timestamp` field in each `binlog.NNNNNN.json` is the latest event timestamp inside that file, which matches the recovery semantics you actually care about. Object modification time tracks when the server last re-uploaded the object on flush, which can be much more recent than the events it contains.

6. **Update `binlog.index` if you delete entries.** If your deletion path removes entries that still appear in `binlog.index`, future runs will fail validation. Either rewrite `binlog.index` to match what is present, or only delete files that have already aged out of `binlog.index` because of a rotation cycle you control.

7. **Apply deletions only when no Percona Binary Log Server instance is writing to the affected storage.** Rules 1–6 assume a static view of `binlog.index`, `metadata.json`, and each `(binlog.NNNNNN, binlog.NNNNNN.json)` pair. A running server appends to the current binlog and rewrites `binlog.index` on rotation. The server also re-flushes a `.json` sidecar at any time. A concurrent deletion script can race with these writes and leave the archive in an inconsistent state. Stop any `fetch` or `pull` process whose `storage.uri` points at this storage (or scale that deployment to zero), apply the deletion, then restart Percona Binary Log Server. The [`purge_binlogs`](command-reference.md#purge_binlogs) command is the supported deletion path. It takes a target binlog file name and atomically removes every stored file with a sequence number at or below it. The command enforces rules 1, 3, and 6 together. It refuses the current tail file so the resume position is preserved. Because it rewrites `binlog.index`, run `purge_binlogs` only when no `fetch` or `pull` process is writing to the same storage. The constraint is per-storage: storage is identified by its `storage.uri` — an absolute filesystem path for the `file` backend, or the bucket-and-prefix pair for the `s3` backend — and a separate Percona Binary Log Server instance that writes to a different `storage.uri` keeps running, even on the same host. S3 Object Lifecycle policies are an exception to the stopped-process requirement. Such policies only delete whole objects and never rewrite `binlog.index` or `metadata.json`. A policy can run while Percona Binary Log Server is active, if rule 2 excludes those files from the policy scope.

### Minimal retention recipe

A simple, reasonably safe policy for time-based retention:

1. Pick a retention horizon `H` (for example, 14 days) based on the maximum window your point-in-time recovery procedure needs.
2. Enumerate all `binlog.NNNNNN.json` files in storage.
3. For each one, read `max_timestamp`. If `max_timestamp < now - H` **and** the file's name is not the last entry in `binlog.index`, mark the pair for deletion.
4. In GTID mode, additionally confirm that no file you intend to keep references (through its `previous_gtids`) a GTID set that was only produced inside the file you are about to delete. This is almost always trivially true for contiguous time-based deletion, but verify before automating.
5. Delete the pairs that survived the checks above. Do not touch `metadata.json` or `binlog.index`.

For S3 backends, the easiest implementation is an Object Lifecycle rule keyed on object age, plus a one-time guard that excludes `metadata.json` and `binlog.index` from the rule's scope. For file backends, a small script that follows the steps above and runs from `cron` is sufficient.

## Summary

* Logging. Set `logger.file: ""` to send logs to stdout. Send the stream to journald, Docker, or your log shipper. Adjust `logger.level` to balance noise and detail.

* Monitoring. Monitor process liveness, error messages in the logs, disk or S3 health, and optional lag derived from metadata or `search_by_timestamp`.

* Alerting. Combine log scraping with alerting rules for stalled flushes, a stopped process, repeated restarts, and storage failures. Do not rely on log scraping alone.

* Retention. The tool does not delete anything. Plan deletion externally (S3 lifecycle rules or scheduled jobs) and apply the safe-deletion rules above so search and resume keep working.
