# EvidenceWatch

**A GenLayer Intelligent Contract for decentralized semantic monitoring of web sources: it tells you not just *that* a page changed, but whether the change is minor or material for the things you care about, and validators must agree before the result is stored.**

> **Status.** Deployed and partly exercised on GenLayer Studio Next (GenVM v0.3) on 5-6 Nov 2026, on two deployments: the earlier version and the final version in this repository. Baseline creation, an unchanged check and a material change reached consensus with three validator models each. See [Tested on Studio Next](#tested-on-studio-next) for exactly what was and was not run live. The 69 local tests run against a *simulation* of the SDK with scripted pages and answers and do not prove real validator consensus or real model behaviour.

## What it is

An owner registers a source URL together with **watch items** (for example "Project deadline", "Eligibility requirements", "Supported features"). EvidenceWatch records a compact **baseline** (per watch item: is it stated, and what does it say). Every later **check** re-fetches the page and, independently on the leader and on every validator, judges each watch item against the baseline. The contract (not the model) derives one of five classifications and keeps a bounded **version history**.

| Classification | Meaning |
|---|---|
| `UNCHANGED` | No meaningful change in any watch item |
| `MINOR_CHANGE` | Wording / formatting / typo changes that do not alter meaning or any value |
| `MATERIAL_CHANGE` | A watch item was modified, added or removed, or the page is now about a different subject |
| `SOURCE_UNAVAILABLE` | The page could not be retrieved (never treated as a change) |
| `INCONCLUSIVE` | Retrieved but empty, or evidence too unclear to classify |

## Why semantic monitoring

URL pings and raw diffs flag every typo fix and cookie-banner tweak, and miss a quietly moved deadline buried in rewritten prose. Watch items let the owner say what matters; independent validator re-reads decide whether that information really changed, and the accepted result is on-chain for other contracts and applications to read.

Use cases: grant requirements and deadlines, terms and policies, technical specifications, project READMEs and documentation, evidence pages cited in a dispute or milestone.

## How it works

```
register_source -> REGISTERED --create_baseline--> ACTIVE --check_source--> new record (version n+1)
                                                     |-- deactivate_source --> DEACTIVATED
```

| Check result | Record stored | Baseline |
|---|---|---|
| `UNCHANGED` | yes | kept |
| `MINOR_CHANGE`, `MATERIAL_CHANGE` | yes | replaced by the new snapshot |
| `SOURCE_UNAVAILABLE`, `INCONCLUSIVE` | yes (failed check recorded) | **kept** |
| consensus fails / undetermined | nothing | kept |

Per watch item the classification is computed in code: absent before and now = unchanged; absent then present = `ADDED`; present then absent = `REMOVED`; present both times = the model's judgement (`UNCHANGED` / `MINOR` / `MODIFIED` / `UNCLEAR`). Overall: any `MODIFIED`/`ADDED`/`REMOVED` or a changed subject = `MATERIAL_CHANGE`; else any `UNCLEAR` = `INCONCLUSIVE`; else any `MINOR` = `MINOR_CHANGE`; else `UNCHANGED`. Confidence is informational only.

## Consensus (Equivalence Principle)

`create_baseline` and `check_source` use the custom leader/validator pattern through `gl.vm.run_nondet_default` (falls back to `run_nondet_unsafe` on GenVM v0.2).

- **Leader:** fetches the page, cleans it (scripts, styles, nav, footer removed; 12,000 characters max), asks the LLM, normalizes the answer.
- **Validators:** do not trust the leader. They check its output is well formed and that the classification follows from its per-item results, then **fetch the page themselves and run the full assessment** against the same stored baseline and compare: overall status, accessibility, whole-subject change, and every watch item's classification (which encodes added / removed / modified / minor / unclear). Values, notes, findings, summaries and confidence are not compared.
- State is written only after consensus; a failed or undetermined round changes nothing.

Details: [docs/CONSENSUS.md](docs/CONSENSUS.md).

## Public API

| Method | Kind | Notes |
|---|---|---|
| `register_source(source_id, source_url, source_name, description, instructions, reference_context, watch_items)` | write | `watch_items`: separate with `\|\|`; empty = 4 defaults. `source_id`: 3-64 chars `[a-z0-9._-]`. |
| `update_source(source_id, source_name, description, instructions, reference_context)` | write | Owner only. URL and watch items are fixed. |
| `deactivate_source(source_id)` | write | Owner only. History stays readable. |
| `create_baseline(source_id)` | write | Owner only, once. Use a generous fee. |
| `check_source(source_id)` | write | Owner only, source `ACTIVE`. Use a generous fee. |
| `get_source`, `get_baseline`, `get_latest_check`, `get_check_history`, `get_source_count`, `get_version_count` | view | History: newest first, last 20 records. |
| `get_integration_status(source_id)` | view | Stable read interface for other contracts/apps ([docs/INTEGRATION.md](docs/INTEGRATION.md)). |

## Deploy and try

1. Open [Studio Next](https://studio-next.genlayer.com/), paste `contracts/evidence_watch.py` (keep the two header lines), deploy with no arguments.
2. `register_source`, then `create_baseline`, then `check_source`. Examples and expected shapes: [docs/USAGE.md](docs/USAGE.md).

The `Depends` runner hash is tied to the GenVM bundle (this file uses the one reported for Studio Next bundles v0.6.0-rc9/rc10). If schema loading fails with `runner absent`/`malformed`, copy the first two lines of a built-in example contract in your Studio build.

## Tests

`python -m unittest discover -s tests -v` (69 tests, no dependencies). They cover registration and validation, access control, baseline rules, change classification (no change, minor, deadline, requirement, functionality, addition, removal, replaced source), unavailable/empty/inconclusive handling, malformed model output, validator disagreement, prompt-injection scenarios, ring-buffer history and no state change after failed consensus, plus static checks of the source. **Simulation only**, see the status note; scripted answers decide what the "model" says.

## Security

Page content is untrusted: delimited blocks, forged delimiters neutralized, explicit rules not to follow embedded instructions, owner-defined watch items and instructions always take priority. The model never picks the final classification, so an injected "report no changes" can at most skew individual item answers, which independent validators must reproduce. URLs: http(s) only, no credentials, private/loopback hosts refused. Availability is not authenticity, and **EvidenceWatch provides no cryptographic proof of historical page content.**

## Tested on Studio Next

Live, GenVM v0.3.0-rc10, 3 agreeing validator models per run, using a public gist as the monitored page (watch items: deadline, eligibility, accepted formats).

**Final version (this repository), 6 Nov 2026**

| Scenario | Result |
|---|---|
| `register_source` | `REGISTERED`, owner and three watch items stored |
| `create_baseline` | 3 of 3 items found with correct values; `observed_date` and `version_info` empty (not invented); source `ACTIVE`, `baseline_version` 1 |
| `check_source`, page served from a stale cache | `UNCHANGED`, all items `UNCHANGED`, baseline kept (version 2 recorded) |
| `check_source`, deadline changed 15 -> 20 Nov | `MATERIAL_CHANGE`; `modified_information` and `affected_requirements` list the deadline; baseline replaced (version 3); baseline `summary` reads "Updated in version 3: ..." (no stale text) |

Transaction hashes for these runs: see the transaction history of the deployed contract at `<CONTRACT_ADDRESS>`.

**Earlier version (before two small fixes), 5 Nov 2026**

| Scenario | Result | Transaction |
|---|---|---|
| `create_baseline` by a non-owner | refused: `[EXPECTED] only the source owner can do this` | `0x29f4cc34b0b03090dc23beeb9b7e46d8c3738f3bdc18107736a8b484ef4b8310` |
| `create_baseline` by the owner | `SUCCESS`; source `ACTIVE` | `0x79493101161ff063fa7a1b7d01d41b2722c763318673afbcae79779f088c18aa` |
| `create_baseline` again | refused: `[EXPECTED] a baseline already exists...` | `0x6e406be0a7b39136ddc100427c4282e8707d53eb86327061056c657938d2da87` |
| `check_source`, page unchanged | `UNCHANGED`, baseline kept | `0x5523e72c688844e289bbc07f3ed18593ba50af6b67ff0067704d98e24936eb85` |
| `check_source`, deadline changed 1 Dec -> 15 Nov | `MATERIAL_CHANGE`, baseline replaced (version 3) | `0x630d22db8f4b5ee78478c010895c6e7031898ebc701ff1660f78dbb0c5764256` |

The earlier version's two issues, both fixed and confirmed on the final version: the baseline `summary` kept the old deadline after an update, and the model invented an `observed_date` that was not on the page.

**Not run on a live network** (simulation tests only): `SOURCE_UNAVAILABLE` recording and baseline preservation, a page with an injected instruction, `MINOR_CHANGE`, item addition/removal, a fully replaced page, empty pages, history overflow (20 records), `update_source`, `deactivate_source`, and rejection of invalid registration inputs.

## Known limitations

- **Free-text fields are model output, not facts.** On a live run the model once filled `observed_date` with a date that is not on the page. Prompts now forbid guessing dates, but only the per-item classes are compared by validators; treat `summary`, `observed_date`, `version_info`, `important_findings` and values as paraphrase.

- **Only part of the scenarios were run live** (see the table above).
- Borderline pages can split validators (the sibling contract showed this live); then nothing is stored and the check can be retried.
- Per-item classification depends on the owner's watch items; changes outside them are only caught if the whole subject changes.
- Plain HTTP GET: JavaScript-rendered pages, logins and paywalls look empty or unavailable. Redirect handling follows the GenLayer web module defaults and was not verified. Pages are truncated to 12,000 characters.
- Only the owner can run baseline/check (prevents history flooding); a third party cannot trigger a check.
- History keeps the last 20 records per source (older ones are overwritten).
- URL and watch items cannot be edited after registration.
- Cross-contract calls to MilestoneJudge were not implemented or verified; see INTEGRATION.md.
- No payments, scheduler or background monitoring: every check is an explicit transaction.

## Layout

```
contracts/evidence_watch.py   the contract
tests/                        simulation tests + SDK stub
docs/                         ARCHITECTURE, CONSENSUS, STATE_MODEL, INTEGRATION, USAGE
```

MIT, see [LICENSE](LICENSE).
