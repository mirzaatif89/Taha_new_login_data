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

    const groups = [];
    if (filterValue === "all" || filterValue === "credentials") {
      groups.push(
        buildResultGroup(
          "Credentials",
          credentials,
          (row) => `${row.username || "-"} | ${row.password || "-"}`,
          "report_credentials.html"
        )
      );
    }
    if (filterValue === "all" || filterValue === "login-status") {
      groups.push(
        buildResultGroup(
          "Login Status",
          loginStatus,
          (row) => `${row.username || "-"} | ${row.status || "-"} | ${row.detail || "-"}`,
          "report_login_status.html"
        )
      );
    }
    if (filterValue === "all" || filterValue === "last-attendance") {
      groups.push(
        buildResultGroup(
          "Last Attendance",
          attendance,
          (row) =>
            `${row.username || "-"} | ${row.day || "-"} | ${row.signin || "-"} → ${row.signout || "-"}`,
          "report_attendance.html"
        )
      );
    }
    if (filterValue === "all" || filterValue === "credit-hours") {
      groups.push(
        buildResultGroup(
          "Credit Hours",
          creditHours,
          (row) => `${row.username || "-"} | ${row.total_time || "-"}`,
          "report_credit_hours.html"
        )
      );
    }

    const content = groups.filter(Boolean).join("");

    if (searchResults) {
      searchResults.innerHTML = content;
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
