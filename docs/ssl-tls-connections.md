# SSL and TLS connections

Percona Binary Log Server can encrypt the replication connection to the source MySQL or Percona Server for MySQL instance.

Configure encryption with the optional `connection.ssl` and `connection.tls` sections in the JSON configuration file.

Secure Sockets Layer (SSL) and Transport Layer Security (TLS) protect data in transit between Binary Log Server and the source.

For storage encryption configuration and metadata, see [Binlog storage encryption](binlog-encryption.md).

## Example configuration

```json
{
  "connection": {
    "host": "127.0.0.1",
    "port": 3306,
    "user": "rpl_user",
    "password": "rpl_password",
    "connect_timeout": 20,
    "read_timeout": 60,
    "write_timeout": 60,
    "ssl": {
      "mode": "verify_identity",
      "ca": "/etc/mysql/ca.pem",
      "capath": "/etc/mysql/cadir",
      "crl": "/etc/mysql/crl-client-revoked.crl",
      "crlpath": "/etc/mysql/crldir",
      "cert": "/etc/mysql/client-cert.pem",
      "key": "/etc/mysql/client-key.pem",
      "cipher": "<SSL_CIPHER_LIST>"
    },
    "tls": {
      "ciphersuites": "<TLS_CIPHERSUITES>",
      "version": "<TLS_VERSION>"
    }
  }
}
```

## `connection.ssl` parameters

| Parameter | Required | Description |
|-----------|----------|-------------|
| `connection.ssl.mode` | Yes, when the section is present | Security mode for the connection. Allowed values: `disabled`, `preferred`, `required`, `verify_ca`, `verify_identity`. Matches the MySQL client [`--ssl-mode`](https://dev.mysql.com/doc/refman/8.4/en/connection-options.html#option_general_ssl-mode) option. |
| `connection.ssl.ca` | No | File that lists trusted Certificate Authorities (CAs) ([`--ssl-ca`](https://dev.mysql.com/doc/refman/8.4/en/connection-options.html#option_general_ssl-ca)). |
| `connection.ssl.capath` | No | Directory of trusted CA certificate files ([`--ssl-capath`](https://dev.mysql.com/doc/refman/8.4/en/connection-options.html#option_general_ssl-capath)). |
| `connection.ssl.crl` | No | Certificate Revocation List (CRL) file ([`--ssl-crl`](https://dev.mysql.com/doc/refman/8.4/en/connection-options.html#option_general_ssl-crl)). |
| `connection.ssl.crlpath` | No | Directory of CRL files ([`--ssl-crlpath`](https://dev.mysql.com/doc/refman/8.4/en/connection-options.html#option_general_ssl-crlpath)). |
| `connection.ssl.cert` | No | Client X.509 certificate ([`--ssl-cert`](https://dev.mysql.com/doc/refman/8.4/en/connection-options.html#option_general_ssl-cert)). |
| `connection.ssl.key` | No | Private key for the client certificate ([`--ssl-key`](https://dev.mysql.com/doc/refman/8.4/en/connection-options.html#option_general_ssl-key)). |
| `connection.ssl.cipher` | No | Allowed ciphers for connection encryption ([`--ssl-cipher`](https://dev.mysql.com/doc/refman/8.4/en/connection-options.html#option_general_ssl-cipher)). |

## `connection.tls` parameters

| Parameter | Required | Description |
|-----------|----------|-------------|
| `connection.tls.ciphersuites` | No | Allowed TLS 1.3 cipher suites ([`--tls-ciphersuites`](https://dev.mysql.com/doc/refman/8.4/en/connection-options.html#option_general_tls-ciphersuites)). |
| `connection.tls.version` | No | Allowed TLS protocol versions ([`--tls-version`](https://dev.mysql.com/doc/refman/8.4/en/connection-options.html#option_general_tls-version)). |

## Recommended practices

* Use `verify_identity` or `verify_ca` in production so the client validates the server certificate

* Store CA, certificate, and key files outside world-readable paths

* Restrict filesystem permissions on those files

* Match TLS versions and cipher suites to the source MySQL or Percona Server for MySQL configuration

## Related topics

* [Binlog storage encryption](binlog-encryption.md)

* [Configuration reference](configuration-reference.md#connectionssl)

* [Get help](get-help.md)
