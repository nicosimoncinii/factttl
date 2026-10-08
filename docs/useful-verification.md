# Useful verification, with visible evidence

FactTTL distinguishes the claim being checked from the source used to check it.
Opening a URL establishes accessibility. It does not establish product stock,
a discount, or the accuracy of a news statement.

## What a result means

| Evidence checked | Useful conclusion | What it does not establish |
| --- | --- | --- |
| Public HTTPS response | The link opened at the observation time | Product stock or the truth of the page |
| Identified product offer | Observed price and stock; disagreement with a claimed price or availability | Checkout total or delivery to the user's address |
| Live source text with validated quotations | The inspected source supports or contradicts the complete scoped assertion | Universal truth or editorial independence |
| Explicitly limited source excerpt | Coherence or conflict with that excerpt | Agreement of omitted article sections |
| Opposing decisive source assessments | Sources conflict; the assertion remains inconclusive | That either source has been independently proven correct |
| Timeout, unread source, missing quotations | Incomplete or inconclusive check | Evidence for marking the assertion false |

The UI uses **Coerente con estratto** and **In contrasto con estratto** for
source-relative news assessments based on limited text. The support indicator
remains partial rather than a complete green certification. Dates, an expired
TTL, and the readiness of a model are never substitutes for evidence.

## What changed in the news workflow

The previous grouped-news policy converted every assessment involving a long
article into `INCONCLUSIVE`, even when a valid quotation explicitly addressed
the claim. It also discarded an existing source assessment when optional search
found no additional evidence.

Grounded assessments now remain useful within their stated scope. A supported
excerpt stays supported **as an excerpt**. Another unread or inconclusive page
does not become supported by association: each URL retains its own outcome.
The group reports the decisive source URLs, opposing evidence, incomplete
sources and whether the comparison covered all planned sources. A decisive
support/contradiction conflict still makes the grouped claim inconclusive.

The model receives one contiguous source window of at most 1,500 characters,
selected by topic overlap when necessary. Selection is not an entailment test.
Truncation is disclosed; citations must occur in both the supplied window and
the live extracted source before a decisive result is stored. Full source
agreement and independent verification are not inferred from a partial window.

The publication timestamp, when known, is passed separately to the model even
if it falls outside the selected text. The live observation timestamp is the
reference checking time, not proof that the article describes current events.
The model must ground "today", current roles and other temporal qualifiers
against that reference and source context. An archived role does not establish
today's role simply because its page was fetched today. Matching historical
claims remain eligible; an older publication does not automatically become
false or unusable. Missing current proof calls for an inconclusive assessment,
not an invented contradiction. There is no arbitrary publication-age cutoff.

## Measured public-source checks

On 2026-10-08 the complete source-reader and local-model adapter was exercised
against the [NASA Artemis page](https://www.nasa.gov/humans-in-space/artemis/).
It used the installed `qwen3:4b` model through Ollama with the CPU profile,
GPU disabled, and validated quotations from the live response.

| Assertion | Source-relative result | Measured elapsed time |
| --- | --- | ---: |
| NASA plans to send astronauts to explore more of the Moon under Artemis. | `SUPPORTED`, with an explicit excerpt scope | 24.44 seconds |
| NASA says Artemis I was a crewed flight in November 2022. | `CONTRADICTED`, with an explicit excerpt scope | 21.26 seconds |

The support citation includes:

> NASA will send astronauts on increasingly difficult missions to explore more of the Moon

The contradiction citation includes:

> an uncrewed test flight

The source's Artemis I section supplies the mission and November 2022 context. Both
complete quotation records, assessment explanations, timestamps and scope
flags are retained in the ignored local development artifact
`.factttl/news-real-scoped-proof.json`. That artifact is not a distributable
fixture or a permanently current source snapshot.

These are two successful public-source checks, not an accuracy benchmark of
all news. They do not establish production Firefox end-to-end operation or a
performance guarantee for every PC. See [hardware profiles and measured
limits](local-engine-hardware.md).

## Product checks and locality

Recognized Amazon product links are associated with their ASIN and marketplace.
Public structured data can supply the offer; privileged browser observations
can supply the primary offer actually displayed to the user. The latter are
validated for identity, freshness and bounded fields before being used.
Unknown offer and seller selectors are retained; a different seller's observation
cannot silently replace the requested offer.

Availability and price have separate outcomes. For example, a displayed
available offer at EUR 10.99 supports its stock observation but contradicts a
claim of EUR 1.00. That example is covered by an integration test with a typed
browser observation; it is not evidence that a particular Amazon listing
currently costs EUR 10.99.

A separate live check on 2026-10-08 read
[Amazon.it ASIN B0DKF9NCN1](https://www.amazon.it/dp/B0DKF9NCN1): EUR 10.99
and available stock contradicted the demonstration's EUR 1 assertion. A
read-only browser inspection also found EUR 10.99 in the primary buy box,
“Disponibilità immediata”, and enabled purchase buttons. No purchase was
made. This validates that listing at the observation time, not every merchant
or the user's Firefox extension lifecycle. Local proof artifacts are ignored
by Git.

Country and language are declared preferences, not GPS or proof of a delivery
destination. A marketplace-country mismatch is shown explicitly. Session prices
and displayed stock do not prove final checkout totals, address-specific
delivery, or availability for every user.

## Automatic source discovery: useful, still limited

Discovery is optional and disabled by default. Enabling
`-NewsDiscovery bing` sends a bounded topic query to Bing RSS. The local model
does not require a paid API key, but the query leaves the PC. Sensitive-string
filters are conservative heuristics; they do not guarantee perfect detection
of private content. See [privacy and network behavior](privacy-and-network.md).

RSS titles and snippets only locate and rank candidates. Selected publisher
pages are read through the protected HTTPS fetcher before analysis. Search
results never become factual evidence by themselves. No more than two new
publisher domains are selected per message; different domains do not prove
editorial independence.

An actual NASA/Artemis discovery probe returned only a Wikipedia NASA candidate.
Another returned unrelated pages when geographic search parameters were used.
The current adapter filters topic overlap and omits those unreliable parameters.
Country remains an interpretation/cache hint and language affects the source
request; geographically targeted search is not guaranteed. Search coverage can
be poor, incomplete, or unavailable. Existing grounded source assessments remain
attributed to their sources while that limitation stays visible.

General source-free prose is not automatically uploaded. The source-free
workflow recognizes bounded public roles, legal obligations with a recognized
jurisdiction, and announcements/releases of recognized public entities, even
without a news marker. Unknown private subjects, opinions, questions and
hypotheses remain excluded. Broad entity recognition, perfect privacy detection
and independent fact corroboration remain product work.
