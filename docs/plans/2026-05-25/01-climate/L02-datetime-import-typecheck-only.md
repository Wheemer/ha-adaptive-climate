# Low 02: `datetime` import used only as type hint

**File:** `custom_components/adaptive_climate/climate.py:7`

**Problem:** With `from __future__ import annotations`, datetime can be TYPE_CHECKING-only.

**Fix:**
1. Move `datetime` into `if TYPE_CHECKING:` block.
2. Keep `timedelta` at top (runtime usage).

**Test:** Pyright clean.

**Risk:** Low.

**Depends on:** none.

**Blocks:** none.
