# Percona Binary Log Server documentation

This repository holds the source files for Percona Binary Log Server documentation.

Percona Binary Log Server is a command-line utility.

The utility extends `mysqlbinlog` in `--read-from-remote-server` mode.

The utility acts as a replication client.

The utility streams binary log events from remote Oracle MySQL or Percona Server for MySQL instances.

The utility stores events on a local filesystem or in cloud storage such as Amazon Simple Storage Service (Amazon S3).

## Table of contents

* [About the project](#about-the-project)

* [How to use these docs](#how-to-use-these-docs)

* [Documentation structure](#documentation-structure)

* [Contributing](#contributing)

* [License](#license)

* [Resources](#resources)

## About the project

Percona Binary Log Server supports the following tasks:

* Fetch binary logs and store them locally or in Amazon S3

* Reconnect and continue from the last stored position after a stop or failure

* Find binlog files by timestamp or Global Transaction Identifier (GTID) set

* Use modern MySQL replication features

The repository holds user guides, operations manuals, and developer documentation.

## How to use these docs

For the software source code, see the [main repository](https://github.com/Percona-Lab/percona-binlog-server).

The documentation uses Markdown.

Browse the files on GitHub, or open the rendered docs from [Resources](#resources).

## Documentation structure

* `docs/`: Documentation source files

* `docs/ssl-tls-connections.md`: Secure Sockets Layer (SSL) and Transport Layer Security (TLS) options for the MySQL replication connection

* `docs/binlog-encryption.md`: Binlog storage encryption and keyring format

## Contributing

To contribute documentation:

1. Fork the repository

2. Create a branch for your changes

3. Open a pull request (PR) that describes the changes

Read the [Contributing Guide](contributing.md) and the [Code of Conduct](code-of-conduct.md) before you submit changes.

To report a documentation bug or a product feature request, use the [Jira issue tracker](https://jira.percona.com) or [GitHub Issues](https://github.com/Percona-Lab/percona-binlog-server/issues).

## License

Percona Binary Log Server documentation uses the [Creative Commons Attribution 4.0 International License](https://creativecommons.org/licenses/by/4.0/).

## Resources

* Main repository: [Percona-Lab/percona-binlog-server](https://github.com/Percona-Lab/percona-binlog-server)

* Community forum: [Percona Community Forum](https://forums.percona.com/)

* Blog: [Percona Database Performance Blog](https://www.percona.com/blog)

For more information about Percona open-source software, visit [percona.com](https://www.percona.com).
