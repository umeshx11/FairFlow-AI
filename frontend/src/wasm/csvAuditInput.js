const REQUIRED_HEADERS = ["gender", "hired"];

const normalizeHeader = (header) => header.trim().toLowerCase();

const parseCsvRows = (csvText) => {
  const rows = [];
  let row = [];
  let cell = "";
  let insideQuotes = false;

  for (let index = 0; index < csvText.length; index += 1) {
    const char = csvText[index];
    const nextChar = csvText[index + 1];

    if (char === '"') {
      if (insideQuotes && nextChar === '"') {
        cell += '"';
        index += 1;
      } else {
        insideQuotes = !insideQuotes;
      }
      continue;
    }

    if (char === "," && !insideQuotes) {
      row.push(cell);
      cell = "";
      continue;
    }

    if ((char === "\n" || char === "\r") && !insideQuotes) {
      if (char === "\r" && nextChar === "\n") {
        index += 1;
      }
      row.push(cell);
      cell = "";
      if (row.some((value) => value !== "")) {
        rows.push(row);
      }
      row = [];
      continue;
    }

    cell += char;
  }

  if (cell.length > 0 || row.length > 0) {
    row.push(cell);
    if (row.some((value) => value !== "")) {
      rows.push(row);
    }
  }

  return rows;
};

const parseDecision = (value) => {
  const normalized = String(value || "").trim().toLowerCase();
  return normalized === "1" || normalized === "true" || normalized === "yes" ? 1 : 0;
};

const parseProtected = (value) => {
  const normalized = String(value || "").trim().toLowerCase();
  return normalized === "m" || normalized === "male" || normalized === "man" ? 1 : 0;
};

const parseNumeric = (value) => {
  const parsed = Number.parseFloat(String(value ?? "").trim());
  return Number.isFinite(parsed) ? parsed : 0;
};

export const buildEthosInputFromCsvText = (csvText, options = {}) => {
  const rows = parseCsvRows(csvText);
  if (!rows.length) {
    throw new Error("CSV is empty.");
  }

  const headers = rows[0].map(normalizeHeader);
  const missing = REQUIRED_HEADERS.filter((header) => !headers.includes(header));
  if (missing.length > 0) {
    throw new Error(`CSV missing required headers: ${missing.join(", ")}`);
  }

  const proxyColumn = normalizeHeader(options.proxyColumn || "years_experience");
  const proxyIndex = headers.indexOf(proxyColumn);
  const genderIndex = headers.indexOf("gender");
  const hiredIndex = headers.indexOf("hired");

  const yTrue = [];
  const yPred = [];
  const protectedAttr = [];
  const proxyFeature = [];

  for (let index = 1; index < rows.length; index += 1) {
    const row = rows[index];
    if (!row || row.length === 0) {
      continue;
    }

    const hired = parseDecision(row[hiredIndex]);
    yTrue.push(hired);
    yPred.push(hired);
    protectedAttr.push(parseProtected(row[genderIndex]));
    proxyFeature.push(proxyIndex >= 0 ? parseNumeric(row[proxyIndex]) : 0);
  }

  if (yTrue.length === 0) {
    throw new Error("CSV has no candidate rows.");
  }

  return {
    yTrue: new Float32Array(yTrue),
    yPred: new Float32Array(yPred),
    protectedAttr: new Int32Array(protectedAttr),
    proxyFeature: new Float32Array(proxyFeature),
    proxyColumn
  };
};

