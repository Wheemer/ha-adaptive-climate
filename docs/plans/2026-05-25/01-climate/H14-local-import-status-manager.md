# High 14: local import of StatusManager inside `__init__`

**File:** `custom_components/adaptive_climate/climate.py:297`

**Problem:** Local import + unconditional construction. Pattern hides import errors until entity creation.

**Fix:**
1. Move `from .managers.status_manager import StatusManager` to module top.
2. Verify no circular import (NightSetback/HumidityDetector already at top — likely safe).

**Test:** Module import + entity instantiation succeed; pyright clean.

**Risk:** Low.

**Depends on:** none.

**Blocks:** M11.
