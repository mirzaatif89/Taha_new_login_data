let api = null;

function bindApi() {
  if (window.pywebview && window.pywebview.api) {
    api = window.pywebview.api;
  }
}

bindApi();
window.addEventListener("pywebviewready", bindApi);

const credentialsTable = document.getElementById("credentials-table");
const loginStatusTable = document.getElementById("login-status-table");
const attendanceTable = document.getElementById("attendance-table");
const creditHoursTable = document.getElementById("credit-hours-table");

const credentialsStatus = document.getElementById("credentials-status");
const loginStatusStatus = document.getElementById("login-status-status");
const attendanceStatus = document.getElementById("attendance-status");
const creditHoursStatus = document.getElementById("credit-hours-status");

const credentialsMeta = document.getElementById("credentials-meta");
const loginStatusMeta = document.getElementById("login-status-meta");
const attendanceMeta = document.getElementById("attendance-meta");
const creditHoursMeta = document.getElementById("credit-hours-meta");

const credentialColumns = [
  { key: "id", label: "ID" },
  { key: "username", label: "Username" },
  { key: "password", label: "Password" },
  { key: "created_at", label: "Created" },
];

const loginStatusColumns = [
  { key: "id", label: "ID" },
  { key: "username", label: "Username" },
  { key: "status", label: "Status" },
  { key: "detail", label: "Detail" },
  { key: "created_at", label: "Created" },
];

const attendanceColumns = [
  { key: "id", label: "ID" },
  { key: "username", label: "Username" },
  { key: "month", label: "Month" },
  { key: "day", label: "Day" },
  { key: "signin", label: "Signin" },
  { key: "signout", label: "Signout" },
  { key: "total_time", label: "Total Time" },
  { key: "attendance_status", label: "Attendance" },
  { key: "action", label: "Action" },
  { key: "created_at", label: "Created" },
];

const creditHoursColumns = [
  { key: "username", label: "Username" },
  { key: "total_time", label: "Total Time" },
  { key: "credit_hours", label: "Credit Hours" },
  { key: "created_at", label: "Created" },
];

function setStatus(el, message) {
  if (el) {
    el.textContent = message;
  }
}

function buildHeader(table, columns) {
  if (!table) return;
  const thead = table.querySelector("thead");
  if (!thead) return;
  thead.innerHTML = "";
  const row = document.createElement("tr");
  columns.forEach((col) => {
    const th = document.createElement("th");
    th.textContent = col.label;
    row.appendChild(th);
  });
  thead.appendChild(row);
}

function buildBody(table, columns, rows) {
  if (!table) return;
  const tbody = table.querySelector("tbody");
  if (!tbody) return;
  tbody.innerHTML = "";
  if (!rows || rows.length === 0) {
    const row = document.createElement("tr");
    const cell = document.createElement("td");
    cell.colSpan = columns.length;
    cell.textContent = "No data yet.";
    row.appendChild(cell);
    tbody.appendChild(row);
    return;
  }
  rows.forEach((item) => {
    const row = document.createElement("tr");
    columns.forEach((col) => {
      const cell = document.createElement("td");
      const value = item[col.key];
      cell.textContent = value === null || value === undefined ? "" : String(value);
      row.appendChild(cell);
    });
    tbody.appendChild(row);
  });
}

async function safeCall(fn, fallbackMessage) {
  if (!api) {
    throw new Error("Python API is initializing…");
  }
  try {
    return await fn();
  } catch (error) {
    console.error(error);
    if (error && error.message) {
      throw error;
    }
    throw new Error(fallbackMessage || "Unexpected error.");
  }
}

let loadAttempts = 0;
let dataCache = null;
let isLoading = false;
const openedCards = new Set();

function parseTotalTime(totalTime) {
  if (!totalTime || typeof totalTime !== "string") return null;
  const parts = totalTime.split(":").map((part) => parseInt(part, 10));
  if (parts.length !== 3 || parts.some((value) => Number.isNaN(value))) return null;
  return parts[0] * 3600 + parts[1] * 60 + parts[2];
}

function buildCreditRows(attendanceRows) {
  return (attendanceRows || []).map((row) => {
    const seconds = parseTotalTime(row.total_time);
    const hours = seconds === null ? "" : (seconds / 3600).toFixed(2);
    return {
      username: row.username || "",
      total_time: row.total_time || "",
      credit_hours: hours,
      created_at: row.created_at || "",
    };
  });
}

async function loadReportData() {
  if (isLoading) return;
  isLoading = true;
  if (!api) {
    if (loadAttempts < 10) {
      loadAttempts += 1;
      setStatus(credentialsStatus, "Waiting for Python API…");
      setStatus(loginStatusStatus, "Waiting for Python API…");
      setStatus(attendanceStatus, "Waiting for Python API…");
      setStatus(creditHoursStatus, "Waiting for Python API…");
      setTimeout(loadReportData, 400);
    } else {
      setStatus(credentialsStatus, "Python API not available.");
      setStatus(loginStatusStatus, "Python API not available.");
      setStatus(attendanceStatus, "Python API not available.");
      setStatus(creditHoursStatus, "Python API not available.");
    }
    isLoading = false;
    return;
  }
  if (typeof api.get_report_data !== "function") {
    setStatus(credentialsStatus, "Report API not available. Restart the app.");
    setStatus(loginStatusStatus, "Report API not available. Restart the app.");
    setStatus(attendanceStatus, "Report API not available. Restart the app.");
    setStatus(creditHoursStatus, "Report API not available. Restart the app.");
    isLoading = false;
    return;
  }
  buildHeader(credentialsTable, credentialColumns);
  buildHeader(loginStatusTable, loginStatusColumns);
  buildHeader(attendanceTable, attendanceColumns);
  buildHeader(creditHoursTable, creditHoursColumns);

  try {
    const result = await safeCall(() => api.get_report_data(), "Failed to load report data.");
    dataCache = result || {};
    const credentialRows = dataCache.credentials || [];
    const loginRows = dataCache.login_status || [];
    const attendanceRows = dataCache.attendance || [];
    const creditRows = buildCreditRows(attendanceRows);

    buildBody(credentialsTable, credentialColumns, credentialRows);
    buildBody(loginStatusTable, loginStatusColumns, loginRows);
    buildBody(attendanceTable, attendanceColumns, attendanceRows);
    buildBody(creditHoursTable, creditHoursColumns, creditRows);

    const limit = result.limit ? ` (latest ${result.limit})` : "";
    if (credentialsMeta) {
      credentialsMeta.textContent = `Latest credentials saved from uploads${limit}.`;
    }
    if (loginStatusMeta) {
      loginStatusMeta.textContent = `Latest login status for each client${limit}.`;
    }
    if (attendanceMeta) {
      attendanceMeta.textContent = `Attendance snapshots captured from the portal${limit}.`;
    }
    if (creditHoursMeta) {
      creditHoursMeta.textContent = `Estimated hours based on total time${limit}.`;
    }
    setStatus(credentialsStatus, `Rows: ${credentialRows.length}`);
    setStatus(loginStatusStatus, `Rows: ${loginRows.length}`);
    setStatus(attendanceStatus, `Rows: ${attendanceRows.length}`);
    setStatus(creditHoursStatus, `Rows: ${creditRows.length}`);
  } catch (error) {
    const message = error && error.message ? error.message : "Failed to load report data.";
    const normalized = message.includes("get_report_data")
      ? "Report API not available. Restart the app."
      : message;
    setStatus(credentialsStatus, normalized);
    setStatus(loginStatusStatus, normalized);
    setStatus(attendanceStatus, normalized);
    setStatus(creditHoursStatus, normalized);
  } finally {
    isLoading = false;
  }
}

window.addEventListener("pywebviewready", () => {
  bindApi();
});

function toggleCard(key) {
  const body = document.getElementById(`${key}-body`);
  const button = document.querySelector(`.card__toggle[data-toggle="${key}"]`);
  if (!body || !button) return;
  const isOpen = body.classList.toggle("open");
  body.setAttribute("aria-hidden", isOpen ? "false" : "true");
  button.textContent = isOpen ? "Close" : "Open";

  if (isOpen && !openedCards.has(key)) {
    openedCards.add(key);
    if (!dataCache) {
      loadReportData();
    }
  }
}

document.querySelectorAll(".card__toggle").forEach((btn) => {
  btn.addEventListener("click", () => {
    const key = btn.getAttribute("data-toggle");
    if (key) toggleCard(key);
  });
});
