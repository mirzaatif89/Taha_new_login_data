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

const PORTAL_KEY = "taha-portal";

function normalizePortal(value) {
  if (value === "canvas" || value === "connect") return value;
  return "connect";
}

function getStoredPortal() {
  try {
    const raw = localStorage.getItem(PORTAL_KEY);
    return raw ? normalizePortal(raw) : "";
  } catch (error) {
    return "";
  }
}

function setStoredPortal(value) {
  try {
    localStorage.setItem(PORTAL_KEY, value);
  } catch (error) {
    // Ignore storage failures.
  }
}

function applyPortalFromBody() {
  const bodyPortalRaw = document.body.getAttribute("data-portal");
  const bodyPortal = bodyPortalRaw ? normalizePortal(bodyPortalRaw) : "";
  const stored = getStoredPortal();
  const active = bodyPortal || stored || "connect";
  if (bodyPortal && bodyPortal !== stored) {
    setStoredPortal(bodyPortal);
  } else if (!stored) {
    setStoredPortal(active);
  }
  return active;
}

function bindPortalApi(portal) {
  if (window.pywebview && window.pywebview.api && typeof window.pywebview.api.set_portal === "function") {
    window.pywebview.api.set_portal(portal);
  }
}

const activePortal = applyPortalFromBody();
bindPortalApi(activePortal);
window.addEventListener("pywebviewready", () => bindPortalApi(activePortal));

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
