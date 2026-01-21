const refreshBtn = document.getElementById("refresh-btn");
if (refreshBtn) {
  refreshBtn.addEventListener("click", () => {
    if (typeof window.navigateReload === "function") {
      window.navigateReload();
      return;
    }
    window.location.reload();
  });
}

document.addEventListener("keydown", (event) => {
  if (event.key !== "F5") return;
  event.preventDefault();
  if (typeof window.navigateReload === "function") {
    window.navigateReload();
    return;
  }
  window.location.reload();
});
