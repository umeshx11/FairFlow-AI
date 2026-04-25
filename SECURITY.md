# Security Model

## Security-First Design
FairLens AI is designed so sensitive hiring data is minimized before backend processing.

## WASM Sandbox Boundary
- The Privacy Shield runs in-browser as a C++ WebAssembly module (`frontend/src/wasm/ethos_core.cpp`).
- For this platform, the browser-hosted WASM module is treated as a practical trusted execution boundary (TEE-style enclave) for first-pass privacy transformations.
- The WASM runtime executes inside the browser sandbox and does not require external network calls.
- PII hashing is performed locally through exported bindings:
  - `ethos_sha256_hex(...)`
  - `ethos_hash_pii_token(...)`

## Local PII Handling
- CSV fields such as `name`, `email`, and `phone` are pseudonymized client-side before upload.
- SHA-256 hashing runs in WASM; generated tokens are sent instead of raw values.
- Backend APIs receive pseudonymized payloads and never require raw personal identifiers for fairness analytics.

## Differential Privacy and Integrity
- Report aggregates are sanitized with Laplace noise (`backend/privacy.py`).
- Every generated report creates an immutable SHA-256 certificate hash stored in `audit_certificates`.

## Threat Surface Summary
- Browser: local PII transformation and fairness precheck.
- Backend: authenticated processing, audit logging, governance memory retrieval.
- Storage: signed report metadata and tamper-evident certificate records.

## Responsible Disclosure
If you identify a security issue, open a private report with reproduction steps and impact details before public disclosure.
