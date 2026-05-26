# Low 09: emoji in user-facing notification titles

**File:** `custom_components/adaptive_climate/climate.py:1328,1599`

**Problem:** Emojis 🔧/⚠️ in titles. CLAUDE.md restricts emoji usage.

**Fix:**
1. Confirm with user whether user-facing strings count (CLAUDE.md ambiguous).
2. If strict: replace with text labels.

**Test:** Visual check in HA notifications.

**Risk:** Low.

**Unresolved:** Does the emoji ban apply to user-visible notification titles, or only code/comments?
