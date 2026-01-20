function navigateTo(url) {
  if (!url) return;
  if (document.body.classList.contains("page-turn")) return;
  document.body.classList.add("page-turn");
  setTimeout(() => {
    window.location.href = url;
  }, 320);
}

function navigateReload() {
  if (document.body.classList.contains("page-turn")) return;
  document.body.classList.add("page-turn");
  setTimeout(() => {
    window.location.reload();
  }, 320);
}

function navigateHistory(direction) {
  if (document.body.classList.contains("page-turn")) return;
  document.body.classList.add("page-turn");
  setTimeout(() => {
    if (direction === "forward") {
      window.history.forward();
    } else {
      window.history.back();
    }
  }, 320);
}

function shouldHandleLink(link) {
  if (!link || link.target === "_blank") return false;
  const href = link.getAttribute("href") || "";
  if (href.startsWith("#") || href.startsWith("mailto:") || href.startsWith("tel:")) {
    return false;
  }
  return true;
}

function hookNavigationLinks() {
  const links = document.querySelectorAll("a[href]");
  links.forEach((link) => {
    if (!shouldHandleLink(link)) return;
    link.addEventListener("click", (event) => {
      event.preventDefault();
      navigateTo(link.href);
    });
  });

  const navButtons = document.querySelectorAll("[data-nav]");
  navButtons.forEach((button) => {
    button.addEventListener("click", () => {
      const direction = button.getAttribute("data-nav") || "back";
      navigateHistory(direction);
    });
  });
}

window.navigateTo = navigateTo;
window.navigateReload = navigateReload;
window.navigateHistory = navigateHistory;

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", hookNavigationLinks);
} else {
  hookNavigationLinks();
}
