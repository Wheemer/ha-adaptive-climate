# Architectural 10: CLAUDE.md vs code reconciliation

**File:** `CLAUDE.md` + code

**Problem:** Docs claim 2.0x Ki cap (code 3.0x), OpenWindowDetector module (doesn't exist), v10 backward-compat (wipes), debug-nesting (flat).

**Fix:**
1. Audit each doc claim against code.
2. Update doc OR code per truth.
3. Specific items: Ki cap (paired with C07), OpenWindowDetector (find/document actual location), v10 persistence (paired with C05/A03), debug attrs (paired with 06-sensors).
4. Add CI doc-drift check (parse code constants, compare with doc table).

**Test:** Doc-drift CI passes.

**Risk:** Low — documentation.

**Depends on:** C07, C05, A03.

**Blocks:** none.
