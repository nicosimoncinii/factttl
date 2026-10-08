# Local policy configuration

FactTTL can read a user-owned TOML file. Configuration is local: loading it does
not call a provider, access the network, or read the current time. The parser
uses Python's standard-library TOML reader and Pydantic v2 validates the
supported schema.

## Example

Save this as `factttl.toml`:

```toml
schema_version = 1

[categories.software_version]
ttl = "7d"

[categories.price]
ttl = "24h"

[categories.market_data]
ttl = "1h"

[categories.never_review]
review_disabled = true
```

Then load it in Python:

```python
from factttl.config import load_policy

policy_config = load_policy("factttl.toml")
category_policy = policy_config.category_policy("software_version")
```

Pass `category_policy` to `resolve_policy(category=..., temporal_class=...)`.
The caller still supplies per-claim overrides and the temporal class, then
passes the resulting policy to `evaluate_freshness` with an explicit evaluation
time.

## Schema and defaults

- `schema_version` is required and currently must be the integer `1`.
- `categories` is a required table. It may be empty (`categories = {}`).
- Each category key uses lowercase letters, digits, and underscores, and starts
  with a lowercase letter (for example, `company_role`).
- Each category table must set exactly one of `ttl` or
  `review_disabled = true`.
- TTLs are non-negative integer durations with one unit: `s` (seconds), `m`
  (minutes), `h` (hours), `d` (24-hour days), or `w` (7-day weeks). `0s` is
  valid and makes a completed check immediately due.
- Categories absent from the file have no category policy. Their behavior is
  decided by the freshness contract: an unconfigured `STABLE` class disables
  routine review; another unconfigured or missing class resolves to `UNKNOWN`.
  There are no implicit category TTL defaults.
- Resolution order remains per-claim setting, category setting, then the
  `STABLE` fallback. Thus a per-claim TTL can override a category disable, and
  a per-claim disable can override a category TTL.

Invalid TOML, unknown fields, unsupported schema versions, malformed TTLs, and
invalid policy combinations raise `PolicyConfigError` with the relevant config
location and correction guidance. Keep this file free of secrets; credentials
belong in a dedicated secret store, not in freshness policy.
