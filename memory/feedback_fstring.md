---
name: Use f-strings for string formatting
description: Always use f-strings, never % or .format() style
type: feedback
---

Always use f-strings for string formatting. Never use `%` style (`"text %s" % val`) or `.format()` style.

**Why:** User preference — explicitly corrected when % style was used in a logging.warning call.

**How to apply:** All string formatting throughout the codebase, including logging calls, error messages, and any other string interpolation.
