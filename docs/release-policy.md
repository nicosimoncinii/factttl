# Compatibility and release policy

Status: policy for the personal testing phase; no 1.0 release is announced.

## Versions and compatibility

The Python package, browser extension and serialized report schemas have
separate versions. A package version change does not silently reinterpret a
stored schema. JSON input/report schema version 1 and policy schema version 1
retain their documented timestamp, expiry and unknown-state semantics.

During 0.x, applications must pin their package version. Patch releases correct
bugs without intentionally removing public imports or fields. Incompatible
public API changes require a minor version change, migration notes and updated
examples. A public symbol scheduled for removal is documented as deprecated
for at least two minor releases before removal, unless a security correction
requires immediate removal; that exception must be explained in release notes.

The supported embedding surface is the symbols in `factttl.__all__`, documented
in `python-api.md`. Underscore-prefixed helpers, bridge internals, extraction
heuristics and merchant selectors are not stable embedding interfaces.
Freshness is never silently promoted to factual verification by a migration.

## Platform support

The deterministic core targets Python 3.11 and later. CI checks Python 3.11 on
Windows, Linux and macOS. Optional MCP, browser and model runtimes have their
own requirements. Passing core CI does not demonstrate local model speed,
accuracy, or browser compatibility on every machine.

Local AI is optional. Machines without a supported installed model can still
run offline freshness evaluation and explicitly enabled public source checks.
Hardware profiles must expose limits rather than silently drop claim text.

## Releases

Each release must include its source revision, dependency lockfile, migration
notes, test results, known limitations and changes to outbound network behavior.
Browser packages must identify whether they are signed. Unsigned development
packages are never described as normal permanent Firefox installations.

Before 1.0, review the public API, schema migration tests, privacy boundaries,
supported adapters and compatibility matrix. Stable release support is
best-effort open source support, with no uptime or response-time SLA. Security
reports follow `SECURITY.md`; secrets and private conversations should never be
included in public bug reports.

## Security updates

Fixes target the latest supported release. A vulnerability in an old optional
provider may require disabling that provider until an update is available.
Security fixes must preserve evidence attribution and cannot turn errors or
missing sources into positive verification results.
