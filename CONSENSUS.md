# Consensus design

Pattern: the custom leader/validator form of the Equivalence Principle, through `gl.vm.run_nondet_default(leader_fn, validator_fn)` (GenVM v0.3; the contract falls back to `run_nondet_unsafe` on v0.2). A validator that only checked JSON shape would not be consensus; here every validator re-fetches and re-judges.

## Design decision that matters most

Semantic judgements from different LLMs never match word for word, and an earlier sibling contract showed live that comparing too much (model-chosen decision, soft flags) splits validators. EvidenceWatch therefore:

1. asks the model only per-**watch item** questions with fixed definitions (present? unchanged / minor / modified / unclear?);
2. derives added / removed from presence bits and the overall classification **in code**;
3. compares only those derived, stable fields.

## Leader (`_assess_check`, `_assess_baseline`)

1. Fetch the URL with `gl.nondet.web` (GET). Non-2xx or an exception -> **`SOURCE_UNAVAILABLE`**, no model call. 2xx but fewer than 40 characters after cleaning -> **`INCONCLUSIVE`**, no model call.
2. Clean the page (scripts, styles, nav, footer, header, aside, forms, comments removed; links kept as `[link: url]`; delimiters neutralised; 12,000 characters).
3. Prompt: security rules, the owner's source definition (trusted), the accepted baseline (trusted, for checks), the page in a `<<<PAGE ...PAGE>>>` block (untrusted). Output via `gl.nondet.exec_prompt(..., response_format="json")`.
4. Normalise: exact item count, booleans, bounded text. The per-item class and the overall status are computed by the contract; any status the model volunteers is ignored.

## Validators

1. Leader did not return a value (error/rollback) -> **disagree**.
2. `_check_is_valid` / `_baseline_is_valid`: well formed and bounded; item texts and base presence equal the stored baseline; every item class follows from the presence bits; the status equals the status derived from the item classes and subject flag.
3. Run the **full assessment independently** (own fetch, own LLM, same stored baseline); any exception -> disagree.
4. Compare.

## Equivalence rules

Baseline (`create_baseline`):

| Compared | Rule |
|---|---|
| Status, accessibility | identical |
| Per watch item: present | identical |
| Per present item: stored value | bound (see below) |
| Subject, title | bound |
| Not compared | summary, source type, version / date text, confidence (no later check uses them) |

Check (`check_source`):

| Compared | Rule |
|---|---|
| Overall status, accessibility, `subject_changed` | identical |
| Per watch item: class (UNCHANGED/MINOR/MODIFIED/ADDED/REMOVED/UNCLEAR) | identical |
| Per item present now: stored value | bound |
| Subject, title, only when the result replaces the baseline (`MINOR_CHANGE`, `MATERIAL_CHANGE`) | bound |
| Not compared | notes, findings, summaries, confidence |

**Binding** (`_bound`). Free text from two LLMs never matches word for word, so every value is reduced to its *hard facts*: numbers (thousands separators and leading zeros ignored), month names (`Dec` = `December`; `may` only next to a day number), ALL-CAPS acronyms, and negations (`not`, `no`, `never`, `cannot`, `without`, `none`). If either value states hard facts, the two sets must be equal, so two different deadlines, formats or negations never bind. Values with no hard facts must share at least 30 % of their words (subject 25 %, title 50 %). An empty value binds only to an empty value.

**Grounding** (`_grounded`). The numbers, months and acronyms of a stored value must literally occur in the page. The leader rejects ungrounded values (`[LLM_ERROR]`), and every validator checks that the leader's stored values occur in its own copy of the page. A present item must carry a value.

Why this matters: the stored baseline is what later checks compare against (the prompt shows the stored values and the baseline subject, and `previous_value` in reports is taken from it). If validators bound only presence, the leader's choice between two values on the page would become the baseline unchecked and could flip a later `UNCHANGED` into `MATERIAL_CHANGE`.

Matching of classes is exact; there is no tolerance (for example `MINOR` vs `MODIFIED` is a disagreement). Because added / removed / modified information and affected requirements are derived from the item classes, agreeing on the classes is agreeing on those findings.

Known weakness: prose-only values and subjects are bound by word overlap, which is weaker than hard-fact matching; the key-token reduction does not understand synonyms or meaning.

## Failure handling

| Situation | Outcome |
|---|---|
| Source down for everyone | agreed `SOURCE_UNAVAILABLE`; recorded by `check_source`; baseline kept. `create_baseline` reverts. |
| Leader reaches the page, validators get 5xx | accessibility differs -> no majority -> nothing stored, retry |
| Empty page for everyone | agreed `INCONCLUSIVE`, no model call |
| Malformed or incomplete model output | `[LLM_ERROR]` at the leader; validators disagree; no state change |
| Validators classify differently | no majority (`UNDETERMINED`); no state change |
| Validator throws | counted as disagreement |
| Consensus value fails the final in-contract validation | revert, nothing stored |

State is written only after `_run_nondet` returns (checked by a source-parsing test). Storage is never read inside the non-deterministic functions: a plain `ctx` dict is built first.

## Prompt-injection defences

Page text is untrusted data in a delimited block with forged delimiters removed; rules say never to follow embedded instructions and to report them as findings; owner instructions and watch items outrank the page; the model never decides the final classification; independent validators must reproduce the per-item answers. Honest limit: if every validator model is fooled the same way, they agree on a wrong answer.

## What was tested

Only in simulation (see the test module docstring): scripted pages and scripted model answers drive the real leader and validator code through a simulated vote. A mutation test (validator always `True`, state written before consensus, baseline replaced on failed checks) makes the suite fail. Nothing here was run on real validators.
