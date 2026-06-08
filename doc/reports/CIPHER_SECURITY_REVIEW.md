# Security Deep-Dive Review Report
**Reviewer:** CIPHER
**Department:** Security
**Date:** 2026-05-22
**Scope:** `backend/`, `frontend/`, `.env`, `docker-compose.yml`

## Executive Summary
A comprehensive security review of the RouteMaster project has uncovered several critical and high-severity vulnerabilities that pose an immediate risk to the platform, user data, and infrastructure. While the project leverages modern frameworks and incorporates some security controls (such as Firebase auth and PII encryption), significant gaps exist in endpoint protection, file handling, and cryptographic practices.

The most alarming issues revolve around **Broken Access Control**, where critical SOS modification endpoints and administrative debug routes lack any authentication middleware. Coupled with an **Unrestricted File Upload / Path Traversal** vulnerability in the SOS module, attackers could easily compromise the host system. Furthermore, **Cryptographic Failures** (like reusing third-party API keys as master encryption keys) and **Hardcoded Secrets** undermine the integrity of the data vault and infrastructure. Addressing these issues prior to production deployment is paramount.

## Insights

### Category 1: Authentication & Authorization Flaws

#### Insight #1: Completely Unauthenticated Admin Debug Endpoints
- **Severity:** 🔴 Critical
- **Type:** Architecture / Bug
- **File(s):** `backend/api/admin/admin.py`
- **Finding:** The `admin.py` router exposes endpoints (`/debug/budget`, `/debug/metrics`, `/debug/providers`) without any `Depends(get_current_user)` authentication or role-based access control (RBAC). Any unauthenticated user can fetch internal system metrics and API budgets.
- **Recommendation:** Add the `get_current_user` dependency and an admin role check to all endpoints in this router, similar to the implementation in `backend/api/admin/refunds.py`.
- **Impact:** Information disclosure of sensitive infrastructure metrics, provider circuit breaker states, and internal API budgets, which can aid in targeted DoS attacks.

#### Insight #2: Missing Authentication on Critical SOS State Modifications
- **Severity:** 🔴 Critical
- **Type:** Bug
- **File(s):** `backend/api/safety/sos.py`
- **Finding:** Endpoints such as `/{event_id}/voice-note`, `/{event_id}/feedback`, `/{event_id}/handshake`, and `/{event_id}/acknowledge` lack the `Depends(get_current_user)` or `Depends(get_optional_user)` middleware. Anyone who can guess or enumerate an `event_id` (UUIDs are somewhat obscure but not cryptographic secrets) can arbitrarily acknowledge SOS events, modify handshakes, or upload malicious files.
- **Recommendation:** Enforce authentication and authorization checks to ensure only authorized responders, admins, or the victim can mutate the SOS event state.
- **Impact:** An attacker could prematurely mark critical SOS incidents as "resolved" or "acknowledged", disrupting emergency response.

### Category 2: File Upload & Input Validation

#### Insight #3: Unrestricted File Upload and Path Traversal in Voice Notes
- **Severity:** 🔴 Critical
- **Type:** Bug
- **File(s):** `backend/api/safety/sos.py`
- **Finding:** The `upload_voice_note` endpoint uses the unsanitized `file.filename` directly in `os.path.join(event_media_dir, filename)`. There is no validation on the file extension or the contents of the filename.
- **Recommendation:** Use a secure, randomly generated filename (e.g., `uuid4() + ".mp3"`) or sanitize `file.filename` using `werkzeug.utils.secure_filename`. Validate the MIME type and extension to ensure only audio files are accepted.
- **Impact:** Remote Code Execution (RCE) or overwriting of critical system files via path traversal (e.g., `../../../evil.py`). 

#### Insight #4: AI Prompt Injection & Token Exhaustion via Unsanitized Input
- **Severity:** 🟠 High
- **Type:** Security / API Security
- **File(s):** `backend/services/intelligence/nlp_passenger.py`, `backend/api/bookings/bookings.py`
- **Finding:** The `parse_passengers_nlp` endpoint accepts a `raw_text` string that is interpolated directly into a Gemini LLM prompt without any length limits or sanitization.
- **Recommendation:** Implement strict length limits (e.g., max 500 characters) on `raw_text` via Pydantic validators. Use system instructions or prompt templating safeguards to prevent prompt injection.
- **Impact:** Malicious actors can send gigabytes of text leading to a Denial of Wallet (exhausting LLM API credits), DoS, or prompt injection to bypass passenger validation rules.

### Category 3: Cryptographic Failures

#### Insight #5: Hardcoded Default Key & Static Salt for PII Encryption
- **Severity:** 🟠 High
- **Type:** Security / Secrets Management
- **File(s):** `backend/utils/crypto.py`
- **Finding:** The PII encryption utility uses a hardcoded fallback secret (`prod-secret-key-for-pii-encryption-123`) and a static, hardcoded salt (`b"railway-static-salt"`) for the PBKDF2 HMAC derivation.
- **Recommendation:** Remove the hardcoded fallback. Fail securely (raise an exception) if the `PII_ENCRYPTION_KEY` environment variable is absent. Generate a unique, random salt per user/record and store it alongside the encrypted data.
- **Impact:** If the environment variable fails to load, all user PII is encrypted with a universally known key, completely nullifying the encryption.

#### Insight #6: Cryptographic Key Reuse (Razorpay Secret as Vault Master Key)
- **Severity:** 🟠 High
- **Type:** Architecture / Security
- **File(s):** `backend/services/auth/vault.py`
- **Finding:** The AES-256 Credential Vault uses `Config.RAZORPAY_KEY_SECRET[:32]` as the master encryption key for storing user IRCTC credentials.
- **Recommendation:** Define a dedicated, high-entropy `VAULT_MASTER_KEY` environment variable exclusively for credential encryption. Never reuse third-party API keys for internal cryptographic operations.
- **Impact:** Compromise of the Razorpay integration (or accidental logging of payment config) immediately leads to the compromise of all securely vaulted user credentials.

### Category 4: Secrets Management & Container Security

#### Insight #7: Hardcoded Secrets in Config and Docker Files
- **Severity:** 🟠 High
- **Type:** Secrets Management
- **File(s):** `docker-compose.yml`, `backend/.env`, `backend/.env.production.backend`
- **Finding:** `.env` and `.env.production.backend` files containing live production credentials (Supabase Service Key, Redis Upstash URLs, Razorpay Secrets, AWS, Gemini API keys) are committed/present in the workspace. `docker-compose.yml` hardcodes `POSTGRES_USER=user` and `POSTGRES_PASSWORD=pass`.
- **Recommendation:** Remove all `.env` files from version control and add them to `.gitignore`. Use a secrets manager (like AWS Secrets Manager, HashiCorp Vault, or Doppler) to inject secrets at runtime.
- **Impact:** Anyone with access to the source code repository or workspace can fully compromise the production databases, payment gateways, and cloud provider accounts.

#### Insight #8: Insecure Container Configuration (Exposed Ports & Root Execution)
- **Severity:** 🟡 Medium
- **Type:** Container Security
- **File(s):** `docker-compose.yml`
- **Finding:** The PostgreSQL (`5432:5432`), Redis (`6379:6379`), and Kafka (`9092:9092`) containers are exposing their ports directly to the host machine. Furthermore, the base images are running as `root` (default behavior).
- **Recommendation:** Remove the `ports` mapping for internal databases so they are only accessible within the Docker `travel_network`. Specify `user: "1000:1000"` (or another non-root UID) for the database and cache containers.
- **Impact:** If the host machine has a public IP and firewall rules are misconfigured, attackers can directly connect to and exploit the unauthenticated/weakly authenticated internal databases.

### Category 5: Code Quality & General Security

#### Insight #9: Missing Schema Length Validations
- **Severity:** 🟡 Medium
- **Type:** API Security
- **File(s):** `backend/api/auth/users.py`
- **Finding:** `UserProfileUpdate` Pydantic models lack `max_length` constraints and regex patterns for fields like `name` and `phone`.
- **Recommendation:** Use `pydantic.Field` to enforce `max_length=100` for names and regex validation for phone numbers (e.g., `^\+?[1-9]\d{1,14}$`).
- **Impact:** Database bloat, potential buffer issues, or subtle XSS if the frontend fails to escape excessively long string payloads.

#### Insight #10: Raw String Formatting in SQL execution (Code Smell)
- **Severity:** 🟢 Low
- **Type:** Best Practice
- **File(s):** `backend/services/emergency/db_sentinel.py`
- **Finding:** The zombie killing query uses an f-string: `db.execute(text(f"SELECT pg_terminate_backend({pid})"))`. While `pid` is sourced from a trusted internal Postgres query, formatting strings into SQL is an anti-pattern.
- **Recommendation:** Use parameterized queries: `db.execute(text("SELECT pg_terminate_backend(:pid)"), {"pid": pid})`.
- **Impact:** Low risk currently, but sets a dangerous precedent that could lead to SQL Injection if the logic is copied to user-facing routes.

## Summary Statistics
| Severity | Count |
|----------|-------|
| 🔴 Critical | 3 |
| 🟠 High | 4 |
| 🟡 Medium | 2 |
| 🟢 Low | 1 |
| 🔵 Info | 0 |
| **Total** | **10** |

## Top Priority Actions
1. **Patch SOS Path Traversal:** Immediately fix `upload_voice_note` to use `secure_filename()` or UUIDs for file storage to prevent RCE.
2. **Secure Unauthenticated Endpoints:** Apply `Depends(get_current_user)` to all routes in `api/admin/admin.py` and state-mutating routes in `api/safety/sos.py`.
3. **Rotate and Remove Secrets:** Invalidate the exposed Razorpay, Supabase, and AWS keys, remove `.env` files from source tracking, and establish a secure secrets injection pipeline.
4. **Fix Cryptographic Reuse:** Generate a dedicated AES-256 key for `CredentialVault` instead of reusing the Razorpay secret. 
5. **Secure Docker Network:** Remove port exposures for `db`, `redis`, and `kafka` in `docker-compose.yml` to prevent external brute-forcing.
