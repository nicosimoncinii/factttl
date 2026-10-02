# Terminology

| Term | Meaning |
|---|---|
| Claim | A proposition expressed in text or supplied as structured input. It may be true, false, uncertain, or underspecified. |
| Claim candidate | Text identified as a possible claim; extraction alone does not establish that it is atomic or factual. |
| Truth | Whether a claim corresponds to reality. FactTTL does not infer truth from age. |
| Freshness | Whether a claim is within its configured review interval at an evaluation time. |
| Confidence | A calibrated or provider-reported estimate about a judgment. It is not a substitute for evidence or freshness. |
| Source quality | An assessment of a source's authority, relevance, and reliability. It is separate from whether it supports a specific claim. |
| Verification | A recorded attempt to compare a claim with evidence. A verification outcome can remain inconclusive. |
| TTL | A configured duration after a qualifying completed evidence check before review becomes due. |
| Check time | `last_checked_at`: time of the latest completed assessment with a `SUPPORTED` or `CONTRADICTED` outcome; an inconclusive/error attempt does not reset freshness. |
| Evaluation time | The explicit instant at which a freshness status is computed, preferably in UTC. |
| Provenance | Information describing where evidence came from and when/how it was retrieved. |

## Four separate dimensions

- **Truth:** true, false, or unknown.
- **Freshness:** fresh, stale, not required, or unknown.
- **Confidence:** a measure attached to a particular assessment, if a provider supports one.
- **Source quality:** properties of evidence origin and relevance.

Examples: a claim can be true but stale; true and fresh; uncertain but fresh; or false regardless of freshness. A fresh timestamp does not make a low-quality source authoritative.
