# Integration with MilestoneJudge (future)

EvidenceWatch is fully independent: it does not import, call or require MilestoneJudge, and MilestoneJudge was not modified. This document describes a small, stable interface for a later combined application. **Nothing here was implemented or tested across contracts.**

## Independent use

Register a source, create a baseline, run checks, read `get_check_history` / `get_integration_status`. No other contract is needed.

## Shared identifiers

| Concept | EvidenceWatch field | Notes |
|---|---|---|
| `source_id` | `source_id` (string, 3-64 chars) | the key a milestone would reference |
| `source_url` | `source_url` | the monitored page |
| `source_owner` | `owner` / `source_owner` | EvidenceWatch only lets the owner trigger checks |
| `baseline_version` | `baseline_version` | version whose snapshot is the accepted baseline |
| `latest_version`, `latest_status` | `latest_version`, `latest_status` | `UNCHANGED`, `MINOR_CHANGE`, `MATERIAL_CHANGE`, `SOURCE_UNAVAILABLE`, `INCONCLUSIVE` (or `BASELINE` right after creation) |
| `latest_check_summary` | `latest_check_summary` | model-written summary (paraphrase) |
| `last_successful_check` | `{version, at}` | last record whose page was retrieved and classified |

`get_integration_status(source_id)` returns exactly these fields in one dictionary. `get_latest_check` and `get_check_history` add the added / removed / modified information and affected requirements.

## Suggested workflow

1. The executor (or whoever owns the evidence) registers the evidence URL in EvidenceWatch and creates a baseline.
2. The milestone creator creates a milestone in MilestoneJudge and stores the EvidenceWatch `source_id` next to the evidence (in the explanation text today; a dedicated field would need a MilestoneJudge change, which is out of scope here).
3. Before evaluation the application reads `get_integration_status(source_id)` and, if `latest_status` is `MATERIAL_CHANGE` since the submission, shows it to the evaluator or includes it as context.
4. The evaluator judges the milestone as usual. EvidenceWatch evidence is context, not a verdict.

## Recommended method: application-level adapter

Contracts cannot read each other's storage. The simplest verified approach is a thin adapter in the consuming application (script, backend or frontend using the GenLayer SDK) that calls the view `get_integration_status` on EvidenceWatch and `get_milestone`/`get_verification` on MilestoneJudge and joins them by `source_id`. This needs no changes to either contract.

```text
status   = evidence_watch.get_integration_status(source_id)
milestone = milestone_judge.get_milestone(milestone_id)
if status.latest_status == "MATERIAL_CHANGE" and status.latest_version > milestone_submission_version: warn
```

## Direct contract-to-contract calls

The v0.3 SDK migration notes list a `gl.contract.get_at(address)` helper (formerly `gl.ContractAt`) for contract interaction. Calling EvidenceWatch views from inside MilestoneJudge, or from MilestoneJudge's non-deterministic evaluation, was **not** implemented or verified, and doing so has open questions: whether views may be called inside a consensus block, fee behaviour, and the cost of reading history. If you try it, call only the small `get_integration_status` view and pass the result into the prompt as untrusted context.

## Limitations

- Only the source owner can trigger checks; a milestone creator who is not the owner must ask the owner.
- "Changed since submission" needs the application to remember which `latest_version` was current at submission time.
- EvidenceWatch reports availability and semantic change, never authenticity or cryptographic proof of what a page said at a given time.
