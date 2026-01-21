let api = null;

function bindApi() {
  if (window.pywebview && window.pywebview.api) {
    api = window.pywebview.api;
  }
}

bindApi();
window.addEventListener("pywebviewready", bindApi);

const table = document.getElementById("detail-table");
const statusEl = document.getElementById("detail-status");
const metaEl = document.getElementById("detail-meta");
const searchInput = document.getElementById("detail-search-input");
const searchBtn = document.getElementById("detail-search-btn");
const deleteSelectedBtn = document.getElementById("detail-delete-selected");
const successFilter = document.getElementById("detail-success-filter");
const startDateInput = document.getElementById("detail-start-date");
const endDateInput = document.getElementById("detail-end-date");
const credentialsAction = document.getElementById("credentials-action");
const credentialModal = document.getElementById("credential-modal");
const credentialModalClose = document.getElementById("credential-modal-close");
const credentialModalCancel = document.getElementById("credential-modal-cancel");
const credentialModalSave = document.getElementById("credential-modal-save");
const credentialUsername = document.getElementById("credential-username");
const credentialPassword = document.getElementById("credential-password");
const credentialModalStatus = document.getElementById("credential-modal-status");

const urlParams = new URLSearchParams(window.location.search);
let queryParam = String(urlParams.get("q") || "").trim().toLowerCase();
let successParam = String(urlParams.get("success") || "all").trim().toLowerCase();
let startDateParam = String(urlParams.get("start") || "").trim();
let endDateParam = String(urlParams.get("end") || "").trim();

const SECTION_CONFIG = {
  credentials: {
    meta: "Latest credentials saved from uploads.",
    columns: [
      { key: "select", label: "Select" },
      { key: "username", label: "Username" },
      { key: "password", label: "Password" },
      { key: "actions", label: "Actions" },
    ],
    rows: (data) => data.credentials || [],
  },
  "login-status": {
    meta: "Latest login status for each client.",
    columns: [
      { key: "select", label: "Select" },
      { key: "id", label: "ID" },
      { key: "username", label: "Username" },
      { key: "status", label: "Status" },
      { key: "detail", label: "Detail" },
      { key: "actions", label: "Actions" },
      { key: "created_at", label: "Created" },
    ],
    rows: (data) => data.login_status || [],
  },
  attendance: {
    meta: "Attendance snapshots captured from the portal.",
    columns: [
      { key: "select", label: "Select" },
      { key: "id", label: "ID" },
      { key: "username", label: "Username" },
      { key: "month", label: "Month" },
      { key: "day", label: "Day" },
      { key: "signin", label: "Signin" },
      { key: "signout", label: "Signout" },
      { key: "total_time", label: "Total Time" },
      { key: "attendance_status", label: "Attendance" },
      { key: "action", label: "Action" },
      { key: "actions", label: "Actions" },
      { key: "created_at", label: "Created" },
    ],
    rows: (data) => data.attendance || [],
  },
  "credit-hours": {
    meta: "Estimated hours based on total time.",
    columns: [
      { key: "select", label: "Select" },
      { key: "id", label: "ID" },
      { key: "username", label: "Username" },
      { key: "total_time", label: "Total Time" },
      { key: "credit_hours", label: "Credit Hours" },
      { key: "actions", label: "Actions" },
      { key: "created_at", label: "Created" },
    ],
    rows: (data) => buildCreditRows(data.attendance || []),
  },
};

function setStatus(message) {
  if (statusEl) {
    statusEl.textContent = message;
  }
}

function ensureConfirmModal() {
  let modal = document.getElementById("confirm-modal");
  if (modal) return modal;

  modal = document.createElement("div");
  modal.id = "confirm-modal";
  modal.className = "confirm-modal";
  modal.innerHTML = `
    <div class="confirm-modal__card" role="dialog" aria-modal="true" aria-labelledby="confirm-title">
      <h3 id="confirm-title">Please confirm</h3>
      <p id="confirm-message"></p>
      <div class="confirm-modal__actions">
        <button id="confirm-cancel" class="btn ghost" type="button">Cancel</button>
        <button id="confirm-ok" class="btn primary" type="button">Confirm</button>
      </div>
    </div>
  `;
  document.body.appendChild(modal);
  return modal;
}

function confirmDialog(message) {
  return new Promise((resolve) => {
    const modal = ensureConfirmModal();
    const msgEl = modal.querySelector("#confirm-message");
    const okBtn = modal.querySelector("#confirm-ok");
    const cancelBtn = modal.querySelector("#confirm-cancel");

    if (msgEl) msgEl.textContent = message;
    modal.classList.add("show");

    const cleanup = (result) => {
      modal.classList.remove("show");
      okBtn.removeEventListener("click", onOk);
      cancelBtn.removeEventListener("click", onCancel);
      modal.removeEventListener("click", onBackdrop);
      resolve(result);
    };

    const onOk = () => cleanup(true);
    const onCancel = () => cleanup(false);
    const onBackdrop = (event) => {
      if (event.target === modal) {
        cleanup(false);
      }
    };

    okBtn.addEventListener("click", onOk);
    cancelBtn.addEventListener("click", onCancel);
    modal.addEventListener("click", onBackdrop);
  });
}

function buildHeader(columns) {
  if (!table) return;
  const thead = table.querySelector("thead");
  if (!thead) return;
  thead.innerHTML = "";
  const row = document.createElement("tr");
  columns.forEach((col) => {
    const th = document.createElement("th");
    if (col.key === "select") {
      const selectAll = document.createElement("input");
      selectAll.type = "checkbox";
      selectAll.className = "select-all";
      selectAll.setAttribute("aria-label", "Select all");
      selectAll.addEventListener("change", () => {
        table.querySelectorAll(".row-select").forEach((input) => {
          input.checked = selectAll.checked;
        });
      });
      th.appendChild(selectAll);
    } else {
      th.textContent = col.label;
    }
    row.appendChild(th);
  });
  thead.appendChild(row);
}

function buildBody(columns, rows, options = {}) {
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
      if (options.renderCell) {
        const rendered = options.renderCell(item, col.key);
        if (rendered instanceof HTMLElement) {
          cell.appendChild(rendered);
        } else if (rendered !== null && rendered !== undefined) {
          cell.innerHTML = String(rendered);
        }
      } else {
        const value = item[col.key];
        cell.textContent = value === null || value === undefined ? "" : String(value);
      }
      row.appendChild(cell);
    });
    tbody.appendChild(row);
  });
}

function filterRows(rows, field) {
  if (!queryParam) return rows;
  return (rows || []).filter((row) => {
    const value = row[field];
    return String(value || "").toLowerCase().includes(queryParam);
  });
}

function openCredentialModal() {
  if (!credentialModal) return;
  credentialModal.classList.add("show");
  credentialModal.setAttribute("aria-hidden", "false");
  if (credentialUsername) credentialUsername.value = "";
  if (credentialPassword) credentialPassword.value = "";
  if (credentialModalStatus) credentialModalStatus.textContent = "";
  if (credentialUsername) credentialUsername.focus();
}

function closeCredentialModal() {
  if (!credentialModal) return;
  credentialModal.classList.remove("show");
  credentialModal.setAttribute("aria-hidden", "true");
}

async function handleImportCredentials() {
  if (!api || typeof api.import_credentials_file !== "function") {
    setStatus("Import API not available. Restart the app.");
    return;
  }
  try {
    setStatus("Importing credentials...");
    const result = await safeCall(
      () => api.import_credentials_file(),
      "Failed to import credentials."
    );
    if (!result || result.error) {
      setStatus((result && result.error) || "Failed to import credentials.");
      return;
    }
    setStatus(`Imported ${result.total || 0} credential(s).`);
    loadDetail();
  } catch (error) {
    setStatus(error.message || "Failed to import credentials.");
  }
}

async function handleAddClientSave() {
  if (!credentialModalStatus) return;
  if (!api || typeof api.add_credential !== "function") {
    credentialModalStatus.textContent = "Add client API not available. Restart the app.";
    return;
  }
  const username = (credentialUsername && credentialUsername.value || "").trim();
  const password = credentialPassword ? credentialPassword.value : "";
  if (!username || !password) {
    credentialModalStatus.textContent = "Username and password are required.";
    return;
  }
  try {
    const result = await safeCall(
      () => api.add_credential(username, password),
      "Failed to add client."
    );
    if (!result || !result.saved) {
      credentialModalStatus.textContent = (result && result.error) || "Failed to add client.";
      return;
    }
    credentialModalStatus.textContent = "Client saved.";
    closeCredentialModal();
    setStatus("Client saved.");
    loadDetail();
  } catch (error) {
    credentialModalStatus.textContent = error.message || "Failed to add client.";
  }
}

function normalizeFilterValue(value) {
  return String(value || "").trim().toLowerCase();
}

function parseDateOnly(value) {
  if (!value) return null;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return null;
  return new Date(date.getFullYear(), date.getMonth(), date.getDate());
}

function getRowDate(row) {
  if (!row || !row.created_at) return null;
  return parseDateOnly(row.created_at);
}

function getSuccessValue(row) {
  if (typeof row.success === "boolean") {
    return row.success ? "success" : "failed";
  }
  if (row.success !== undefined && row.success !== null) {
    return normalizeFilterValue(row.success);
  }
  return normalizeFilterValue(row.status);
}

function applyLoginStatusFilters(rows) {
  let filtered = rows || [];
  filtered = filterRows(filtered, "username");
  const startDate = parseDateOnly(startDateParam);
  const endDate = parseDateOnly(endDateParam);
  if (startDate || endDate) {
    filtered = filtered.filter((row) => {
      const rowDate = getRowDate(row);
      if (!rowDate) return false;
      if (startDate && rowDate < startDate) return false;
      if (endDate) {
        const endOfDay = new Date(
          endDate.getFullYear(),
          endDate.getMonth(),
          endDate.getDate(),
          23,
          59,
          59,
          999
        );
        if (rowDate > endOfDay) return false;
      }
      return true;
    });
  }
  if (successParam && successParam !== "all") {
    filtered = filtered.filter((row) => getSuccessValue(row) === successParam);
  }
  return filtered;
}

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
      id: row.id,
      username: row.username || "",
      total_time: row.total_time || "",
      credit_hours: hours,
      created_at: row.created_at || "",
    };
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
let lastFilteredRows = [];
let showPopupAfterLoad = false;

function ensureReportModal() {
  let modal = document.getElementById("report-modal");
  if (modal) return modal;

  modal = document.createElement("div");
  modal.id = "report-modal";
  modal.className = "modal";
  modal.innerHTML = `
    <div class="modal__card report-modal" role="dialog" aria-modal="true" aria-labelledby="report-title">
      <button class="modal__close" type="button" aria-label="Close report popup">&times;</button>
      <h3 id="report-title">Filtered Results</h3>
      <div class="report-modal__actions">
        <button id="report-download" class="btn ghost" type="button">Save As</button>
      </div>
      <div class="report-modal__body">
        <div class="table-wrap report-modal__table">
          <table class="data-table" id="report-modal-table">
            <thead></thead>
            <tbody></tbody>
          </table>
        </div>
      </div>
    </div>
  `;
  document.body.appendChild(modal);

  const closeBtn = modal.querySelector(".modal__close");
  if (closeBtn) {
    closeBtn.addEventListener("click", () => modal.classList.remove("show"));
  }
  modal.addEventListener("click", (event) => {
    if (event.target === modal) {
      modal.classList.remove("show");
    }
  });

  return modal;
}

function buildPopupTable(columns, rows) {
  const modal = ensureReportModal();
  const tableEl = modal.querySelector("#report-modal-table");
  if (!tableEl) return;
  const popupColumns = columns.filter((col) => !["select", "actions"].includes(col.key));

  const thead = tableEl.querySelector("thead");
  const tbody = tableEl.querySelector("tbody");
  if (!thead || !tbody) return;
  thead.innerHTML = "";
  tbody.innerHTML = "";

  const headerRow = document.createElement("tr");
  popupColumns.forEach((col) => {
    const th = document.createElement("th");
    th.textContent = col.label;
    headerRow.appendChild(th);
  });
  thead.appendChild(headerRow);

  if (!rows || rows.length === 0) {
    const emptyRow = document.createElement("tr");
    const cell = document.createElement("td");
    cell.colSpan = popupColumns.length;
    cell.textContent = "No data for current filters.";
    emptyRow.appendChild(cell);
    tbody.appendChild(emptyRow);
    return;
  }

  rows.forEach((row) => {
    const tr = document.createElement("tr");
    popupColumns.forEach((col) => {
      const td = document.createElement("td");
      const value = row[col.key];
      td.textContent = value === null || value === undefined ? "" : String(value);
      tr.appendChild(td);
    });
    tbody.appendChild(tr);
  });
}

function toCsvValue(value) {
  const text = value === null || value === undefined ? "" : String(value);
  if (/[",\n]/.test(text)) {
    return `"${text.replace(/"/g, "\"\"")}"`;
  }
  return text;
}

async function saveExcel(columns, rows) {
  const popupColumns = columns.filter((col) => !["select", "actions"].includes(col.key));
  const exportRows = (rows || []).map((row) => {
    const entry = {};
    popupColumns.forEach((col) => {
      entry[col.label] = row[col.key];
    });
    return entry;
  });
  if (api && typeof api.save_excel_report === "function") {
    try {
      const result = await safeCall(
        () => api.save_excel_report(exportRows, "login_status_filtered.xlsx"),
        "Failed to save report."
      );
      if (!result.saved) {
        setStatus(result.error || "Save cancelled.");
        return;
      }
      setStatus(`Saved: ${result.path}`);
      return;
    } catch (error) {
      setStatus(error.message || "Failed to save report.");
      return;
    }
  }
  setStatus("Excel save is not available. Restart the app.");
}

async function loadDetail() {
  const section = document.body.getAttribute("data-section");
  const config = SECTION_CONFIG[section];
  if (!config) {
    setStatus("Unknown report type.");
    return;
  }

  if (!api) {
    if (loadAttempts < 10) {
      loadAttempts += 1;
      setStatus("Waiting for Python API…");
      setTimeout(loadDetail, 400);
    } else {
      setStatus("Python API not available.");
    }
    return;
  }
  if (typeof api.get_report_data !== "function") {
    setStatus("Report API not available. Restart the app.");
    return;
  }

  buildHeader(config.columns);

  try {
    const result = await safeCall(() => api.get_report_data(), "Failed to load report data.");
    const rawRows = config.rows(result);
    const rows =
      section === "login-status" ? applyLoginStatusFilters(rawRows) : filterRows(rawRows, "username");
    lastFilteredRows = rows;
    if (section === "credentials") {
      buildBody(config.columns, rows, {
        renderCell: (item, key) => {
          if (key === "select") {
            const checkbox = document.createElement("input");
            checkbox.type = "checkbox";
            checkbox.className = "row-select";
            checkbox.dataset.username = item.username || "";
            return checkbox;
          }
          if (key !== "actions") {
            const value = item[key];
            return value === null || value === undefined ? "" : String(value);
          }
          const wrapper = document.createElement("div");
          wrapper.className = "action-buttons";
          const editBtn = document.createElement("button");
          editBtn.className = "btn ghost action-btn";
          editBtn.textContent = "Edit";
          editBtn.dataset.username = item.username || "";
          editBtn.dataset.password = item.password || "";

          const deleteBtn = document.createElement("button");
          deleteBtn.className = "btn ghost action-btn";
          deleteBtn.textContent = "Delete";
          deleteBtn.dataset.username = item.username || "";

          wrapper.appendChild(editBtn);
          wrapper.appendChild(deleteBtn);
          return wrapper;
        },
      });
    } else if (["login-status", "attendance", "credit-hours"].includes(section)) {
      buildBody(config.columns, rows, {
        renderCell: (item, key) => {
          if (key === "select") {
            const checkbox = document.createElement("input");
            checkbox.type = "checkbox";
            checkbox.className = "row-select";
            checkbox.dataset.id = item.id || "";
            checkbox.dataset.username = item.username || "";
            return checkbox;
          }
          if (key !== "actions") {
            const value = item[key];
            return value === null || value === undefined ? "" : String(value);
          }
          const wrapper = document.createElement("div");
          wrapper.className = "action-buttons";
          const editBtn = document.createElement("button");
          editBtn.className = "btn ghost action-btn";
          editBtn.textContent = "Edit";
          editBtn.dataset.id = item.id || "";
          editBtn.dataset.username = item.username || "";
          editBtn.dataset.status = item.status || "";
          editBtn.dataset.detail = item.detail || "";
          editBtn.dataset.month = item.month || "";
          editBtn.dataset.day = item.day || "";
          editBtn.dataset.signin = item.signin || "";
          editBtn.dataset.signout = item.signout || "";
          editBtn.dataset.totalTime = item.total_time || "";
          editBtn.dataset.attendanceStatus = item.attendance_status || "";
          editBtn.dataset.actionValue = item.action || "";

          const deleteBtn = document.createElement("button");
          deleteBtn.className = "btn ghost action-btn";
          deleteBtn.textContent = "Delete";
          deleteBtn.dataset.id = item.id || "";
          deleteBtn.dataset.username = item.username || "";

          wrapper.appendChild(editBtn);
          wrapper.appendChild(deleteBtn);
          return wrapper;
        },
      });
    } else {
      buildBody(config.columns, rows);
    }
    const limit = result.limit ? ` (latest ${result.limit})` : "";
    if (metaEl) {
      const filters = [];
      if (queryParam) {
        filters.push(`Search: ${queryParam}`);
      }
      if (section === "login-status") {
        if (successParam && successParam !== "all") {
          filters.push(`Success: ${successParam}`);
        }
        if (startDateParam || endDateParam) {
          const startLabel = startDateParam || "...";
          const endLabel = endDateParam || "...";
          filters.push(`Date: ${startLabel} to ${endLabel}`);
        }
      }
      const queryNote = filters.length ? ` | Filter: ${filters.join(", ")}` : "";
      metaEl.textContent = `${config.meta}${limit}${queryNote}.`;
    }
    setStatus(`Rows: ${rows.length}`);
    if (showPopupAfterLoad && section === "login-status") {
      showPopupAfterLoad = false;
      const modal = ensureReportModal();
      buildPopupTable(config.columns, rows);
      const downloadBtn = modal.querySelector("#report-download");
      if (downloadBtn) {
        downloadBtn.onclick = () => saveExcel(config.columns, rows);
      }
      modal.classList.add("show");
    }
  } catch (error) {
    const message = error && error.message ? error.message : "Failed to load report data.";
    const normalized = message.includes("get_report_data")
      ? "Report API not available. Restart the app."
      : message;
    setStatus(normalized);
  }
}

window.addEventListener("pywebviewready", () => {
  bindApi();
  loadDetail();
});

loadDetail();

function runSearch() {
  const section = document.body.getAttribute("data-section");
  const value = String(searchInput ? searchInput.value : "").trim().toLowerCase();
  queryParam = value;
  successParam = normalizeFilterValue(successFilter ? successFilter.value : "all") || "all";
  startDateParam = String(startDateInput ? startDateInput.value : "").trim();
  endDateParam = String(endDateInput ? endDateInput.value : "").trim();
  const nextParams = new URLSearchParams(window.location.search);
  if (value) {
    nextParams.set("q", value);
  } else {
    nextParams.delete("q");
  }
  if (successParam && successParam !== "all") {
    nextParams.set("success", successParam);
  } else {
    nextParams.delete("success");
  }
  if (startDateParam) {
    nextParams.set("start", startDateParam);
  } else {
    nextParams.delete("start");
  }
  if (endDateParam) {
    nextParams.set("end", endDateParam);
  } else {
    nextParams.delete("end");
  }
  const newUrl = `${window.location.pathname}?${nextParams.toString()}`;
  window.history.replaceState({}, "", newUrl);
  showPopupAfterLoad = section === "login-status";
  loadDetail();
}

if (searchInput && queryParam) {
  searchInput.value = queryParam;
}
if (successFilter) {
  successFilter.value = successParam || "all";
}
if (startDateInput) {
  startDateInput.value = startDateParam;
}
if (endDateInput) {
  endDateInput.value = endDateParam;
}

if (searchBtn) {
  searchBtn.addEventListener("click", runSearch);
}

if (searchInput) {
  searchInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      runSearch();
    }
  });
}


async function handleCredentialAction(event) {
  const target = event.target;
  if (!(target instanceof HTMLElement)) return;
  const section = document.body.getAttribute("data-section");
  if (!section) return;

  if (target.classList.contains("action-btn")) {
    const action = target.textContent;
    if (section === "credentials") {
      const username = target.dataset.username || "";
      if (!username) return;

      if (action === "Edit") {
        const newUsername = window.prompt("Edit username", username);
        if (!newUsername) return;
        const newPassword = window.prompt("Edit password", target.dataset.password || "");
        if (newPassword === null) return;
        try {
          const result = await safeCall(
            () => api.update_credential(username, newUsername, newPassword),
            "Failed to update credential."
          );
          if (!result.saved) {
            setStatus(result.error || "Failed to update credential.");
            return;
          }
          setStatus("Credential updated.");
          loadDetail();
        } catch (error) {
          setStatus(error.message || "Failed to update credential.");
        }
      }

      if (action === "Delete") {
        const confirmed = await confirmDialog(`Delete credential for ${username}?`);
        if (!confirmed) return;
        try {
          const result = await safeCall(
            () => api.delete_credential(username),
            "Failed to delete credential."
          );
          if (!result.deleted) {
            setStatus(result.error || "Failed to delete credential.");
            return;
          }
          setStatus("Credential deleted.");
          loadDetail();
        } catch (error) {
          setStatus(error.message || "Failed to delete credential.");
        }
      }
      return;
    }

    const rowId = target.dataset.id;
    if (!rowId) return;

    if (section === "login-status") {
      if (action === "Edit") {
        const newStatus = window.prompt("Edit status", target.dataset.status || "");
        if (newStatus === null) return;
        const newDetail = window.prompt("Edit detail", target.dataset.detail || "");
        if (newDetail === null) return;
        try {
          const result = await safeCall(
            () => api.update_login_status(rowId, newStatus, newDetail),
            "Failed to update login status."
          );
          if (!result.saved) {
            setStatus(result.error || "Failed to update login status.");
            return;
          }
          setStatus("Login status updated.");
          loadDetail();
        } catch (error) {
          setStatus(error.message || "Failed to update login status.");
        }
      }

      if (action === "Delete") {
        const name = target.dataset.username || "";
        const confirmed = await confirmDialog(
          `Delete all login status for ${name || "this user"}?`
        );
        if (!confirmed) return;
        try {
          const deleteFn =
            typeof api.delete_login_results_by_username === "function"
              ? () => api.delete_login_results_by_username(name)
              : () => api.delete_login_result(rowId);
          const result = await safeCall(deleteFn, "Failed to delete login status.");
          if (!result.deleted) {
            setStatus(result.error || "Failed to delete login status.");
            return;
          }
          setStatus("Login status deleted.");
          loadDetail();
        } catch (error) {
          setStatus(error.message || "Failed to delete login status.");
        }
      }
      return;
    }

    if (section === "attendance") {
      if (action === "Edit") {
        const month = window.prompt("Edit month", target.dataset.month || "");
        if (month === null) return;
        const day = window.prompt("Edit day", target.dataset.day || "");
        if (day === null) return;
        const signin = window.prompt("Edit signin", target.dataset.signin || "");
        if (signin === null) return;
        const signout = window.prompt("Edit signout", target.dataset.signout || "");
        if (signout === null) return;
        const totalTime = window.prompt("Edit total time (HH:MM:SS)", target.dataset.totalTime || "");
        if (totalTime === null) return;
        const attendanceStatus = window.prompt(
          "Edit attendance status",
          target.dataset.attendanceStatus || ""
        );
        if (attendanceStatus === null) return;
        const actionValue = window.prompt("Edit action", target.dataset.actionValue || "");
        if (actionValue === null) return;
        try {
          const result = await safeCall(
            () =>
              api.update_attendance(rowId, {
                month,
                day,
                signin,
                signout,
                total_time: totalTime,
                attendance_status: attendanceStatus,
                action: actionValue,
              }),
            "Failed to update attendance."
          );
          if (!result.saved) {
            setStatus(result.error || "Failed to update attendance.");
            return;
          }
          setStatus("Attendance updated.");
          loadDetail();
        } catch (error) {
          setStatus(error.message || "Failed to update attendance.");
        }
      }

      if (action === "Delete") {
        const name = target.dataset.username || "";
        const confirmed = await confirmDialog(
          `Delete all attendance for ${name || "this user"}?`
        );
        if (!confirmed) return;
        try {
          const deleteFn =
            typeof api.delete_login_results_by_username === "function"
              ? () => api.delete_login_results_by_username(name)
              : () => api.delete_login_result(rowId);
          const result = await safeCall(deleteFn, "Failed to delete attendance.");
          if (!result.deleted) {
            setStatus(result.error || "Failed to delete attendance.");
            return;
          }
          setStatus("Attendance deleted.");
          loadDetail();
        } catch (error) {
          setStatus(error.message || "Failed to delete attendance.");
        }
      }
      return;
    }

    if (section === "credit-hours") {
      if (action === "Edit") {
        const totalTime = window.prompt("Edit total time (HH:MM:SS)", target.dataset.totalTime || "");
        if (totalTime === null) return;
        try {
          const result = await safeCall(
            () => api.update_credit_hours(rowId, totalTime),
            "Failed to update credit hours."
          );
          if (!result.saved) {
            setStatus(result.error || "Failed to update credit hours.");
            return;
          }
          setStatus("Credit hours updated.");
          loadDetail();
        } catch (error) {
          setStatus(error.message || "Failed to update credit hours.");
        }
      }

      if (action === "Delete") {
        const name = target.dataset.username || "";
        const confirmed = await confirmDialog(
          `Delete all credit hours for ${name || "this user"}?`
        );
        if (!confirmed) return;
        try {
          const deleteFn =
            typeof api.delete_login_results_by_username === "function"
              ? () => api.delete_login_results_by_username(name)
              : () => api.delete_login_result(rowId);
          const result = await safeCall(deleteFn, "Failed to delete credit hours.");
          if (!result.deleted) {
            setStatus(result.error || "Failed to delete credit hours.");
            return;
          }
          setStatus("Credit hours deleted.");
          loadDetail();
        } catch (error) {
          setStatus(error.message || "Failed to delete credit hours.");
        }
      }
    }
  }
}

if (table) {
  table.addEventListener("click", handleCredentialAction);
}

async function handleDeleteSelected() {
  const section = document.body.getAttribute("data-section");
  if (!section || !table) return;
  const selected = Array.from(table.querySelectorAll(".row-select:checked"));
  if (!selected.length) {
    setStatus("Select at least one row.");
    return;
  }

  const usernames = Array.from(
    new Set(selected.map((input) => input.dataset.username).filter(Boolean))
  );
  const ids = selected.map((input) => input.dataset.id).filter(Boolean);
  const confirmed = await confirmDialog(`Delete ${usernames.length || ids.length} selected item(s)?`);
  if (!confirmed) return;

  try {
    if (section === "credentials") {
      for (const username of usernames) {
        await safeCall(() => api.delete_credential(username), "Failed to delete credential.");
      }
      setStatus("Selected credentials deleted.");
      loadDetail();
      return;
    }

    if (typeof api.delete_login_results_by_username === "function" && usernames.length) {
      for (const username of usernames) {
        await safeCall(
          () => api.delete_login_results_by_username(username),
          "Failed to delete records."
        );
      }
      setStatus("Selected records deleted.");
      loadDetail();
      return;
    }

    for (const id of ids) {
      await safeCall(() => api.delete_login_result(id), "Failed to delete records.");
    }
    setStatus("Selected records deleted.");
    loadDetail();
  } catch (error) {
    setStatus(error.message || "Failed to delete selected records.");
  }
}

if (deleteSelectedBtn) {
  deleteSelectedBtn.addEventListener("click", handleDeleteSelected);
}

if (credentialsAction) {
  credentialsAction.addEventListener("change", () => {
    const value = credentialsAction.value;
    if (value === "import-file") {
      handleImportCredentials();
    } else if (value === "add-client") {
      openCredentialModal();
    }
    credentialsAction.value = "";
  });
}

if (credentialModalClose) {
  credentialModalClose.addEventListener("click", closeCredentialModal);
}
if (credentialModalCancel) {
  credentialModalCancel.addEventListener("click", closeCredentialModal);
}
if (credentialModalSave) {
  credentialModalSave.addEventListener("click", handleAddClientSave);
}
if (credentialModal) {
  credentialModal.addEventListener("click", (event) => {
    if (event.target === credentialModal) {
      closeCredentialModal();
    }
  });
}
