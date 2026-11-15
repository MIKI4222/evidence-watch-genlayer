# State model

All persistent fields are declared in the class body with explicit, fully instantiated generic types. Records are `@allow_storage @dataclass` classes made only of `str`, `bool`, `Address`, `u32`. Lists and objects are stored as compact JSON strings (this avoids nested generic collections).

```python
class EvidenceWatch(gl.contract.Contract):
    sources: DynArray[Source]
    checks: DynArray[Check]            # ring buffer slots
    source_index: TreeMap[str, u64]    # source_id            -> index in sources
    url_index: TreeMap[str, u64]       # "<owner>|<url>"      -> index in sources (duplicate guard)
    check_index: TreeMap[str, u64]     # "<source_id>:<slot>" -> index in checks
```

## `Source`

`source_id`, `owner`, `url`, `name`, `description`, `instructions`, `reference_context`, `watch_text` (one item per line), `watch_count`, `status` (`REGISTERED`/`ACTIVE`/`DEACTIVATED`), `baseline_json` (compact accepted snapshot), `baseline_version`, `latest_version`, `latest_status`, `latest_summary`, `last_success_version`, `last_success_at`, `registered_at`, `updated_at`.

Baseline snapshot JSON: `title`, `source_type`, `subject`, `summary`, `version_info`, `observed_date`, `items: [{item, present, value}]` (at most 8 items, values at most 160 characters).

## `Check`

`source_id`, `version`, `prev_version`, `kind` (`BASELINE`/`CHECK`), `status`, `title`, `summary`, `added_json`, `removed_json`, `modified_json`, `affected_json`, `findings_json`, `items_json`, `confidence`, `observed_at`, `baseline_version` (baseline in effect after the record), `baseline_updated`, `caller`.

## Versions

Version 1 is the baseline record; every later check (including failed ones) adds one. `latest_version` is the counter, `get_version_count` returns it, `prev_version` links records.

## Bounded history

Version `n` is stored in slot `(n-1) % MAX_HISTORY` (20). Once a source has more than 20 records the oldest slot is overwritten in place, so storage per source is capped at 20 `Check` records regardless of how many checks are run. `get_check_history` returns the retained records newest first; a slot is only returned if its stored version matches (overwritten versions are gone). The accepted baseline and the latest/last-success summary live on `Source`, so they are never lost.

## Size limits

Description 1,000, instructions 1,000, context 1,000 characters; at most 8 watch items of 120; stored values 160; findings 8 x 200; summary 600; page text sent to the model 12,000. These bound storage and calldata; real GenVM storage and serialisation limits were not measured.
