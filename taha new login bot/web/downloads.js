let api = null;

function bindApi() {
  if (window.pywebview && window.pywebview.api) {
    api = window.pywebview.api;
  }
}

bindApi();
window.addEventListener("pywebviewready", bindApi);

const downloadsRefresh = document.getElementById("downloads-refresh");
const downloadsList = document.getElementById("downloads-list");
const downloadsStatus = document.getElementById("downloads-status");

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

async function refreshDownloads() {
  if (!downloadsList || !downloadsStatus) return;
  const ready = await waitForApi("list_client_reports");
  if (!ready) {
    downloadsStatus.textContent = "Downloads API not available. Restart the app.";
    return;
  }
  downloadsStatus.textContent = "Loading downloads...";
  try {
    const result = await safeCall(() => api.list_client_reports(), "Failed to load downloads.");
    const files = result.files || [];
    if (!files.length) {
      downloadsList.innerHTML = "";
      downloadsStatus.textContent = "No downloads yet.";
      return;
    }
    downloadsStatus.textContent = "";
    downloadsList.innerHTML = files
      .map(
        (file) => `
        <div class="download-row">
          <div class="download-name">${file.name}</div>
          <button class="btn ghost small" type="button" data-path="${file.path}">Save As</button>
        </div>
      `
      )
      .join("");
    downloadsList.querySelectorAll("button[data-path]").forEach((button) => {
      button.addEventListener("click", async () => {
        const path = button.getAttribute("data-path");
        if (!path) return;
        const canExport = await waitForApi("export_report_file");
        if (!canExport) {
          downloadsStatus.textContent = "Export API not available.";
          return;
        }
        downloadsStatus.textContent = "Exporting file...";
        try {
          const result = await safeCall(() => api.export_report_file(path), "Export failed.");
          if (result.saved) {
            downloadsStatus.textContent = `Saved to ${result.path}`;
          } else {
            downloadsStatus.textContent = result.error || "Export failed.";
          }
        } catch (error) {
          downloadsStatus.textContent = error.message || "Export failed.";
        }
      });
    });
  } catch (error) {
    downloadsStatus.textContent = error.message || "Failed to load downloads.";
  }
}

if (downloadsRefresh) {
  downloadsRefresh.addEventListener("click", refreshDownloads);
}

refreshDownloads();
