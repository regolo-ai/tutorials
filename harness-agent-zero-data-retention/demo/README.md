# 🧪 Regolo Sentinel — Interactive Demo Project

This directory provides an instant, self-contained microservice project (`auth.py`, `service.py`, `test_service.py`) designed to test **Regolo Sentinel's Code Review, Secret Redaction, and Targeted AST Intelligence**.

---

## 🎯 What this Demo Tests

1. **Pre-flight Secret Redaction (`policy.py`):**
   - Contains a hardcoded Stripe live key (`sk_live_...`).
   - The policy engine detects and censors it to `[REDACTED]` *before* sending anything to the LLM.
2. **Targeted AST Cross-File Resolution (`ast_engine.py`):**
   - `service.py` imports and calls `AuthService.verify_token(user_token, max_age=1800)` from `auth.py`.
   - The AST engine extracts the interface of `auth.py` and feeds it to Regolo ZDR, preventing false positives.
3. **Security Vulnerability Audit:**
   - Detects timing side-channel attacks (`user_token == ADMIN_PIN`).
   - Detects lack of input validation (negative amounts).
   - Flags credential exposure in return objects.
4. **Interactive Auto-Fix:**
   - Generates the clean AST code removing the secret, replacing it with `os.getenv("STRIPE_SECRET_KEY")`, and adding `hmac.compare_digest`.

---

## 🚀 How to Run the Demo

### Via TUI:
1. Launch the TUI:
   ```bash
   ./regolo.sh
   ```
2. Press **`3`** (`Review & Auto-Fix Repository`).
3. Enter `demo` when prompted for the project path.
4. Watch the review run live in ~2.5 seconds.
5. Answer **`y`** to generate and apply the auto-fix!

### Via CLI:
```bash
# Review only
./regolo.sh review --path demo

# Review and generate auto-fix
./regolo.sh review --path demo --fix
```
