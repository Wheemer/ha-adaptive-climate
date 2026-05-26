# Architectural 07: Derive magic numbers from constants

**File:** `adaptive/learning.py:1103, 1104, 1154, 1155, 1180, 1181, 1208, 1473`

**Problem:** `0.8`, `0.5`, `0.4` duplicated; should come from `HEATING_TYPE_CONFIDENCE_SCALE` / `CONFIDENCE_TIER_*`.

**Fix:**
1. Inventory each magic number + origin.
2. Replace with named const reference.
3. Remove duplicates.
4. Add lint rule (numeric literal in this file scope → fail).

**Test:** Behavior unchanged across heating types; existing tests pass.

**Risk:** Low.

**Depends on:** H11.

**Blocks:** none.
