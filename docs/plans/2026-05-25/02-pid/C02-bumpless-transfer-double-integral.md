# Critical 2: Bumpless transfer adds integral on top of bumpless value

**File:** `pid_controller/__init__.py:597-598`

**Problem:** `prepare_bumpless_transfer` sets `_integral` to required value, then the same `calc()` tick accumulates Ki·err·dt on top of it. First post-OFF calc is not actually bumpless when `dt > 0`.

**Fix:**
1. After successful `prepare_bumpless_transfer()`, set `_bumpless_just_applied = True`.
2. Skip accumulate/clamp branch (lines 605-668) for that single tick.
3. Clear flag at end of `calc()`.
4. Assert `_last_input is None` invariant; document why.

**Test:** Unit: OFF→AUTO with non-zero dt, assert output == last_output_before_off.

**Risk:** Med. Touches restart path; need careful test of preheat scenarios.

**Depends on:** none.

**Blocks:** H07 (bumpless skip integral reset).
