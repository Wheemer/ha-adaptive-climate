# Architectural 03: Fix migration story end-to-end

**File:** `adaptive/learner_serialization.py`, `adaptive/persistence.py`

**Problem:** Comments claim v7→v10 migrations exist; none do. Destructive on unknown version.

**Fix:**
1. Define migration policy in module docstring.
2. Implement per-version migrators with regression tests (one fixture per old version).
3. Document upgrade story in CLAUDE.md and CHANGELOG.
4. Add CI test that loads each historical schema fixture.
5. Bump-version checklist: "add migrator + fixture" required.

**Test:** Each schema version → migrates to current with no data loss.

**Risk:** High — user data integrity.

**Depends on:** C05, C06, M12.

**Blocks:** none.

**Unresolved:** Where to source v5–v9 fixtures? git log?
