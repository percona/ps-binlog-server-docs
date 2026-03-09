# Storage Reference

Percona Binary Log Server supports local filesystem [storage](glossary.md#storage) and [S3-compatible](glossary.md#s3-compatible-storage) object storage.

## Local Filesystem URI Format

For `backend: "file"`, use:

```text
file://<absolute_path>
```

Example:

```text
file:///home/user/vault
```

The path must be absolute. Relative paths are not supported.

## Amazon S3 URI Format

For Amazon S3, use:

```text
s3://[<access_key_id>:<secret_access_key>@]<bucket_name>[.<region>]/<path>
```

Examples:

```text
s3://binsrv-bucket/vault
s3://binsrv-bucket.us-east-1/vault
s3://key_id:secret@binsrv-bucket.us-east-1/vault
```

When constructing an Amazon S3 URI, credentials and region are optional in some cases, the path after the bucket name defines where objects are stored, and certain characters in the secret access key must be URL-encoded—the list covers each of these.

* omitting AWS credentials in the URI when public access is available

* omitting the region when automatic region detection is preferred

* using the path after the bucket name as the object prefix

* URL-encoding `/` in `secret_access_key` as `%2F` when needed

## S3-Compatible Storage URI Format

For MinIO or another S3-compatible service, use:

```text
http[s]://[<access_key_id>:<secret_access_key>@]<host>[:<port>]/<bucket_name>/<path>
```

Examples:

```text
http://key_id:secret@localhost:9000/binsrv-bucket/vault
https://key_id:secret@192.168.0.100:9000/binsrv-bucket/vault
```

In the S3-compatible URI format in this section, the bucket name must be the first path segment.

## Checkpointing

[Checkpoint](glossary.md#checkpoint)ing controls how often Percona Binary Log Server flushes buffered data to permanent storage.

### `checkpoint_size`

`checkpoint_size` uses a size string: an integer plus an optional suffix. The suffix sets the multiplier (binary).

* no suffix (for example `42`): bytes; size = value × 1

* `K` (for example `42K`): multiplier 2^10; size = value × 1024 bytes

* `M` (for example `42M`): multiplier 2^20; size = value × 1048576 bytes

* `G` (for example `42G`): multiplier 2^30; size = value × 2^30 bytes

* `T` (for example `42T`): multiplier 2^40; size = value × 2^40 bytes

* `P` (for example `42P`): multiplier 2^50; size = value × 2^50 bytes

### `checkpoint_interval`

`checkpoint_interval` uses a time string:

* `42` or `42s` for seconds

* `42m` for minutes

* `42h` for hours

* `42d` for days

### Cost and Performance Warning (S3)

S3 and S3-compatible object storage do not support append. Each checkpoint flush re-uploads the whole binlog object (the entire file up to the current flush point). If you set a small `checkpoint_interval` or small `checkpoint_size` on a high-traffic server, you will trigger very frequent flushes. That leads to a large number of S3 PUT requests, which can produce a large AWS (or provider) bill and saturate network throughput.

Tune checkpointing for S3 with cost and throughput in mind. Prefer `checkpoint_size` over `checkpoint_interval` for rate-limiting flushes: set `checkpoint_size` based on your typical binlog event volume (for example, average event size times expected events between flushes) so that flushes happen at a bounded size rather than on a fixed timer. Avoid short `checkpoint_interval` values (for example, a few seconds) when writing to S3 unless your traffic is low.

Example of how upload volume grows with size-based checkpoints:

* using a `1G` binary log file with `checkpoint_size` set to `256M`

* uploading `256M + 512M + 768M + 1024M = 2560M` in total

Choose checkpoint values with care, especially for large binary logs and S3 backends.

### Cost Optimization (S3)

S3 re-uploads are a direct cost and throughput hazard. A small time-based checkpoint can produce an extreme number of PUTs. Example: with `checkpoint_interval` set to 10 seconds and a single binlog file that grows to 50GB over the day, the server performs one full re-upload every 10 seconds. That is 8,640 full uploads per day (86,400 ÷ 10), each upload rewriting the entire object up to the current size. PUT request charges and data transfer can dominate your S3 bill.

Recommendation: use a size-based checkpoint instead of (or much larger than) a short interval. Set `checkpoint_size` to a value that balances acceptable data loss risk (amount of data in the buffer at the next transaction boundary) against S3 PUT cost. A typical range is 50MB–100MB: large enough to keep flush count and PUT requests low, small enough that at most that much data is at risk between checkpoints if the process exits. Prefer `checkpoint_size` (for example, `64M` or `128M`) and avoid or increase `checkpoint_interval` so that time-based flushes do not dominate. Monitor PUT request volume and storage costs after deployment and adjust if needed.
