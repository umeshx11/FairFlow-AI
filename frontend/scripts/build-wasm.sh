#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC_FILE="$ROOT_DIR/src/wasm/ethos_core.cpp"
OUT_DIR="$ROOT_DIR/public/wasm"
CACHE_DIR="$ROOT_DIR/.cache/emscripten"

mkdir -p "$OUT_DIR"
mkdir -p "$CACHE_DIR"
export EM_CACHE="$CACHE_DIR"

em++ "$SRC_FILE" \
  -O3 \
  -flto \
  -msimd128 \
  -s WASM=1 \
  -s MODULARIZE=1 \
  -s EXPORT_ES6=1 \
  -s ENVIRONMENT='web,worker,node' \
  -s EXPORT_NAME='createEthosCore' \
  -s EXPORTED_FUNCTIONS='["_ethos_run","_ethos_sha256_hex","_ethos_hash_pii_token","_malloc","_free"]' \
  -s EXPORTED_RUNTIME_METHODS='["HEAPF32","HEAP32","HEAPU8"]' \
  -s ALLOW_MEMORY_GROWTH=1 \
  -s INITIAL_MEMORY=33554432 \
  -s FILESYSTEM=0 \
  -s ASSERTIONS=0 \
  -s STACK_SIZE=524288 \
  --no-entry \
  -o "$OUT_DIR/ethos_core.js"

echo "WASM bundle written to $OUT_DIR/ethos_core.js and $OUT_DIR/ethos_core.wasm"
