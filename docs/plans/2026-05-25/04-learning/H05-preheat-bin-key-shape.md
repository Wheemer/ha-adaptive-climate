# High 05: `preheat.from_dict` no bin_key shape validation

**File:** `adaptive/preheat.py:373-374`

**Problem:** `tuple(obs_data["bin_key"])` blindly accepts any length. 3-element list silently creates wrong-keyed bin that `get_learned_rate` never reads.

**Fix:**
1. Guard: `if not isinstance(bk, (list, tuple)) or len(bk) != 2: log + continue`.
2. Validate element types: both str.

**Test:** Unit: corrupt obs (3-len, wrong types) → skipped, valid obs restored.

**Risk:** Low.

**Depends on:** none.

**Blocks:** H06.
