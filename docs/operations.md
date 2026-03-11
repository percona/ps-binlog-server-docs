# Operations

This page describes how to run Percona Binary Log Server in production: logging, monitoring, and alerting. The server is a single process; there is no separate agent or sidecar. You operate the server by configuring the JSON file, directing log output, and observing the process and storage.

## Logging

### Where logs go

Log destination is set in the configuration file under `logger`:

* `logger.file`: path to a file, or `""` for standard output.

* `logger.level`: minimum severity (`trace`, `debug`, `info`, `warning`, `error`, `fatal`). Use `info` or `warning` in production; use `debug` or `trace` only when diagnosing issues.

With `"file": ""`, all log output goes to stdout. Piping into your existing log pipeline is straightforward.

### Piping to a log pipeline

Run the process so that stdout (and stderr, if used) is captured by your logging stack:

* Systemd. Configure the service unit so that stdout/stderr are captured by journald, then ship logs from the journal to your pipeline (for example, Fluentd, Filebeat, or a Datadog/ELK agent that reads the journal). Set `TimeoutStopSec` long enough for a graceful flush (at least `connection.read_timeout` plus a few seconds), so systemd does not send SIGKILL before the process has flushed; see [Graceful shutdown](operational-behavior-reference.md#graceful-shutdown).

* Docker. Run the container without redirecting stdout; your orchestrator or sidecar can collect container logs and send them to ELK, Datadog, Splunk, and so on.

* Bare process. Redirect to a file or pipe: for example, `./binlog_server pull config.json >> /var/log/binlog-server/binsrv.log 2>&1`, and have your log shipper tail that file. Alternatively, use `logger.file: ""` in the config and redirect the process stdout from the launcher (systemd, supervisord, or your own wrapper).

The server does not write to syslog or a custom API. To get logs into ELK, Datadog, or similar, you rely on the process stdout (or a file) and your existing log collection (Filebeat, Fluentd, Datadog agent, and so on).

## Monitoring

### What to observe

* Process health. The process should be running when you expect continuous collection (`pull`). Use your process manager (systemd, Kubernetes, Docker health checks) to restart the process on exit. Note: the server exits on non-recoverable errors (for example, out of disk, or unrecoverable storage errors). Restarting will resume from the last position; monitor exit codes and restarts.

* Log output. At `info` level, the server logs progress (configuration loaded, storage opened, connection established, and so on). Errors (connection failures, write failures, checksum errors) are logged. Use log level and message content to detect connection loops, repeated write failures, or checksum mismatches.

* Storage growth and lag. There is no built-in “binlog lag” metric. You can infer lag by comparing the latest event timestamp in storage (for example, from `search_by_timestamp` or from metadata files) to the current time or to the source server’s binlog position. Some teams run a scheduled job that calls `search_by_timestamp` with “now” and checks the returned files’ `max_timestamp` to approximate how far behind the storage is.

* Disk and S3. For local storage, monitor disk space on the volume that holds the storage URI and, if used, `fs_buffer_directory`. For S3, monitor upload errors in logs and any S3/API rate limits or throttling reported by your cloud provider or endpoint.

### Setting an alert when “binlog lag” exceeds a threshold

The server does not expose a “lag in seconds” metric. To alert when stored data is too far behind:

1. Define “lag” in a way you can measure: for example, “latest event timestamp in storage is more than 5 minutes before now.”

2. Periodically run a script or job that:
   * Calls `search_by_timestamp` with a timestamp from a few minutes ago (or the current time), or reads the latest metadata file in storage to get the latest `max_timestamp`.
   * Compares that timestamp to the current time.
   * If the difference exceeds your threshold (for example, 5 minutes), trigger an alert.

3. Run the script from your monitoring system (Cron plus a script that exits non-zero and is picked up by your alerting, or a Datadog/Prometheus custom check that runs the script and reports a metric or event).

That approach gives you “lag” based on event timestamps in storage, not on the source server’s current position. For stricter alignment with the source, you would need to compare source binlog position to stored position; that requires querying the source (for example, `SHOW BINARY LOG STATUS`) and comparing to stored metadata, which is outside the scope of this document.

## Alerting

Do not rely only on tailing logs. Alert on anomalies: stalled streaming, process down, and storage or connection failures. The following Prometheus alerting rules are examples you can add to your Prometheus or Alertmanager config. The metric names assume the server (or a custom exporter you run) exposes a last-flush timestamp; if your deployment does not expose that metric yet, implement an exporter that reads the latest flush time from storage metadata and exposes it, or use the [binlog lag script](#setting-an-alert-when-binlog-lag-exceeds-a-threshold) in this page to drive a metric and alert on that.

### Prometheus alert rule: streaming stalled

Alert when no successful flush has occurred for more than 10 minutes (streaming likely stalled or process stuck):

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

Adjust the threshold (600), `for` duration, and labels to match your environment. The metric `binlog_server_last_flush_timestamp_seconds` must be the Unix timestamp of the last successful checkpoint flush. The application does not expose this metric. Use a sidecar or cron job that reads storage metadata: for example, the modification time of the current binlog file’s `.json` metadata file, or the latest file’s `max_timestamp` (event time) converted to Unix seconds, then expose it via a Prometheus exporter or pushgateway.

### Other alerts to consider

* Process down. Alert when the Binary Log Server process or pod is not running (for example, `up == 0` on the process scrape target, or Kubernetes pod not ready).
* Repeated restarts. Alert when the process or container restart count increases rapidly (for example, crash loop).
* Disk full or S3 write failures. Alert on log patterns or metrics that indicate storage write errors (if exposed or inferred from logs).

## Summary

* Logging. Set `logger.file` to `""` for stdout and feed stdout into your log pipeline (journald, Docker logs, file tail, or a shipper). Use `logger.level` to control verbosity.

* Monitoring. Watch process liveness, log messages for errors, storage growth, and (if needed) a custom “lag” check based on timestamps in storage.

* Alerting. Alert on anomalies: use Prometheus rules such as BinlogServerStalled (no flush for 10+ minutes), process down, restarts, and storage errors. Do not rely on tailing logs alone.
