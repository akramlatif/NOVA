# NOVA — Security Policy & Sandbox Architecture (v1.0.0)

Security in NOVA is a core foundational invariant, not an afterthought.

---

## 1. Security Architecture Principles

1. **Local-First Boundary**:
   - Zero telemetry, zero external cloud dependencies.
   - All LLM inference runs locally via Ollama (`127.0.0.1:11434`).
   - Network calls to external APIs or services are strictly user-directed.

2. **Containment & Sandboxing**:
   - Filesystem operations are confined by `PathSandbox` using absolute `.resolve()` path canonicalization. Path traversal (`../../`) is unconditionally rejected.
   - CLI execution is managed by `ControlledTerminal` and filtered through a strict allowlist with `shell=False`.

3. **Human-in-the-Loop Approval**:
   - Actions with permanent or destructive side-effects (`SENSITIVE` permission tier) halt execution in `waiting_for_approval` state until explicitly authorized by the user.

4. **Credential & Secret Protection**:
   - `PrivacyScrubber` actively detects and redacts OpenAI keys (`sk-proj-...`), AWS keys, private SSH/RSA keys, and passwords before any memory persistence or logging occurs.

5. **Device Mutual Authentication**:
   - Web and remote access is protected with PBKDF2-HMAC-SHA256 tokens and 5-minute single-use pairing codes.
   - Brute-force requests are mitigated by sliding-window rate limiters.

---

## 2. Security Documentation References

For exhaustive technical threat modeling and performance assessments:
- **STRIDE Threat Model & Vulnerability Audit**: [`docs/SECURITY_ASSESSMENT.md`](file:///e:/3rd%20Semester/Projects/NOVA/docs/SECURITY_ASSESSMENT.md)
- **Performance Profiling & RAM Budget**: [`docs/PERFORMANCE_BENCHMARK.md`](file:///e:/3rd%20Semester/Projects/NOVA/docs/PERFORMANCE_BENCHMARK.md)

---

## 3. Reporting Security Issues

If you discover a potential vulnerability in NOVA, please file a private issue or email `akramlatif1122@gmail.com`.
