# Low 09: try/except ImportError changes types silently

**File:** `managers/night_setback_manager.py:11-18`

**Problem:** `HomeAssistant = Any` fallback fragile. `dt_util = None` fallback unused in production.

**Fix:**
1. Use `if TYPE_CHECKING:` block for type-only imports.
2. Drop unused fallback.

**Test:** Pyright clean. Existing tests pass.

**Risk:** Low.

**Depends on:** none.

**Blocks:** none.
