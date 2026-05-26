# Low 08: pyright-ignore comment missing rationale

**File:** `custom_components/adaptive_climate/climate.py:1096`

**Problem:** `# pyright: ignore[reportUnnecessaryComparison]` without explanation.

**Fix:** Add comment: "# pyright: ignore[reportUnnecessaryComparison] — pyright infers always-set, but defensive guard needed for restoration path".

**Test:** Pyright clean.

**Risk:** Low.

**Depends on:** none.

**Blocks:** none.
