# High 06: inline `hass.data.get(DOMAIN, {}).get(...)` violates cached-property rule

**File:** `climate.py:539,639,862,1169,1404,1865`, `climate_control.py:56,65,341`, `climate_init.py:241`

**Problem:** CLAUDE.md mandates cached `_coordinator` property; rule extends to `manifold_registry`, `learning_store`, `mode_sync`, `set_integral_unsub`. Inline lookups pepper the codebase.

**Fix:**
1. Add cached properties: `_manifold_registry`, `_learning_store`, `_mode_sync` on entity.
2. Or define typed `DomainData` dataclass stored on coordinator with strict typing.
3. Replace all inline lookups; grep `hass.data.get(DOMAIN`.

**Test:** Pyright clean; grep returns zero hits outside `_coordinator` property impl.

**Risk:** Low — mechanical refactor.

**Depends on:** none.

**Blocks:** A04 (single source of truth for domain data).
