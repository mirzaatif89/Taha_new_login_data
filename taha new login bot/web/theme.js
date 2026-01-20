const THEME_KEY = "taha-theme";
const themeSelect = document.getElementById("theme-select");

function applyTheme(theme) {
  if (!theme) return;
  document.body.setAttribute("data-theme", theme);
}

function getStoredTheme() {
  try {
    return localStorage.getItem(THEME_KEY) || "light";
  } catch (error) {
    return "light";
  }
}

function storeTheme(theme) {
  try {
    localStorage.setItem(THEME_KEY, theme);
  } catch (error) {
    // Ignore storage failures (e.g., disabled storage).
  }
}

const initialTheme = getStoredTheme();
applyTheme(initialTheme);

if (themeSelect) {
  themeSelect.value = initialTheme;
  themeSelect.addEventListener("change", (event) => {
    const nextTheme = event.target.value || "light";
    applyTheme(nextTheme);
    storeTheme(nextTheme);
  });
}
