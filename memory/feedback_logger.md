---
name: Use logger instead of print
description: Always use logging module instead of print() for output
type: feedback
---

Always use `logging.getLogger(__name__)` (or a module-level logger) instead of `print()` for any diagnostic or informational output.

**Why:** User preference for proper logging infrastructure over ad-hoc print statements.

**How to apply:** Any time output/debugging/info needs to be emitted from code — use `logger.debug/info/warning/error` instead of `print`.
