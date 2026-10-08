# Changelog

All notable changes to FactTTL will be documented here.

The project is in development. No public product release has been made.

## Unreleased

### Fixed

- Browser extension 0.3.2 recognizes ChatGPT product-search shortcuts as
  searches without a selected offer and can request direct merchant links
  without fetching the private ChatGPT destination.
- Product images and favicon assets no longer count as merchant references.
- Correction and memory messages identify their extension origin; connection
  errors and missing evidence do not establish that a product is out of stock.
- Settings identify the browser-to-local-service connection separately from
  the optional MCP app and tunnel. Manual correction mode is documented.
- Automatic correction waits for an enabled host send button and visible
  acknowledgment; inserting text or clicking alone no longer reports success.
  Unconfirmed submits keep their reservation to prevent duplicate messages.

This changelog will follow [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and release versions will follow [Semantic Versioning](https://semver.org/).
