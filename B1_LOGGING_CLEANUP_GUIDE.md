# B1 — Logger Cleanup Task Guide

## Overview

**Task**: Replace all `print()` statements with structured `logger.info()` / `logger.debug()` / `logger.warning()` / `logger.error()` calls for production-ready logging.

**Status**: 80% Complete — Logging infrastructure is setup, but `print()` statements remain in several critical files.

**Impact**: 
- ✅ Performance: No performance impact (print vs logger is negligible)
- ✅ Functionality: No functional impact (system works fine)
- ⏳ Maintainability: Structured logging enables proper log levels, monitoring, and debugging

---

## Files Requiring Print() Replacement

### 1. **backend/app/api/endpoints/chat.py**

**Lines with print()**: ~20 lines (Layer 0, 1, 2 debug output)

**Example**:
```python
# BEFORE
print("\n" + "🚦 " * 20)
print("[LAYER 0 OUTPUT] Gateway Result:")
print(json.dumps(gateway_result, indent=2, ensure_ascii=False, default=str))

# AFTER
logger.debug("[LAYER 0] Gateway Result: %s", json.dumps(gateway_result, indent=2, ensure_ascii=False, default=str))
```

**Command to find**:
```bash
grep -n "print(" backend/app/api/endpoints/chat.py | wc -l
```

---

### 2. **backend/app/api/dependencies/auth.py**

**Lines with print()**: ~5 lines (AUTH SUCCESS/REJECTED messages)

**Example**:
```python
# BEFORE
print(f"🚨 [AUTH REJECTED] NPP '{npp_clean}' mencoba masuk tapi tidak terdaftar/tidak aktif di DB HRIS!")

# AFTER
logger.warning("[AUTH] NPP '%s' rejected - not registered/inactive in HRIS DB", npp_clean)
```

---

### 3. **backend/app/utils/token_expiry.py**

**Lines with print()**: ~5 lines (Token migration & cleanup logs)

**Example**:
```python
# BEFORE
print("✅ [MIGRATION] Token expiry schema setup completed")

# AFTER
logger.info("[TOKEN_EXPIRY] Schema setup completed")
```

---

### 4. **backend/app/utils/request_logging.py**

**Lines with print()**: ~1 line (Setup confirmation)

**Example**:
```python
# BEFORE
print("✅ [LOGGING] Request ID tracing setup completed")

# AFTER
logger.info("[REQUEST_LOGGING] Request ID tracing setup completed")
```

---

### 5. **backend/app/services/chat_history_service.py**

**Lines with print()**: ~5 lines (Title generation, feedback logs)

**Example**:
```python
# BEFORE
print(f"📝 [AUTO TITLE] Berhasil merubah judul sesi: {auto_title}")

# AFTER
logger.info("[AUTO_TITLE] Session title updated: %s", auto_title)
```

---

### 6. **backend/app/services/agent/cognitive_loop.py**

**Lines with print()**: ~10 lines (Cognitive processing logs)

**Example**:
```python
# BEFORE
print("⚙️  [COGNITIVE LOOP] Orkestrator DeepSeek-R1 (Slot 2) siap merajut pemikiran, bolo!")

# AFTER
logger.debug("[COGNITIVE_LOOP] Orchestrator ready for deep thinking")
```

---

## Implementation Steps

### Step 1: Import Logger
Ensure each file has:
```python
import logging
logger = logging.getLogger(__name__)  # or specific name
```

### Step 2: Replace Print Statements

Use this regex pattern for sed/find-replace:

**Pattern 1** (Simple messages):
```regex
print("(.*?)")
→ logger.info("$1")
```

**Pattern 2** (F-strings):
```regex
print(f"(.*?)")
→ logger.info("...", ...)  # Manually convert to format args
```

### Step 3: Choose Correct Log Level

- `logger.debug()` — Layer 0/1/2 processing details (hidden by default in production)
- `logger.info()` — Important events (token setup, migration complete, title generated)
- `logger.warning()` — Auth rejections, fallback activations, retries
- `logger.error()` — Exceptions and failures

### Step 4: Remove Emoji Prefixes (Optional)

Emoji prefixes like 🚦, 🧠, ✍️ should be removed or moved to a separate emoji_prefix system if desired.

---

## Quick Fix Script (Bash)

```bash
#!/bin/bash

# Replace simple print() with logger.info()
for file in \
  "backend/app/api/endpoints/chat.py" \
  "backend/app/api/dependencies/auth.py" \
  "backend/app/utils/token_expiry.py" \
  "backend/app/utils/request_logging.py" \
  "backend/app/services/chat_history_service.py" \
  "backend/app/services/agent/cognitive_loop.py"; do
  
  echo "Processing: $file"
  
  # Backup
  cp "$file" "${file}.bak"
  
  # Replace print( with logger call
  sed -i 's/print(f"/{comment_placeholder}/g' "$file"
  
done

echo "✅ Done! Review each file and fix format arguments manually."
echo "Files backed up with .bak extension"
```

---

## Verification Checklist

After implementing:

```bash
# Count remaining print() calls
grep -r "print(" backend/app --include="*.py" | wc -l
# Should output: 0

# Verify all files import logger
grep -r "import logging" backend/app --include="*.py" | wc -l
# Should be high (most files importing)

# Run type checking
mypy backend/app/

# Run tests
pytest backend/tests/
```

---

## Production Readiness

Once B1 is 100% complete:
1. ✅ All `print()` removed
2. ✅ All files use `logger`
3. ✅ Log levels properly configured in `logging_setup.py`
4. ✅ Production can run with `--loglevel=INFO` to suppress debug output
5. ✅ Development can run with `--loglevel=DEBUG` for detailed tracing

---

## Notes

- **Non-blocking**: This is cosmetic/best-practice cleanup, not a functional blocker
- **Safe**: No behavior changes, only logging format changes
- **Benefit**: Better log aggregation, CloudWatch/Datadog/Splunk integration, production monitoring
- **Time estimate**: 30-60 minutes for manual fixes + testing
