const TOKEN_OUTPUT_CAPACITY = 26;

let runtimePromise = null;

const runtimeImport = (path) => import(/* webpackIgnore: true */ path);

const toHex = (buffer) =>
  Array.from(new Uint8Array(buffer))
    .map((byte) => byte.toString(16).padStart(2, "0"))
    .join("");

const readCStringFromHeap = (heap, ptr, maxBytes) => {
  const bytes = [];
  for (let index = 0; index < maxBytes; index += 1) {
    const value = heap[ptr + index];
    if (value === 0) {
      break;
    }
    bytes.push(value);
  }
  return new TextDecoder().decode(new Uint8Array(bytes));
};

const hashFallback = async (value) => {
  const normalized = String(value || "").trim().toLowerCase();
  if (!normalized) {
    return "";
  }
  if (typeof window !== "undefined" && window.crypto?.subtle) {
    const encoded = new TextEncoder().encode(normalized);
    const digest = await window.crypto.subtle.digest("SHA-256", encoded);
    return `hash_${toHex(digest).slice(0, 20)}`;
  }
  let state = 0;
  for (let index = 0; index < normalized.length; index += 1) {
    state = (state * 33 + normalized.charCodeAt(index)) >>> 0;
  }
  return `hash_${state.toString(16).padStart(8, "0")}`;
};

const loadRuntime = async () => {
  if (runtimePromise) {
    return runtimePromise;
  }
  runtimePromise = (async () => {
    try {
      const moduleImport = await runtimeImport("/wasm/ethos_core.js");
      const createModule = moduleImport.default || moduleImport.createEthosCore || moduleImport;
      const module = await createModule({
        locateFile: (fileName) => `/wasm/${fileName}`
      });
      if (!module._ethos_hash_pii_token || !module._malloc || !module._free || !module.HEAPU8) {
        throw new Error("Privacy Shield WASM bindings unavailable.");
      }
      return {
        type: "wasm",
        module
      };
    } catch (error) {
      return {
        type: "js",
        module: null
      };
    }
  })();
  return runtimePromise;
};

export const hashPiiTokenWithWasm = async (value) => {
  const normalized = String(value || "").trim().toLowerCase();
  if (!normalized) {
    return "";
  }

  const runtime = await loadRuntime();
  if (runtime.type !== "wasm") {
    return hashFallback(normalized);
  }

  const { module } = runtime;
  const inputBytes = new TextEncoder().encode(normalized);
  const inputPtr = module._malloc(inputBytes.length);
  const outputPtr = module._malloc(TOKEN_OUTPUT_CAPACITY);

  try {
    module.HEAPU8.set(inputBytes, inputPtr);
    const status = module._ethos_hash_pii_token(
      inputPtr,
      inputBytes.length,
      outputPtr,
      TOKEN_OUTPUT_CAPACITY
    );
    if (status !== 0) {
      return hashFallback(normalized);
    }
    return readCStringFromHeap(module.HEAPU8, outputPtr, TOKEN_OUTPUT_CAPACITY);
  } finally {
    module._free(inputPtr);
    module._free(outputPtr);
  }
};
