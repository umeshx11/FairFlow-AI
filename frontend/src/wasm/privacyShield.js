import { hashPiiTokenWithWasm } from "./privacyShieldWasm";

const PII_COLUMNS = new Set(["name", "email", "phone", "mobile", "contact_number"]);

const normalizeHeader = (header) => String(header || "").trim().toLowerCase();

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

const csvEscape = (value) => {
  const text = String(value ?? "");
  if (text.includes('"') || text.includes(",") || text.includes("\n") || text.includes("\r")) {
    return `"${text.replaceAll('"', '""')}"`;
  }
  return text;
};

export const sanitizeCsvForUpload = async (csvText) => {
  const rows = parseCsvRows(csvText);
  if (!rows.length) {
    return {
      csvText,
      stats: {
        rowsProcessed: 0,
        fieldsHashed: 0,
        columnsHashed: []
      }
    };
  }

  const header = rows[0].map((item) => String(item || "").trim());
  const headerNormalized = header.map(normalizeHeader);
  const piiIndexes = headerNormalized
    .map((column, index) => (PII_COLUMNS.has(column) ? index : -1))
    .filter((index) => index >= 0);

  if (!piiIndexes.length) {
    return {
      csvText,
      stats: {
        rowsProcessed: Math.max(0, rows.length - 1),
        fieldsHashed: 0,
        columnsHashed: []
      }
    };
  }

  let fieldsHashed = 0;
  for (let rowIndex = 1; rowIndex < rows.length; rowIndex += 1) {
    const row = rows[rowIndex];
    for (const columnIndex of piiIndexes) {
      const current = row[columnIndex] ?? "";
      if (String(current).trim() !== "") {
        row[columnIndex] = await hashPiiTokenWithWasm(current);
        fieldsHashed += 1;
      }
    }
  }

  const serialized = rows
    .map((row) => row.map(csvEscape).join(","))
    .join("\n");

  return {
    csvText: serialized,
    stats: {
      rowsProcessed: Math.max(0, rows.length - 1),
      fieldsHashed,
      columnsHashed: piiIndexes.map((index) => header[index])
    }
  };
};
