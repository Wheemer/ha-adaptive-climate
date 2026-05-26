# High 06: `preheat.from_dict` no per-observation try/except

**File:** `adaptive/preheat.py:374-386, 358` + caller `learning.py:1646-1655`

**Problem:** Missing key (start_temp/end_temp/etc) raises `KeyError` aborting entire restore.

**Fix:**
1. Wrap per-observation construction in try/except (`KeyError`, `ValueError`, `TypeError`).
2. Log WARN with bin_key + skip; continue.
3. Add summary log: "skipped N malformed observations".

**Test:** Unit: mix valid + malformed obs → only valid restored, no exception.

**Risk:** Low.

**Depends on:** H05.

**Blocks:** none.
