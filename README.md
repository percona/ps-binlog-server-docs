# Percona Binary Log Server documentation

The repository contains the source files and resources for the documentation of the Percona Binary Log Server.

The Percona Binary Log Server is a command-line utility that serves as an enhanced version of `mysqlbinlog` in `--read-from-remote-server` mode. The utility acts as a replication client that can stream binary log events from remote Oracle MySQL or Percona Server for MySQL instances to both local filesystems and cloud storage, for example AWS S3.

## Table of Contents

* [About the Project](https://www.google.com/search?q=%23about-the-project)
* [How to Use These Docs](https://www.google.com/search?q=%23how-to-use-these-docs)
* [Documentation Structure](https://www.google.com/search?q=%23documentation-structure)
* [Contributing](https://www.google.com/search?q=%23contributing)
* [License](https://www.google.com/search?q=%23license)
* [Resources](https://www.google.com/search?q=%23resources)

## About the Project

The Percona Binary Log Server provides a robust way to:

* Stream & Archive: Fetch binary logs and store them locally or in S3.
* Resume Operations: Automatically reconnect and resume from the last point of termination.
* Search: Quickly find binlog files by Timestamp or GTID set.
* Support Modern Standards: Built with C++20 and supports advanced MySQL replication features.

The repository serves as the central hub for user guides, operational manuals, and developer documentation to help the community effectively deploy and manage the server.

## How to Use These Docs

If you are looking for the software itself, please visit the [main repository](https://github.com/Percona-Lab/percona-binlog-server).

The documentation is typically written in Markdown. You can browse the files directly here on GitHub or follow the links in our [Resources](https://www.google.com/search?q=%23resources) section for rendered versions.

## Documentation Structure

* `docs/`: Documentation source files, including user guides, architecture material, examples, and deployment guidance.

## Contributing

We encourage contributions to improve the quality of our documentation! To contribute:

1. Fork the repository.
2. Create a new branch for your documentation updates.
3. Submit a Pull Request (PR) describing your changes.

Please review the [Contributing Guide](contributing.md) and the [Code of Conduct](code-of-conduct.md) before submitting changes.

If you find a bug in the documentation or have a feature request for the tool itself, please use the [Jira issue tracker](https://www.google.com/search?q=https://jira.percona.com) or the [GitHub Issues](https://github.com/Percona-Lab/percona-binlog-server/issues) page.

## License

Percona Binary Log Server documentation is licensed under a [Creative Commons Attribution 4.0 International License](https://creativecommons.org/licenses/by/4.0/).

## Resources

* Main Repository: [Percona-Lab/percona-binlog-server](https://github.com/Percona-Lab/percona-binlog-server)
* Community Forum: [Percona Community Forum](https://www.google.com/search?q=https://forums.percona.com/)
* Blog Posts: [Percona Database Performance Blog](https://www.google.com/search?q=https://www.percona.com/blog)


*For more information about Percona's open-source software, visit [percona.com](https://www.google.com/search?q=https://www.percona.com).*
