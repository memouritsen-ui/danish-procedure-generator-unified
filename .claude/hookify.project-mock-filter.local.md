---
name: project-mock-filter
enabled: true
event: file
pattern: (?<!test_)(?<!_test)(?<!/tests/).*\.(py|tsx?)$.*?(mock|Mock|MOCK|dummy|Dummy|stub|Stub|placeholder)(?!_mode)(?!s\s*=)
action: warn
---

## PROJECT-SPECIFIC: Mock/Placeholder Detection

**Note:** This rule is tuned for danish-procedure-generator-unified to reduce false positives.

**Legitimate patterns in this codebase:**
- `dummy_mode` - Feature for running without API keys (settings.py)
- `placeholders` - SQL parameterized queries (library_search.py)
- `placeholder` - HTML input attributes (frontend)
- `mock` in test files (backend/tests/)

**This rule only triggers for PRODUCTION code with mock patterns.**

If triggered, verify:
1. Is this actually mock/stub code that should be real?
2. Or is this a legitimate use like the ones listed above?

If legitimate, the pattern filter should exclude it. Consider updating this rule.
