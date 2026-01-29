let api = null;

function bindApi() {
  if (window.pywebview && window.pywebview.api) {
    api = window.pywebview.api;
  }
}

bindApi();
window.addEventListener("pywebviewready", bindApi);

const searchInput = document.getElementById("report-search-input");
const searchBtn = document.getElementById("report-search-btn");
const searchFilter = document.getElementById("report-search-filter");
const searchStatus = document.getElementById("report-search-status");
const searchResults = document.getElementById("report-search-results");
const downloadsOpen = document.getElementById("downloads-open");

function setStatus(message) {
  if (searchStatus) {
    searchStatus.textContent = message;
  }
}

function normalize(value) {
  return String(value || "").trim().toLowerCase();
}

function buildResultGroup(title, rows, formatter, link) {
  if (!rows.length) {
    return "";
  }
  const items = rows
    .map((row) => `<div class="search-item">${formatter(row)}</div>`)
    .join("");
  return `
    <div class="search-group">
      <div class="search-group__header">
        <strong>${title}</strong>
        <a class="btn ghost" href="${link}">Open</a>
      </div>
      <div class="search-list">${items}</div>
    </div>
  `;
}

function getLatestByUser(rows) {
  const seen = new Set();
  const sorted = [...rows].sort((a, b) => String(b.created_at || "").localeCompare(String(a.created_at || "")));
  return sorted.filter((row) => {
    const username = normalize(row.username);
    if (!username || seen.has(username)) return false;
    seen.add(username);
    return true;
  });
}

async function waitForApi(method, attempts = 6) {
  for (let i = 0; i < attempts; i += 1) {
    bindApi();
    if (api && typeof api[method] === "function") {
      return true;
    }
    await new Promise((resolve) => setTimeout(resolve, 300));
  }
  return false;
}

function buildClientTable(rows) {
  if (!rows.length) return "";
  const header = `
    <div class="client-table__row client-table__header">
      <div>Type</div>
      <div>Details</div>
      <div>Created</div>
    </div>
  `;
  const body = rows
    .map(
      (row) => `
      <div class="client-table__row">
        <div>${row.type}</div>
        <div>${row.detail}</div>
        <div>${row.created}</div>
      </div>
    `
    )
    .join("");
  return `<div class="client-table">${header}${body}</div>`;
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

async function runSearch() {
  const query = normalize(searchInput ? searchInput.value : "");
  if (!query) {
    setStatus("Enter a client username to search.");
    if (searchResults) searchResults.innerHTML = "";
    return;
  }

  if (!api) {
    setStatus("Waiting for Python API…");
    return;
  }
  if (typeof api.get_report_data !== "function") {
    setStatus("Report API not available. Restart the app.");
    return;
  }

  setStatus("Searching...");
  try {
    const data = await safeCall(() => api.get_report_data(), "Failed to load report data.");
    const filterValue = normalize(searchFilter ? searchFilter.value : "all");

    const credentials = (data.credentials || []).filter((row) =>
      normalize(row.username).includes(query)
    );
    const loginStatusRows = (data.login_status || []).filter((row) =>
      normalize(row.username).includes(query)
    );
    const loginStatus =
      filterValue === "login-status" || filterValue === "all"
        ? getLatestByUser(loginStatusRows)
        : loginStatusRows;

    const attendanceRows = (data.attendance || []).filter((row) =>
      normalize(row.username).includes(query)
    );
    const attendance = filterValue === "last-attendance" ? getLatestByUser(attendanceRows) : attendanceRows;
    const creditHours = getLatestByUser(attendance).map((row) => ({
      username: row.username || "-",
      total_time: row.total_time || "",
      created_at: row.created_at || "",
    }));

    let totalMatches = credentials.length + loginStatus.length + attendance.length;
    if (filterValue === "credit-hours") {
      totalMatches = creditHours.length;
    }
    if (!totalMatches) {
      setStatus("No matching client data found.");
      if (searchResults) searchResults.innerHTML = "";
      return;
    }

    const tableRows = [];
    if (filterValue === "all" || filterValue === "credentials") {
      credentials.forEach((row) =>
        tableRows.push({
          type: "Credentials",
          detail: `${row.username || "-"} | ${row.password || "-"}`,
          created: row.created_at || "-",
        })
      );
    }
    if (filterValue === "all" || filterValue === "login-status") {
      loginStatus.forEach((row) =>
        tableRows.push({
          type: "Login Status",
          detail: `${row.username || "-"} | ${row.status || "-"} | ${row.detail || "-"}`,
          created: row.created_at || "-",
        })
      );
    }
    if (filterValue === "all" || filterValue === "last-attendance") {
      attendance.forEach((row) =>
        tableRows.push({
          type: "Attendance",
          detail: `${row.username || "-"} | ${row.day || "-"} | ${row.signin || "-"} → ${row.signout || "-"}`,
          created: row.created_at || "-",
        })
      );
    }
    if (filterValue === "all" || filterValue === "credit-hours") {
      creditHours.forEach((row) =>
        tableRows.push({
          type: "Credit Hours",
          detail: `${row.username || "-"} | ${row.total_time || "-"}`,
          created: row.created_at || "-",
        })
      );
    }

    if (searchResults) {
      const downloadBtn = `<button class="btn ghost" type="button" id="client-download-btn">Save to Downloads</button>`;
      searchResults.innerHTML = `${downloadBtn}${buildClientTable(tableRows)}`;
      const downloadBtnEl = document.getElementById("client-download-btn");
      if (downloadBtnEl) {
        downloadBtnEl.addEventListener("click", async () => {
          const ready = await waitForApi("save_client_report");
          if (!ready) {
            setStatus("Download API not available. Restart the app.");
            return;
          }
          setStatus("Saving client report...");
          try {
            const result = await safeCall(
              () => api.save_client_report(query),
              "Failed to save client report."
            );
            if (result.saved) {
              setStatus(`Saved to ${result.path}`);
              refreshDownloads();
            } else {
              setStatus(result.error || "Failed to save client report.");
            }
          } catch (error) {
            setStatus(error.message || "Failed to save client report.");
          }
        });
      }
    }
    setStatus(`Matches: ${totalMatches}`);
  } catch (error) {
    setStatus(error.message || "Search failed.");
  }
}

if (searchBtn) searchBtn.addEventListener("click", runSearch);
if (searchInput) {
  searchInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      runSearch();
    }
  });
}
if (downloadsOpen) {
  downloadsOpen.addEventListener("click", () => {
    if (typeof window.navigateTo === "function") {
      window.navigateTo("downloads.html");
      return;
    }
    window.location.href = "downloads.html";
  });
}
