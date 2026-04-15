# Ethos Module 1: Local WASM Fairness Core

## Goal
Run fairness metric computation fully inside the browser so candidate-level audit data never leaves the client during precheck.

## Execution Pipeline
1. User drops CSV in the audit page.
2. `csvAuditInput.js` parses rows and emits typed arrays.
3. `ethosEngine.js` loads `/wasm/ethos_core.wasm` (C++ compiled with Emscripten).
4. The C++ kernel runs a single-pass metric pipeline in `ethos_run(...)`.
5. Metrics are rendered in `LocalWasmPrecheckCard`.
6. If the WASM artifact is missing, the same logic executes through a JS fallback with identical output schema.

## C++ Export Contract
`int ethos_run(const float* y_true, const float* y_pred, const int32_t* protected_attr, const float* proxy_feature, int32_t count, float* out_metrics)`

`out_metrics` layout:
- `0`: disparate impact
- `1`: equalized odds (absolute)
- `2`: TPR gap (unprivileged - privileged)
- `3`: FPR gap (unprivileged - privileged)
- `4`: proxy score (`|corr(proxy_feature, protected_attr)|`)
- `5`: privileged selection rate
- `6`: unprivileged selection rate
- `7`: overall positive rate
- `8`: fairness score (0-100 from threshold checks)
- `9`: sample count

## Build
```bash
cd frontend
npm run build:wasm
```

Artifacts:
- `frontend/public/wasm/ethos_core.js`
- `frontend/public/wasm/ethos_core.wasm`

## Performance Choices
- Single-pass accumulation loop in C++ for all metrics.
- Tight typed-array memory transfer (`Float32Array`/`Int32Array`).
- `-O3`, `-flto`, `-msimd128`, no filesystem in runtime.
- Local Emscripten cache under `frontend/.cache/emscripten` for repeat build speed.

## Privacy Boundary
- Precheck is computed in-browser only.
- No CSV row-level data is sent to third-party services during metric computation.
- Server upload remains optional workflow continuation, not required for precheck.
