# Binlog storage encryption

Percona Binary Log Server encrypts binlog payloads with a per-file key.

That file key is wrapped with a key-encryption key (KEK) from a local keyring.

An optional top-level `keyring` section loads the keyring file.

An optional `storage.encryption` section selects the KEK and the data cipher for new files.

The server writes per-file encryption envelopes into binlog metadata.

The following sections describe the configuration contract, keyring format, and metadata behavior.

## How encryption configuration works

Add the optional `keyring` section and, when new files must be encrypted, the optional `storage.encryption` section to the JSON configuration file.

When `storage.encryption` is present, the server completes the following steps:

1. Load encryption keys from `keyring.uri`

2. Select the configured KEK (`storage.encryption.kek_id`) from that keyring

3. Create a file key for each binlog file and record a wrapped file-key envelope

4. Record a file-data envelope for the configured data cipher

5. Encrypt binlog file bytes with that data cipher before writing them to storage

6. Store those per-file encryption envelopes in the binlog metadata JSON file

`storage.encryption` applies to both supported storage backends:

* `file`

* `s3`

`keyring` must be present when storage already contains at least one encrypted binlog file, even if `storage.encryption` is omitted.

Storage encryption settings differ from [Transport Layer Security (TLS) for the MySQL connection](ssl-tls-connections.md).

## Cipher name format

Cipher names are strings.

The server reads key length and mode from substrings in the name when the server builds an encryption envelope.

| Part | Recognized values |
|------|-------------------|
| Key length token | `-128-`, `-192-`, `-256-` |
| Mode suffix | `-ECB`, `-CBC`, `-CTR`, `-GCM` |

Upstream samples often use the pattern `AES-<KEY_LENGTH>-<MODE>`:

```text
AES-<KEY_LENGTH>-<MODE>
```

Names that match that pattern:

* `AES-128-ECB`

* `AES-128-CBC`

* `AES-128-CTR`

* `AES-128-GCM`

* `AES-192-ECB`

* `AES-192-CBC`

* `AES-192-CTR`

* `AES-192-GCM`

* `AES-256-ECB`

* `AES-256-CBC`

* `AES-256-CTR`

* `AES-256-GCM`

The parser does not require an `AES` prefix.

Percona Binary Log Server has been tested with `AES`, `ARIA`, and `CAMELLIA`.

Prefer `AES` for new deployments.

An unrecognized key-length token or mode suffix causes an error when the server builds an encryption envelope.

### KEK ciphers

The KEK cipher is the `cipher` field in the keyring record.

Any cipher name with a recognized key-length token and mode suffix can wrap file keys, subject to [KEK and data-cipher combinations](#kek-and-data-cipher-combinations).

### Data ciphers

The data cipher is `storage.encryption.cipher`.

The only supported mode for the data cipher is CTR.

Configuration validation rejects any other mode with:

```text
error validating storage encryption config: only CTR mode is supported for data encryption cipher
```

Use a CTR cipher such as `AES-256-CTR`.

Do not set `storage.encryption.cipher` to `*-ECB`, `*-CBC`, or `*-GCM`.

### KEK and data-cipher combinations

Not every KEK cipher can wrap every data-cipher key length.

If the active KEK uses `*-ECB` or `*-CBC`, the KEK can wrap only file keys whose length is a multiple of 16 bytes.

In that case `storage.encryption.cipher` may be `*-128-CTR` or `*-256-CTR`.

`*-192-CTR` fails because a 192-bit (24-byte) file key is not a multiple of 16 bytes.

Startup also tests that a random file key of the data-cipher length can be encrypted with the active KEK.

### Recommended combination for first deployments

| Role | Setting | Value |
|------|---------|-------|
| KEK cipher | `keys[].cipher` in the keyring | `<KEK_CIPHER>` |
| Data cipher | `storage.encryption.cipher` | `AES-256-CTR` |

For first deployments, prefer a 256-bit authenticated mode for the KEK (`*-256-GCM`).

Use CTR for the data cipher (`AES-256-CTR`).

## Configuration file location and how to apply changes

Binary Log Server does not require a fixed system path for the configuration file.

Package installs can place a sample file at `/etc/percona-binlog-server/main_config.json`.

Pass the path as a command-line argument on every run:

```text
./binlog_server fetch <PATH_TO_CONFIG.json>
./binlog_server pull <PATH_TO_CONFIG.json>
./binlog_server list <PATH_TO_CONFIG.json>
```

Each process reads the JSON file at start.

The product does not reload the configuration while a process runs.

To apply encryption or keyring changes:

1. Edit the JSON configuration file and the keyring file as needed

2. Stop a long-running `pull` process if one is active

3. Start `fetch` or `pull` again with the same `<PATH_TO_CONFIG.json>`

## Enable encryption

Add a top-level `keyring` object and a `storage.encryption` object to the configuration file:

```json
{
  "keyring": {
    "uri": "file:///var/lib/pbs/keyring/keyring_data.json"
  },
  "storage": {
    "backend": "file",
    "uri": "file:///var/lib/pbs/vault",
    "encryption": {
      "format": "generic",
      "kek_id": "<KEK_ID>",
      "cipher": "AES-256-CTR"
    }
  }
}
```

### Configuration parameters

| Parameter | Required | Description |
|-----------|----------|-------------|
| `keyring.uri` | When any stored file is encrypted, or when `storage.encryption` is present | URI of the keyring JSON file. The only supported scheme is `file://` on the local filesystem. Example: `file:///var/lib/pbs/keyring/keyring_data.json`. |
| `storage.encryption.format` | Yes (when `encryption` is present) | Encryption format. The only supported value is `generic`. |
| `storage.encryption.kek_id` | Yes (when `encryption` is present) | ID of the KEK in the keyring. The ID must exist in the keyring file. |
| `storage.encryption.cipher` | Yes (when `encryption` is present) | Cipher name for binlog file data encryption. Must be a CTR mode cipher (for example, `AES-256-CTR`). |

Omit `storage.encryption` when new binlog files must be written without encryption.

Keep `keyring` when existing files in that storage still have encryption metadata.

!!! note

    `storage.encryption.format` must be `generic` when the section is present.

    Storage metadata records the format name `generic` for encrypted files.

    You can omit `storage.encryption` later so that new files are written without encryption, as long as `keyring` remains configured for existing encrypted files.

## Generate key-encryption keys

Do not copy sample `data_hex` values from documentation or from sample files in the source tree.

Create each KEK with a cryptographically secure random generator.

Match the key length to the cipher name in the keyring record:

| Cipher name pattern | Key length | Hex characters for `data_hex` | Example command |
|---------------------|------------|-------------------------------|-----------------|
| `*-128-*` | 16 bytes | 32 | `openssl rand -hex 16` |
| `*-192-*` | 24 bytes | 48 | `openssl rand -hex 24` |
| `*-256-*` | 32 bytes | 64 | `openssl rand -hex 32` |

Example workflow:

1. Choose a KEK cipher (`<KEK_CIPHER>`). Prefer a 256-bit authenticated mode (`*-256-GCM`)

2. Generate key material that matches the key length for that cipher. For a `*-256-*` cipher, run `openssl rand -hex 32`

3. Create or update the keyring JSON file with a unique `id`, the cipher name, and the hex output as `data_hex`

4. Restrict keyring file permissions. See [Keyring file permissions](#keyring-file-permissions)

5. Set `keyring.uri` to that keyring file

6. Set `storage.encryption.kek_id` to that key `id`

7. Set `storage.encryption.cipher` to a CTR data cipher (for example, `AES-256-CTR`)

The KEK cipher wraps file keys.

The data cipher encrypts binlog file bytes.

Those two cipher values can differ.

## Keyring file format

The keyring is a JSON file on the local filesystem.

The only supported URI scheme is `file://`.

```json
{
  "version": 1,
  "keys": [
    {
      "id": "<KEK_ID>",
      "cipher": "<KEK_CIPHER>",
      "data_hex": "<OUTPUT_OF_openssl_rand_-hex_N>"
    }
  ]
}
```

| Field | Description |
|-------|-------------|
| `version` | Keyring format version. The value must be `1`. |
| `keys` | Array of key records. |
| `keys[].id` | Unique string ID for the key. Duplicate IDs cause startup to fail. Set `storage.encryption.kek_id` to this value for the active KEK. |
| `keys[].cipher` | Symmetric cipher for this key. The mode must be `ECB`, `CBC`, `CTR`, or `GCM`. The server uses this cipher to wrap file keys. |
| `keys[].data_hex` | Key material as a hexadecimal string. Length must match the cipher name. The server validates that length at startup. See [Generate key-encryption keys](#generate-key-encryption-keys). |

## Keyring file permissions

The keyring file stores key material in plaintext JSON.

Only the operating system user that runs `binlog_server` must read that file.

### Identify the process user

If `binlog_server` is running:

```bash
ps -o user= -C binlog_server
```

If several processes match, use the process ID:

```bash
pgrep -a binlog_server
ps -o user= -p <PID>
```

If you start the utility yourself, the process user is your account:

```bash
id -un
```

Package installs do not create a dedicated `binlog_server` system user.

The process user is the account that runs the command or service unit.

### Set ownership and mode

Replace `<PROCESS_USER>` and `<PROCESS_GROUP>` with the account from the previous step.

Replace the paths with your keyring directory and file:

```bash
sudo mkdir -p /var/lib/pbs/keyring
sudo chown <PROCESS_USER>:<PROCESS_GROUP> /var/lib/pbs/keyring
sudo chmod 700 /var/lib/pbs/keyring
sudo chown <PROCESS_USER>:<PROCESS_GROUP> /var/lib/pbs/keyring/keyring_data.json
sudo chmod 600 /var/lib/pbs/keyring/keyring_data.json
```

| Path | Suggested mode | Meaning |
|------|----------------|---------|
| Keyring directory | `700` | Owner can list and enter the directory |
| Keyring file | `600` | Owner can read and write the file |

A user who can read the keyring and the encrypted binlogs can recover the data.

## What stays in plaintext

The following objects stay in plaintext and remain sensitive:

| Object | Examples of exposed data |
|--------|--------------------------|
| `metadata.json` | Replication mode, encryption format name (`generic`) |
| Sidecar metadata `<BINLOG_NAME>.json` | File size, timestamps, Global Transaction Identifier (GTID) sets, `kek_id`, data cipher name, IVs, wrapped file key material, Authenticated Encryption with Associated Data (AEAD) tags |
| `binlog.index` | Ordered list of binlog file names |
| Object names and paths | Binlog file names, storage URI prefixes, S3 keys |
| Keyring JSON file | Key IDs, KEK cipher names, KEK `data_hex` values |
| Logger output | Encryption format, keyring URI, key IDs, active KEK description |

Treat metadata, index files, logs, and the keyring as sensitive.

Restrict filesystem or object-storage access to those objects.

## Decrypt operations and missing KEK errors

`fetch` and `pull` write binlog data to storage.

With `storage.encryption` enabled, those commands create encryption envelopes for each new binlog file.

The following commands open storage with the same configuration:

* `list`

* `search_by_timestamp`

* `search_by_gtid_set`

* `purge_binlogs`

Those commands do not decrypt binlog payloads to standard output.

Those commands include an optional `encryption` object in each per-file result entry when that file has encryption metadata.

See [Command JSON output](#command-json-output) and [Command reference](command-reference.md).

Every command that opens storage with encrypted files present, or with `storage.encryption` configured, loads the keyring from `keyring.uri`.

When `storage.encryption` is present, the server also resolves `storage.encryption.kek_id`.

### Missing KEK ID

If `storage.encryption` is present and the keyring does not contain `storage.encryption.kek_id`, storage initialization fails.

The error message is:

```text
keyring does not contain the specified KEK ID
```

JSON-style command responses can include that text in the `message` field:

```json
{
  "status": "error",
  "message": "keyring does not contain the specified KEK ID"
}
```

If code loads a key ID that is absent from the keyring collection, the error message is:

```text
key not found in the keyring record collection
```

### Incorrect KEK material

If the key ID exists but `data_hex` is the wrong key material (correct length, wrong bytes), startup does not report a separate validation error for those bytes.

If `data_hex` length does not match the cipher name, startup fails.

Restore the correct KEK from backup before you rely on future decrypt of retained files.

## Existing storage and mixed encryption

Whether each binlog file is encrypted is recorded in that file's sidecar metadata.

`storage.encryption` controls encryption for **new** files only.

You can change the configuration between runs:

* Omit `storage.encryption` so that later files are written without encryption.

* Keep `keyring` so the server can unwrap file keys for files that already have encryption metadata.

* Add or keep `storage.encryption` so that later files are encrypted.

A vault can therefore contain both encrypted and unencrypted binlog files.

Do not remove `keyring` while any retained file still has an `encryption` object in its sidecar.

## Migrate to storage with encryption metadata

Binary Log Server does not convert an existing storage URI in place when you enable `storage.encryption`.

To encrypt an archive that was created without encryption, repopulate an empty storage from the MySQL source.

### 1. Record the state

1. Run `list` against the old configuration file

2. Note the latest binlog name and the storage URI

3. Confirm that the MySQL source retains the binary logs you need

### 2. Create keyring and configuration with encryption metadata

1. Generate a KEK. See [Generate key-encryption keys](#generate-key-encryption-keys)

2. Write the keyring file and set permissions. See [Keyring file permissions](#keyring-file-permissions)

3. Copy the old configuration file to a second file, such as `<PATH_TO_ENCRYPTION_CONFIG.json>`

4. Set an empty `storage.uri` value

5. Add `keyring.uri` and `storage.encryption` with `format` `generic`, your `kek_id`, and a CTR data cipher (`AES-256-CTR`)

### 3. Repopulate the target storage

1. Stop `pull` on the old storage if that process is running

2. Start capture to the target storage:

   ```text
   ./binlog_server fetch <PATH_TO_ENCRYPTION_CONFIG.json>
   ```

   Or for continuous capture:

   ```text
   ./binlog_server pull <PATH_TO_ENCRYPTION_CONFIG.json>
   ```

3. Let `fetch` or `pull` stream from the MySQL source into the target URI

The utility does not copy files from the old storage directory into the target storage.

### 4. Validate the target storage

1. Confirm startup log lines for encryption format, keyring status, and active KEK

2. Confirm `metadata.json` includes `"encryption": "generic"` when the vault was initialized with encryption

3. Confirm a `<BINLOG_NAME>.json` file includes an `encryption` object with the expected `kek_id` and data cipher

4. Run `list` against the target configuration and confirm expected binlog names and sizes

5. Compare coverage with the old storage and with the source retention requirements

### 5. Cut over

1. Configure operations and automation with `<PATH_TO_ENCRYPTION_CONFIG.json>`

2. Keep the old configuration file and old storage read-only until validation is complete

3. Run only one writer (`fetch` or `pull`) against the target storage URI

### 6. Remove the old storage

Remove the old storage only when all of the following are true:

* The target storage has the required binlog coverage

* Validation checks in step 4 passed

* No process uses the old storage URI

* You have a secure backup of the keyring file

* Your retention policy no longer requires the old files

Then delete or archive the old storage URI according to your site policy.

## Key-encryption key rotation, backup, and loss

Binary Log Server has no built-in KEK rotation command.

Manage keys in the keyring file and in the configuration file.

### Backup

Copy the keyring JSON file to a secure offline location before you change keys.

Protect backups with the same access controls as the live keyring.

Without the KEK material, binlog metadata that references that KEK cannot be unwrapped.

Future encrypted payloads that use that KEK cannot be decrypted without the KEK material.

### Rotation for later binlog files

1. Generate a KEK and add a key record to the keyring file

2. Keep every older KEK that older binlog metadata references

3. Set `storage.encryption.kek_id` to the KEK ID

4. Stop `pull` if the process is running

5. Start `fetch` or `pull` again

Later binlog files use the KEK ID in `file_key_envelope.kek_id`.

Older binlog files keep the previous KEK ID in their metadata.

### Access to metadata that references an older key

Keep the older KEK records in the same keyring file.

The server needs those keys to unwrap file keys for older metadata.

Do not remove an old KEK while any retained binlog metadata lists that `kek_id`.

### Loss or removal

If a KEK is lost or removed from the keyring, binlog metadata that references that `kek_id` cannot have its file key unwrapped.

Future ciphertext that uses that KEK cannot be decrypted.

Restore the KEK from backup before you need to read those files.

If the active `kek_id` is missing at start, the process fails with `keyring does not contain the specified KEK ID`.

## Verify that encryption metadata is present

The following checks confirm that encryption configuration and envelopes are active.

### Startup log

On start, Binary Log Server writes encryption details to the logger destination from `logger.file`.

Look for lines that report:

* Binlog storage encryption format

* Binlog storage encryption keyring URI

* Keyring status and loaded key IDs

* Active KEK ID and KEK cipher

### Storage metadata

Open `metadata.json` in the storage URI.

Confirm that the `encryption` field is set to `generic` when the vault has used encryption.

### Command JSON output

Run `list`, `search_by_timestamp`, `search_by_gtid_set`, or `purge_binlogs` against storage that has encryption metadata.

Each per-file entry in `result` can include an optional `encryption` object.

That object matches the sidecar metadata shape:

* `encryption.file_key_envelope`

* `encryption.file_data_envelope`

Example fragment:

```json
"encryption": {
  "file_key_envelope": {
    "kek_id": "<KEK_ID>",
    "data_hex": "<WRAPPED_FILE_KEY_HEX>",
    "iv_hex": "<IV_HEX>",
    "tag_hex": "<TAG_HEX>"
  },
  "file_data_envelope": {
    "cipher": "AES-256-CTR",
    "iv_hex": "<IV_HEX>"
  }
}
```

Omit `iv_hex` or `tag_hex` when the cipher mode does not use those fields.

Files written without encryption omit the `encryption` object.

See [Command reference](command-reference.md).

### Per-binlog metadata

For each binlog file `<BINLOG_NAME>`, open the sidecar metadata file `<BINLOG_NAME>.json` in the same storage location.

Confirm that the metadata includes an `encryption` object for files written with `storage.encryption` enabled.

| Field | What to confirm |
|-------|-----------------|
| `encryption.file_key_envelope.kek_id` | KEK ID used to wrap the file key |
| `encryption.file_data_envelope.cipher` | Data cipher recorded for the binlog file |
| `encryption.file_key_envelope.data_hex` | Wrapped file key material is present |
| `encryption.file_data_envelope.iv_hex` | IV for the data cipher is present |

Binlog files written with encryption enabled include this `encryption` object.

## Per-file encryption metadata

With encryption enabled, each binlog metadata record includes an `encryption` object.

The object contains the following parts:

* File key envelope: KEK ID, optional IV, wrapped file key (`data_hex`), and optional AEAD tag for Galois/Counter Mode (GCM)

* File data envelope: data cipher name and IV for CTR mode

The server stores this metadata so the server can recover the file key and decrypt binlog data from storage.

## Related topics

* [SSL and TLS connections](ssl-tls-connections.md)

* [Configuration reference](configuration-reference.md#keyring-optional)

* [Storage reference](storage-reference.md)

* [Get help](get-help.md)
