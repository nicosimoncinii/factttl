# Changelog

All notable changes to FactTTL will be documented here.

The project is in development. No public product release has been made.

## Unreleased

### Changed

- Browser extension 0.4.0 is a passive verification surface: it no longer
  reads, changes, blocks, or submits the message composer.
- Model-visible verification, corrections, and persistent history now use the
  FactTTL MCP tools and their structured results.

### Fixed

- The browser extension recognizes ChatGPT product-search shortcuts as
  searches without a selected offer and can request direct merchant links
  without fetching the private ChatGPT destination.
- Product images and favicon assets no longer count as merchant references.
- Connection errors and missing evidence do not establish that a product is
  out of stock.
- Settings identify the browser-to-local-service connection separately from
  the MCP app and tunnel.

This changelog will follow [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and release versions will follow [Semantic Versioning](https://semver.org/).
