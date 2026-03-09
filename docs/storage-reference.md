# Storage reference

Percona Binary Log Server writes to local filesystem [storage](glossary.md#storage) or to [S3-compatible](glossary.md#s3-compatible-storage) object storage.

## Local filesystem URI format

For `backend: "file"`, use:

```text
file://<absolute_path>
```

Example:

```text
file:///home/user/vault
```

The path must be absolute. The tool rejects relative paths.

## Amazon S3 URI format

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

Amazon S3 URIs vary by setup:

* Credentials are read **only** from the `storage.uri` userinfo. Percona Binary Log Server does not consult the AWS default credential chain, so `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY` environment variables, IRSA on EKS, instance profiles, IMDS, and `~/.aws/credentials` have no effect. The userinfo brackets in the URI grammar make the credentials look syntactically optional, but in practice they are required. The only case where the userinfo can be omitted is a bucket that allows public writes, which is rare in production.

* Omit the region to let the client detect the region from the bucket name or endpoint.

* The part of the path after the bucket name is used as the object prefix.

* Percent-encode any URI-reserved characters in the access key or secret before embedding them in the userinfo. The most important case is `/` as `%2F` (common in AWS secret access keys). Also encode `+` as `%2B`, `=` as `%3D`, `@` as `%40`, and `:` as `%3A`.

## S3-compatible storage URI format

For MinIO or another S3-compatible service, use:

```text
http[s]://[<access_key_id>:<secret_access_key>@]<host>[:<port>]/<bucket_name>/<path>
```

Examples:

```text
http://key_id:secret@localhost:9000/binsrv-bucket/vault
https://key_id:secret@192.168.0.100:9000/binsrv-bucket/vault
```

In an S3-compatible URI, the bucket name must be the first path segment. Credentials follow the same rules as the Amazon S3 URIs in the preceding section. Embed credentials in the userinfo and percent-encode any URI-reserved characters. The server does not consult the AWS default credential chain. As a result, environment variables, IRSA, instance profiles, IMDS, and `~/.aws/credentials` have no effect for S3-compatible endpoints either.

## Checkpointing

[Checkpointing](glossary.md#checkpoint) controls how often Percona Binary Log Server flushes buffered data to permanent storage.

### `checkpoint_size`

`checkpoint_size` accepts a size string. The size string is an integer followed by an optional suffix. The suffix is a binary multiplier.

* no suffix (for example `42`): bytes; size = value × 1

* `K` (for example `42K`): multiplier 2^10; size = value × 1024 bytes

* `M` (for example `42M`): multiplier 2^20; size = value × 1048576 bytes

* `G` (for example `42G`): multiplier 2^30; size = value × 2^30 bytes

* `T` (for example `42T`): multiplier 2^40; size = value × 2^40 bytes

* `P` (for example `42P`): multiplier 2^50; size = value × 2^50 bytes

### `checkpoint_interval`

`checkpoint_interval` accepts a time string:

* `42` or `42s` for seconds

* `42m` for minutes

* `42h` for hours

* `42d` for days

### S3 checkpointing behavior

S3 and S3-compatible object storage do not support append operations. Each checkpoint flush re-uploads the entire binlog object up to the current flush point. As a result, the total bytes transferred are greater than the final file size, and the total grows with the flush frequency. For example, a 1G binlog file that is flushed at `checkpoint_size: 256M` transfers `256M + 512M + 768M + 1024M = 2560M` in total.

Tuning guidance belongs in the Explanation section. A dedicated page will cover the cost model, recommended ranges, and the trade-offs between `checkpoint_size` and `checkpoint_interval`.
