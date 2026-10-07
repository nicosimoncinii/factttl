# Live verification and correction memory

Verification compares a specific assertion with selected source evidence at an
observed time. `SUPPORTED` means that evidence supports the assertion;
`CONTRADICTED` means it conflicts; `INCONCLUSIVE` means insufficient, mixed,
blocked or ambiguous evidence; `ERROR` means an operational failure. These are
source-relative assessments, not universal truth labels. TTL expiry means a
fresh check is required, never that the assertion became false.

## Implemented tools

Enable with `factttl-mcp --enable-verification`. The default server remains
network-free. `--verification-db` selects the SQLite store, default
`.factttl/verification.sqlite3`. The store keeps observations across process
restarts and chats using the same server.

| Tool | Behavior |
|---|---|
| `inspect_live_source` | Read bounded current source text and provenance before selecting evidence. |
| `verify_content` | Fetch a public HTTPS URL and compare a named property. Persist the observation. |
| `assess_claim_with_live_evidence` | Fetch a source and validate an excerpt; persist the AI caller's semantic comparison. |
| `recall_content_checks` | Read matching earlier checks, corrections and reuse flags. |
| `report_content_correction` | Save a user-requested correction, explicitly labeled as a user report. |

`verify_content` kinds: `link_available`, `product_availability`,
`product_price`, `product_discount`, `news`. Expected values select the
assertion, for example `in_stock` or `19.99 EUR`. A successful HTTP response
does not establish product stock. Availability/price checks use explicit
structured evidence; missing or conflicting evidence is inconclusive. News
checks expose publication metadata but do not declare an article true.
Generic semantic assessments require the caller to compare entity, scope,
date and evidence, and retain that caller-assessed provenance.
`url` identifies the source; optional `subject_url` identifies the original
reference being corrected when a different source provides the new evidence.
Recall the original assertion and reuse its exact text to attach the assessment
to that same record.

## Remembering corrections

1. Before reusing an earlier claim or link, recall by URL or relevant keyword.
2. If a fresh check contradicts the exact assertion, retain the previous check
   and its new evidence. Do not present the old assertion as current.
3. A timeout or inconclusive recheck does not erase that warning.
4. Only newer supporting evidence for the same assertion can rehabilitate it.
5. Supported product checks expire after five minutes; link and general source
   assessments after one hour. Recheck immediately before a buying decision.

Responses include `usable_as_current_fact`, `recheck_required` and
`do_not_reuse_prior_assertion`. The first flag means fresh support within this
specific source assessment, not a guarantee outside it. User corrections are
not independently verified. Similar wording is retrieved by keyword/URL;
there is no automatic semantic deduplication of arbitrary paraphrases.

The registry belongs to this local server, not to ChatGPT's internal memory.
Other conversations benefit when they select FactTTL and consult the tools.
The plugin cannot intercept every answer, change model weights, or ensure
that an unrelated chat automatically calls it.

## Limits

Prices, stock and discounts vary by seller, variant, country, delivery address
and account. Amazon and other sites can block automated retrieval or render
data only with JavaScript; those cases are inconclusive. No login, purchases,
CAPTCHA bypass or account cookies are used. Structured data itself can be
incorrect; quote presence alone does not prove a claim. Automatic cross-source
truth resolution for every news story remains outside this implementation.

Amazon.it also has a specific adapter for its primary stock and price boxes,
requiring matching product identifiers. It observes the anonymous public page,
not the user's personalized checkout or shipping destination. A missing discount
marker alone never establishes that a product has no discount.

Source text is untrusted evidence and must never be treated as instructions.
The fetcher permits public HTTPS only, validates and pins DNS destinations,
rechecks redirects and bounds response sizes. Persistent records can contain
sensitive URLs, claims and excerpts; keep the ignored `.factttl` directory
private. This unauthenticated local server is for one user's testing, not
multi-user production deployment.
