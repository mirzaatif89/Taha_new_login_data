let api = null;
let hasUploadedFile = false;

function bindApi() {
  if (window.pywebview && window.pywebview.api) {
    api = window.pywebview.api;
  }
}

bindApi();
window.addEventListener("pywebviewready", bindApi);

const uploadBtn = document.getElementById("upload-btn");
const uploadByFile = document.getElementById("upload-by-file");
const uploadByStored = document.getElementById("upload-by-stored");
const testingOnlyToggle = document.getElementById("testing-only-toggle");
const testingSaveBtn = document.getElementById("testing-save-btn");
const downloadBtn = document.getElementById("download-btn");
const loginBtn = document.getElementById("login-btn");
const threadInput = document.getElementById("thread-count");
const incognitoToggle = document.getElementById("incognito-toggle");
const loginStatusToggle = document.getElementById("log-login-status");
const attendanceStatusToggle = document.getElementById("log-attendance-status");
const reportBtn = document.getElementById("report-btn");
const reportCard = document.getElementById("report-card");
const reportPreview = document.getElementById("report-preview");
const refreshBtn = document.getElementById("refresh-btn");
const settingsBtn = document.getElementById("settings-btn");

const uploadStatus = document.getElementById("upload-status");
const uploadColumns = document.getElementById("upload-columns");
const downloadStatus = document.getElementById("download-status");
const loginStatus = document.getElementById("login-status");
const loginTime = document.getElementById("login-time");
const uploadModal = document.getElementById("upload-modal");
const uploadModalMessage = document.getElementById("upload-modal-message");
const uploadModalClose = document.getElementById("upload-modal-close");
const uploadModalCta = document.getElementById("upload-modal-cta");
let testingRows = [];

function setStatus(el, message) {
  if (el) {
    el.textContent = message;
  }
}

function showUploadReminder(message) {
  if (uploadModalMessage) {
    uploadModalMessage.textContent = message;
  }
  if (uploadModal) {
    uploadModal.classList.add("show");
    uploadModal.setAttribute("aria-hidden", "false");
  }
}

function hideUploadReminder() {
  if (uploadModal) {
    uploadModal.classList.remove("show");
    uploadModal.setAttribute("aria-hidden", "true");
  }
}

function getSelectedMode() {
  if (attendanceStatusToggle && attendanceStatusToggle.checked) {
    return "attendance";
  }
  if (loginStatusToggle && loginStatusToggle.checked) {
    return "login";
  }
  return null;
}

async function loadReportSummary() {
  if (!reportPreview) return;
  if (!api) {
    reportPreview.textContent = "Waiting for report summary...";
    setTimeout(loadReportSummary, 400);
    return;
  }
  try {
    if (typeof api.get_report_summary !== "function") {
      reportPreview.textContent = "Report summary API not available. Restart the app.";
      return;
    }
    const result = await safeCall(() => api.get_report_summary(), "Failed to load report summary.");
    if (!result || (!result.login_total && !result.report_total && !result.latest_report)) {
      reportPreview.textContent = "No report data yet. Run a login batch first.";
      return;
    }
    const parts = [
      `Login rows: ${result.login_total}`,
      `Report logs: ${result.report_total}`,
    ];
    if (result.latest_report) {
      const latest = result.latest_report;
      const label = `${latest.report_type || "report"} | ${latest.mode || "-"} | ${latest.created_at || "-"}`;
      parts.push(`Latest: ${label}`);
    }
    reportPreview.textContent = parts.join(" · ");
  } catch (error) {
    reportPreview.textContent = error.message || "Failed to load report summary.";
  }
}

async function safeCall(fn, fallbackMessage) {
  if (!api) {
    throw new Error("Python API is initializing… please retry.");
  }
  try {
    return await fn();
  } catch (error) {
    console.error(error);
    throw new Error(fallbackMessage || error.message || "Unexpected error.");
  }
}

async function handleUpload() {
  if (uploadByStored && uploadByStored.checked) {
    setStatus(uploadStatus, "Using stored data. Upload not required.");
    return;
  }
  setStatus(uploadStatus, "Waiting for file selection...");
  setStatus(uploadColumns, "Columns: —");
  hasUploadedFile = false;
  try {
    const result = await safeCall(() => api.select_upload_file(), "Failed to select file.");
    if (!result || !result.path) {
      setStatus(uploadStatus, "No file selected.");
      hasUploadedFile = false;
      return;
    }
    if (result.error) {
      setStatus(uploadStatus, result.error);
      hasUploadedFile = false;
    } else {
      setStatus(uploadStatus, "File selected.");
      hasUploadedFile = true;
      hideUploadReminder();
    }
    const columns = result.columns && result.columns.length ? result.columns.join(", ") : "—";
    setStatus(uploadColumns, `Columns: ${columns}`);
  } catch (error) {
    setStatus(uploadStatus, error.message);
  }
}

async function handleDownload() {
  setStatus(downloadStatus, "Preparing template...");
  try {
    const result = await safeCall(() => api.save_template(), "Failed to download template.");
    if (result.saved) {
      setStatus(downloadStatus, `Saved to ${result.path}`);
    } else {
      setStatus(downloadStatus, result.error || "Unknown error.");
    }
  } catch (error) {
    setStatus(downloadStatus, error.message);
  }
}

function validateThreadCount(value) {
  const parsed = parseInt(value, 10);
  if (Number.isNaN(parsed) || parsed < 1) {
    return 1;
  }
  if (parsed > 20) {
    return 20;
  }
  return parsed;
}

async function handleLogin() {
  const source = uploadByStored && uploadByStored.checked ? "stored" : "file";
  const testingOnly = !!(testingOnlyToggle && testingOnlyToggle.checked);
  if (testingOnly && source !== "file") {
    setStatus(loginStatus, "Testing mode requires a file upload.");
    return;
  }
  if (source === "file" && !hasUploadedFile) {
    showUploadReminder("Upload your clients file before starting logins.");
    setStatus(loginStatus, "Upload your clients file.");
    return;
  }
  if (source === "stored") {
    try {
      const countResult = await safeCall(
        () => api.get_credentials_count(),
        "Failed to read stored credentials."
      );
      if (!countResult || !countResult.total) {
        setStatus(loginStatus, "No credentials found in stored data.");
        return;
      }
    } catch (error) {
      setStatus(loginStatus, error.message);
      return;
    }
  }
  const mode = getSelectedMode();
  if (!mode) {
    setStatus(loginStatus, "Select at least one status option.");
    return;
  }
  setStatus(loginStatus, "Starting login batch...");
  setStatus(loginTime, "Time: …");
  if (testingSaveBtn) testingSaveBtn.hidden = true;
  testingRows = [];
  loginBtn.disabled = true;
  try {
    const options = {
      threads: validateThreadCount(threadInput.value),
      incognito: !!incognitoToggle.checked,
      mode,
      source,
      testing: testingOnly,
    };
    const result = await safeCall(() => api.start_login(options), "Failed to start login.");
    if (result.error) {
      setStatus(loginStatus, result.error);
      return;
    }

    setStatus(
      loginStatus,
      `Total ${result.total} | Success ${result.success} | Failed ${result.failed} | Errors ${result.errors}`
    );
    const elapsed = typeof result.elapsed_seconds === "number" ? `${result.elapsed_seconds}s` : "—";
    let timeMessage = `Time: ${elapsed}`;
    if (result.report_saved && result.report_path) {
      timeMessage += " | Report saved.";
    } else if (result.report_error) {
      timeMessage += " | Report error.";
    }
    if (result.browser_error) {
      timeMessage += " | Browser error.";
    }
    setStatus(loginTime, timeMessage);
    if (testingOnly && result.testing_rows) {
      testingRows = result.testing_rows;
      if (testingSaveBtn) testingSaveBtn.hidden = testingRows.length === 0;
    }
  } catch (error) {
    setStatus(loginStatus, error.message);
  } finally {
    loginBtn.disabled = false;
  }
}

if (uploadBtn) uploadBtn.addEventListener("click", handleUpload);
if (downloadBtn) downloadBtn.addEventListener("click", handleDownload);
if (loginBtn) loginBtn.addEventListener("click", handleLogin);
function goToReport() {
  if (typeof window.navigateTo === "function") {
    window.navigateTo("report.html");
    return;
  }
  window.location.href = "report.html";
}

if (reportBtn) reportBtn.addEventListener("click", goToReport);
if (reportCard) reportCard.addEventListener("click", (event) => {
  if (event.target === reportBtn) {
    return;
  }
  goToReport();
});
if (refreshBtn) {
  refreshBtn.addEventListener("click", () => {
    if (typeof window.navigateReload === "function") {
      window.navigateReload();
      return;
    }
    window.location.reload();
  });
}

if (settingsBtn) {
  settingsBtn.addEventListener("click", () => {
    window.location.href = "settings.html";
  });
}

loadReportSummary();
if (uploadModalClose) uploadModalClose.addEventListener("click", hideUploadReminder);
if (uploadModalCta) uploadModalCta.addEventListener("click", hideUploadReminder);
if (uploadModal) {
  uploadModal.addEventListener("click", (event) => {
    if (event.target === uploadModal) {
      hideUploadReminder();
    }
  });
}

function syncUploadSource(changed) {
  if (!uploadByFile || !uploadByStored) return;
  if (changed === "file" && uploadByFile.checked) {
    uploadByStored.checked = false;
  }
  if (changed === "stored" && uploadByStored.checked) {
    uploadByFile.checked = false;
    if (testingOnlyToggle) testingOnlyToggle.checked = false;
    setStatus(uploadStatus, "Using stored data. Upload not required.");
    setStatus(uploadColumns, "Columns: —");
    safeCall(() => api.get_credentials_count(), "Failed to read stored credentials.")
      .then((result) => {
        if (!result || !result.total) {
          setStatus(uploadStatus, "No stored credentials found.");
        } else {
          setStatus(uploadStatus, `Using stored data. ${result.total} clients found.`);
        }
      })
      .catch((error) => {
        setStatus(uploadStatus, error.message);
      });
  }
  if (!uploadByFile.checked && !uploadByStored.checked) {
    uploadByFile.checked = true;
  }
}

if (uploadByFile) {
  uploadByFile.addEventListener("change", () => syncUploadSource("file"));
}
if (uploadByStored) {
  uploadByStored.addEventListener("change", () => syncUploadSource("stored"));
}

if (testingOnlyToggle) {
  testingOnlyToggle.addEventListener("change", () => {
    if (!testingOnlyToggle.checked) return;
    if (uploadByFile) uploadByFile.checked = true;
    if (uploadByStored) uploadByStored.checked = false;
    setStatus(uploadStatus, "Testing mode enabled. Stored data is disabled.");
  });
}

if (testingSaveBtn) {
  testingSaveBtn.addEventListener("click", async () => {
    if (!testingRows.length) {
      setStatus(uploadStatus, "No testing data to save.");
      return;
    }
    try {
      const result = await safeCall(
        () => api.save_excel_report(testingRows, "testing_report.xlsx"),
        "Failed to save report."
      );
      if (result.saved) {
        setStatus(uploadStatus, `Saved: ${result.path}`);
      } else {
        setStatus(uploadStatus, result.error || "Save cancelled.");
      }
    } catch (error) {
      setStatus(uploadStatus, error.message);
    }
  });
}
