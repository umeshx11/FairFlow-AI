const OUTPUT_KEYS = [
  "disparateImpact",
  "equalizedOdds",
  "tprGap",
  "fprGap",
  "proxyScore",
  "selectionPrivileged",
  "selectionUnprivileged",
  "overallPositiveRate",
  "fairnessScore",
  "sampleCount"
];

let runtimePromise = null;

const toFloat32 = (value) => (value instanceof Float32Array ? value : new Float32Array(value));
const toInt32 = (value) => (value instanceof Int32Array ? value : new Int32Array(value));
const runtimeImport = (path) => import(/* webpackIgnore: true */ path);

const safeDivide = (numerator, denominator) => (Math.abs(denominator) < 1e-9 ? 0 : numerator / denominator);

const runJsFallback = ({ yTrue, yPred, protectedAttr, proxyFeature }) => {
  let privTotal = 0;
  let unprivTotal = 0;
  let privSelected = 0;
  let unprivSelected = 0;

  let privTruePos = 0;
  let unprivTruePos = 0;
  let privTrueNeg = 0;
  let unprivTrueNeg = 0;
  let privTp = 0;
  let unprivTp = 0;
  let privFp = 0;
  let unprivFp = 0;
  let globalPositive = 0;

  let sumX = 0;
  let sumX2 = 0;
  let sumA = 0;
  let sumA2 = 0;
  let sumXA = 0;

  for (let index = 0; index < yTrue.length; index += 1) {
    const y = yTrue[index] >= 0.5 ? 1 : 0;
    const p = yPred[index] >= 0.5 ? 1 : 0;
    const a = protectedAttr[index] > 0 ? 1 : 0;
    const x = Number(proxyFeature[index]) || 0;

    globalPositive += p;

    if (a === 1) {
      privTotal += 1;
      privSelected += p;
      if (y === 1) {
        privTruePos += 1;
        privTp += p;
      } else {
        privTrueNeg += 1;
        privFp += p;
      }
    } else {
      unprivTotal += 1;
      unprivSelected += p;
      if (y === 1) {
        unprivTruePos += 1;
        unprivTp += p;
      } else {
        unprivTrueNeg += 1;
        unprivFp += p;
      }
    }

    sumX += x;
    sumX2 += x * x;
    sumA += a;
    sumA2 += a * a;
    sumXA += x * a;
  }

  const selectionPrivileged = safeDivide(privSelected, privTotal);
  const selectionUnprivileged = safeDivide(unprivSelected, unprivTotal);
  const disparateImpact = safeDivide(selectionUnprivileged, selectionPrivileged);

  const tprPriv = safeDivide(privTp, privTruePos);
  const tprUnpriv = safeDivide(unprivTp, unprivTruePos);
  const fprPriv = safeDivide(privFp, privTrueNeg);
  const fprUnpriv = safeDivide(unprivFp, unprivTrueNeg);

  const tprGap = tprUnpriv - tprPriv;
  const fprGap = fprUnpriv - fprPriv;
  const equalizedOdds = 0.5 * (Math.abs(tprGap) + Math.abs(fprGap));

  const n = yTrue.length;
  const numerator = n * sumXA - sumX * sumA;
  const denominator = Math.sqrt((n * sumX2 - sumX * sumX) * (n * sumA2 - sumA * sumA));
  const proxyScore = denominator <= 1e-9 ? 0 : Math.abs(numerator / denominator);

  let checks = 0;
  checks += disparateImpact > 0.8 ? 1 : 0;
  checks += Math.abs(tprGap) < 0.1 ? 1 : 0;
  checks += Math.abs(fprGap) < 0.1 ? 1 : 0;

  return {
    disparateImpact,
    equalizedOdds,
    tprGap,
    fprGap,
    proxyScore,
    selectionPrivileged,
    selectionUnprivileged,
    overallPositiveRate: safeDivide(globalPositive, n),
    fairnessScore: (checks / 3) * 100,
    sampleCount: n
  };
};

const mapOutput = (metrics) =>
  OUTPUT_KEYS.reduce((accumulator, key, index) => {
    accumulator[key] = Number(metrics[index]);
    return accumulator;
  }, {});

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

      if (!module._ethos_run || !module._malloc || !module._free) {
        throw new Error("Invalid WASM export surface.");
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

export const runEthosPipeline = async ({ yTrue, yPred, protectedAttr, proxyFeature }) => {
  const yTrueArray = toFloat32(yTrue);
  const yPredArray = toFloat32(yPred);
  const protectedArray = toInt32(protectedAttr);
  const proxyArray = toFloat32(proxyFeature);

  if (
    yTrueArray.length === 0 ||
    yTrueArray.length !== yPredArray.length ||
    yTrueArray.length !== protectedArray.length ||
    yTrueArray.length !== proxyArray.length
  ) {
    throw new Error("Invalid Ethos input arrays.");
  }

  const runtime = await loadRuntime();
  if (runtime.type !== "wasm") {
    return {
      engine: "js",
      ...runJsFallback({
        yTrue: yTrueArray,
        yPred: yPredArray,
        protectedAttr: protectedArray,
        proxyFeature: proxyArray
      })
    };
  }

  const { module } = runtime;
  const outputLength = OUTPUT_KEYS.length;
  const bytesF32 = Float32Array.BYTES_PER_ELEMENT;
  const bytesI32 = Int32Array.BYTES_PER_ELEMENT;

  const yTruePtr = module._malloc(yTrueArray.length * bytesF32);
  const yPredPtr = module._malloc(yPredArray.length * bytesF32);
  const protectedPtr = module._malloc(protectedArray.length * bytesI32);
  const proxyPtr = module._malloc(proxyArray.length * bytesF32);
  const outputPtr = module._malloc(outputLength * bytesF32);

  try {
    module.HEAPF32.set(yTrueArray, yTruePtr >> 2);
    module.HEAPF32.set(yPredArray, yPredPtr >> 2);
    module.HEAP32.set(protectedArray, protectedPtr >> 2);
    module.HEAPF32.set(proxyArray, proxyPtr >> 2);

    const status = module._ethos_run(
      yTruePtr,
      yPredPtr,
      protectedPtr,
      proxyPtr,
      yTrueArray.length,
      outputPtr
    );
    if (status !== 0) {
      throw new Error(`ethos_run failed with status ${status}.`);
    }

    const output = module.HEAPF32.subarray(outputPtr >> 2, (outputPtr >> 2) + outputLength);
    return {
      engine: "wasm",
      ...mapOutput(output)
    };
  } finally {
    module._free(yTruePtr);
    module._free(yPredPtr);
    module._free(protectedPtr);
    module._free(proxyPtr);
    module._free(outputPtr);
  }
};
