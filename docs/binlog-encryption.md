# Binlog storage encryption

Percona Binary Log Server encrypts binary log data before the server writes the data to storage.

With encryption enabled, each stored binlog file uses a data-encryption cipher.

The server wraps each per-file key with a key-encryption key (KEK) from a local keyring.

Binlog storage encryption is available in Percona Binary Log Server 0{{ release }}.

## How encryption works

Add the optional `storage.encryption` section to the JSON configuration file.

The server then completes the following steps:

1. Loads encryption keys from the keyring URI

2. Selects the configured KEK (`kek_id`) from that keyring

3. Creates a file key for each binlog file and wraps the file key with the KEK

4. Encrypts binlog file data with the configured data cipher

5. Stores per-file encryption envelopes in the binlog metadata JSON file

A data cipher example is `AES-256-CTR`.

Encryption applies to binlog data files that the storage backend writes.

Supported storage backends are `file` and `s3`.

Storage encryption differs from [Transport Layer Security (TLS) for the MySQL connection](ssl-tls-connections.md).

## Configuration file location and how to apply changes

Binary Log Server does not use a fixed system path for the configuration file.

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

Add a `storage.encryption` object to the configuration file:

```json
{
  "storage": {
    "backend": "file",
    "uri": "file:///var/lib/pbs/vault",
    "encryption": {
      "format": "generic",
      "keyring_uri": "file:///var/lib/pbs/keyring/keyring_data.json",
      "kek_id": "alpha",
      "cipher": "AES-256-CTR"
    }
  }
}
```

### Configuration parameters

| Parameter | Required | Description |
|-----------|----------|-------------|
| `storage.encryption.format` | Yes | Encryption format. The only supported value is `generic`. |
| `storage.encryption.keyring_uri` | Yes | URI of the keyring JSON file. The only supported scheme is `file://` on the local filesystem. Example: `file:///var/lib/pbs/keyring/keyring_data.json`. |
| `storage.encryption.kek_id` | Yes | ID of the KEK in the keyring. The ID must exist in the keyring file. |
| `storage.encryption.cipher` | Yes | Cipher for binlog file data. Example: `AES-256-CTR`. Use a streaming cipher such as `*-CTR` or `*-GCM`. |

Omit `storage.encryption` to store binlog files without encryption.

!!! note

    The encryption format in storage metadata must match `storage.encryption.format` in the configuration file.

    A mismatch causes storage initialization to fail.

## Generate key-encryption keys

Do not copy the sample `data_hex` values from the documentation or from `keyring_data.json` in the source tree.

Create each KEK with a cryptographically secure random generator.

Match the key length to the cipher name in the keyring record:

| Cipher name pattern | Key length | Hex characters for `data_hex` | Example command |
|---------------------|------------|-------------------------------|-----------------|
| `*-128-*` | 16 bytes | 32 | `openssl rand -hex 16` |
| `*-192-*` | 24 bytes | 48 | `openssl rand -hex 24` |
| `*-256-*` | 32 bytes | 64 | `openssl rand -hex 32` |

Example workflow:

1. Choose a KEK cipher, for example `AES-256-GCM`

2. Generate key material: `openssl rand -hex 32`

3. Create or update the keyring JSON file with a unique `id`, the cipher name, and the hex output as `data_hex`

4. Set filesystem permissions so only the Binary Log Server process user can read the keyring file

5. Set `storage.encryption.kek_id` to that key `id`

6. Set `storage.encryption.cipher` to the data cipher for binlog file content, for example `AES-256-CTR`

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
      "id": "alpha",
      "cipher": "AES-256-GCM",
      "data_hex": "<OUTPUT_OF_openssl_rand_-hex_32>"
    }
  ]
}
```

| Field | Description |
|-------|-------------|
| `version` | Keyring format version. The value must be `1`. |
| `keys` | Array of key records. |
| `keys[].id` | Unique string ID for the key. Set `storage.encryption.kek_id` to this value for the active KEK. |
| `keys[].cipher` | Symmetric cipher for this key. Examples: `AES-256-GCM`, `AES-128-ECB`. The server uses this cipher to wrap file keys. |
| `keys[].data_hex` | Key material as a hexadecimal string. Length must match the cipher name. See [Generate key-encryption keys](#generate-key-encryption-keys). |

Restrict filesystem permissions on the keyring file.

A user who can read the keyring and the encrypted binlogs can decrypt the data.

## Verify that binlogs are encrypted

The `list` command does not print encryption fields.

Use the following checks.

### Startup log

On start, Binary Log Server writes encryption details to the logger destination from `logger.file`.

Look for lines that report:

* Binlog storage encryption format

* Binlog storage encryption keyring URI

* Keyring status and loaded key IDs

* Active KEK ID and KEK cipher

### Storage metadata

Open `metadata.json` in the storage URI.

Confirm that the `encryption` field is set to `generic` when encryption is enabled.

### Per-binlog metadata

For each binlog file `BINLOG_NAME`, open the sidecar metadata file `BINLOG_NAME.json` in the same storage location.

Confirm that the metadata includes an `encryption` object.

| Field | What to confirm |
|-------|-----------------|
| `encryption.file_key_envelope.kek_id` | KEK ID used to wrap the file key |
| `encryption.file_data_envelope.cipher` | Data cipher used for the binlog file |
| `encryption.file_key_envelope.data_hex` | Wrapped file key is present |
| `encryption.file_data_envelope.iv_hex` | Initialization vector (IV) for the data cipher is present |

New binlog files written with encryption enabled include this `encryption` object.

## Existing unencrypted binlogs

Storage encryption mode is fixed when the storage is first initialized.

The server stores the encryption format in `metadata.json`.

Later runs must use the same encryption setting:

* Storage created without `storage.encryption` must keep encryption disabled

* Storage created with `storage.encryption.format` set to `generic` must keep the same format

If the configuration and `metadata.json` disagree, storage initialization fails.

Encrypted and unencrypted binlogs do not share one storage after a configuration change.

To move from unencrypted storage to encrypted storage:

1. Create a new empty storage URI

2. Enable `storage.encryption` in the configuration file for that URI

3. Run `fetch` or `pull` against the new storage

4. Keep or purge the old unencrypted storage as a separate decision

## Key-encryption key rotation, backup, and loss

Binary Log Server has no built-in KEK rotation command.

Manage keys in the keyring file and in the configuration file.

### Backup

Copy the keyring JSON file to a secure offline location before you change keys.

Protect backups with the same access controls as the live keyring.

Without the KEK material, encrypted binlogs that use that KEK cannot be decrypted.

### Rotation for new binlog files

1. Generate a new KEK and add a new key record to the keyring file

2. Keep every old KEK that older binlog metadata still references

3. Set `storage.encryption.kek_id` to the new key ID

4. Stop `pull` if the process is running

5. Start `fetch` or `pull` again

New binlog files use the new KEK ID in `file_key_envelope.kek_id`.

Older binlog files keep the previous KEK ID in their metadata.

### Access to binlogs encrypted with an older key

Keep the older KEK records in the same keyring file.

The server needs those keys to unwrap file keys for older metadata.

Do not remove an old KEK while any retained binlog metadata still lists that `kek_id`.

### Loss or removal

If a KEK is lost or removed from the keyring, binlog files that reference that `kek_id` cannot be decrypted.

Restore the KEK from backup before you need to read those files.

## Per-file encryption metadata

With encryption enabled, each binlog metadata record includes an `encryption` object.

The object contains the following parts:

* File key envelope: KEK ID, optional IV, wrapped file key (`data_hex`), and optional Authenticated Encryption with Associated Data (AEAD) tag for Galois/Counter Mode (GCM)

* File data envelope: data cipher name, IV for streaming modes (`*-CTR` or `*-GCM`), and optional AEAD tag for GCM modes

The server uses this metadata to recover the file key and decrypt binlog data from storage.

## Related topics

* [SSL and TLS connections](ssl-tls-connections.md)

* [Get help](get-help.md)
