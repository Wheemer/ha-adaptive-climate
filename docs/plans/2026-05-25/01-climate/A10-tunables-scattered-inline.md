# Architectural 10: tunables/literals scattered across entity files

**File:** `climate.py:946,1755`, `climate_control.py:92` and others

**Problem:** `0.5°C` setpoint threshold, `60min` grace, `0.9` decay factor inline. No discoverability.

**Fix:**
1. Audit all numeric literals in `climate*.py` files.
2. Move to const.py with descriptive names.
3. Group by feature (`# region: humidity`, `# region: duty accumulator`).

**Test:** Existing tests pass; grep `\\d+\\.\\d+` shows only zero defaults and indices.

**Risk:** Low.

**Depends on:** H10, M09.

**Blocks:** none.
