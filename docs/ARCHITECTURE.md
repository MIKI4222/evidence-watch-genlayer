# Architecture

One contract class (`EvidenceWatch`), two record types (`Source`, `Check`), three indexes. Everything non-deterministic lives in two module-level helpers (`_assess_baseline`, `_assess_check`) that are only called inside the consensus block.

## Components

| Component | Role |
|---|---|
| Source registry (`sources`, `source_index`, `url_index`) | Owner, URL, instructions, watch items, lifecycle status, accepted baseline, latest result |
| Check history (`checks`, `check_index`) | Bounded ring buffer of accepted records per source |
| `_assess_*` | Fetch the page, build the prompt, call the LLM, normalize |
| `_normalize_*`, `_derive_status`, `_item_class` | Turn model output into the canonical result; derive classification |
| `_*_is_valid`, `_*_equivalent` | Leader-output validation and consensus comparison |
| `_run_nondet` | Leader/validator entry point (`run_nondet_default` on v0.3) |

## Lifecycle

```
(none) --register_source--> REGISTERED --create_baseline--> ACTIVE --deactivate_source--> DEACTIVATED
                                                              |  check_source (repeatable)
```

| Action | Who | Allowed in | Effect |
|---|---|---|---|
| `register_source` | anyone (becomes owner) | n/a | creates `REGISTERED` source; rejects duplicate ID and duplicate owner+URL |
| `update_source` | owner | `REGISTERED`, `ACTIVE` | name, description, instructions, context |
| `create_baseline` | owner | `REGISTERED` only | version 1 record, source becomes `ACTIVE` |
| `check_source` | owner | `ACTIVE` only | new record `version+1`; baseline rules below |
| `deactivate_source` | owner | `REGISTERED`, `ACTIVE` | no further baseline/check; reads still work |

Every other transition is refused with `[EXPECTED] ...` (check before baseline, second baseline, anything on a deactivated source, non-owner calls).

## Snapshot creation (baseline)

Baseline consensus succeeds only if the source was retrieved and the validators agree on which watch items the page states. If the source is unavailable or empty, `create_baseline` **reverts** and nothing is stored (no partially initialised source).

## Change detection

See [CONSENSUS.md](CONSENSUS.md). Result per check: status, per-item classes, added / removed / modified information, affected requirements, important findings, summary, confidence; stored as a compact record. Raw HTML is never stored.

## Baseline update rules

`UNCHANGED` keeps the baseline. `MINOR_CHANGE` and `MATERIAL_CHANGE` replace it with the new snapshot (the baseline version becomes the record's version). `SOURCE_UNAVAILABLE` and `INCONCLUSIVE` are recorded without touching the baseline or `last_successful_check`, so a temporary outage never destroys the last reliable state.

## Time

Timestamps are the transaction time (`datetime.now(timezone.utc)`), recorded as `registered_at`, `updated_at`, `observed_at` and `last_successful_check.at`. They are not proof of when the page itself changed.
