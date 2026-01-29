const PORTAL_KEY = "taha-portal";
const FALLBACK_ADMIN_KEY = "taha-admin";
const FALLBACK_ADMIN_LIST_KEY = "taha-admins";

function getPortal() {
  try {
    return localStorage.getItem(PORTAL_KEY) || "connect";
  } catch (error) {
    return "connect";
  }
}

const PORTAL = getPortal();
const ADMIN_KEY = `taha-admin-${PORTAL}`;
const ADMIN_LIST_KEY = `taha-admins-${PORTAL}`;

const table = document.getElementById("admin-accounts-table");
const status = document.getElementById("admin-accounts-status");
const searchInput = document.getElementById("admin-search-input");

function getAdminList() {
  try {
    const raw = localStorage.getItem(ADMIN_LIST_KEY);
    const list = raw ? JSON.parse(raw) : [];
    if (Array.isArray(list)) {
      return list;
    }
  } catch (error) {
    return [];
  }
  return [];
}

function ensureCreatedAt(list) {
  let updated = false;
  const normalized = list.map((admin) => {
    if (!admin.createdAt) {
      updated = true;
      return { ...admin, createdAt: new Date().toISOString() };
    }
    return admin;
  });
  if (updated) {
    try {
      localStorage.setItem(ADMIN_LIST_KEY, JSON.stringify(normalized));
    } catch (error) {
      // Ignore storage failures.
    }
  }
  return normalized;
}

function getAdminsForDisplay() {
  let list = getAdminList();
  if (!list.length) {
    try {
      const raw = localStorage.getItem(ADMIN_KEY);
      const single = raw ? JSON.parse(raw) : null;
      if (single) {
        list = [single];
      }
    } catch (error) {
      list = [];
    }
  }
  if (!list.length) {
    try {
      const legacyList = localStorage.getItem(FALLBACK_ADMIN_LIST_KEY);
      const parsed = legacyList ? JSON.parse(legacyList) : [];
      if (Array.isArray(parsed) && parsed.length) {
        list = parsed;
      }
    } catch (error) {
      list = list;
    }
  }
  if (!list.length) {
    try {
      const legacy = localStorage.getItem(FALLBACK_ADMIN_KEY);
      const parsed = legacy ? JSON.parse(legacy) : null;
      if (parsed) {
        list = [parsed];
      }
    } catch (error) {
      list = list;
    }
  }
  return ensureCreatedAt(list);
}

function formatDate(value) {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString();
}

function render() {
  if (!table || !status) return;
  table.innerHTML = "";
  let list = getAdminsForDisplay();
  const query = (searchInput && searchInput.value.trim().toLowerCase()) || "";
  if (query) {
    list = list.filter((admin) => {
      const name = (admin.name || "").toLowerCase();
      const email = (admin.email || "").toLowerCase();
      return name.includes(query) || email.includes(query);
    });
  }
  if (!list.length) {
    status.textContent = "No admins found.";
    return;
  }
  status.textContent = "";

  const header = document.createElement("div");
  header.className = "admin-table__row admin-table__header";
  header.innerHTML = "<div>Name</div><div>Email</div><div>Password</div><div>Created</div>";
  table.appendChild(header);

  list.forEach((admin) => {
    const row = document.createElement("div");
    row.className = "admin-table__row";
    const name = admin.name || "-";
    const email = admin.email || "-";
    const password = admin.password || "-";
    const created = formatDate(admin.createdAt);
    row.innerHTML = `<div>${name}</div><div>${email}</div><div>${password}</div><div>${created}</div>`;
    table.appendChild(row);
  });
}

render();

if (searchInput) {
  searchInput.addEventListener("input", render);
}
