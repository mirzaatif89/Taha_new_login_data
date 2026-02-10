from __future__ import annotations

import csv
import os
import shutil
import sys
import tempfile
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
import sqlite3
from pathlib import Path
from time import perf_counter
from typing import Iterable, List, Sequence, Tuple, Optional
from contextlib import suppress
import json

import pandas as pd


def _resource_base() -> Path:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent


def _app_data_base() -> Path:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        base = os.environ.get("APPDATA") or os.environ.get("LOCALAPPDATA")
        if base:
            return Path(base) / "TAHA College Detail Bot"
    return Path(__file__).resolve().parent


RESOURCE_DIR = _resource_base()
APP_DATA_DIR = _app_data_base()
REPORTS_DIR = APP_DATA_DIR / "reports"
DRIVER_DIR = RESOURCE_DIR / "drivers"
USER_DRIVER_DIR = APP_DATA_DIR / "drivers"
KEEP_BROWSER_OPEN = True
ACTIVE_DRIVERS: list[dict] = []
PLAYWRIGHT_SESSIONS: list[dict] = []
DATA_DIR = APP_DATA_DIR / "data"
TEMPLATES_DIR = APP_DATA_DIR / "templates"
CURRENT_PORTAL = "connect"
LEGACY_DB_PATH = DATA_DIR / "taha_bot.db"
DB_PATH = DATA_DIR / "taha_bot_connect.db"
DEFAULT_WINDOW_SIZE = (1400, 900)
DEFAULT_WINDOW_POS = (0, 0)
CHROME_PROFILE_ROOT = APP_DATA_DIR / "chrome_profiles"
ATTENDANCE_HEADERS = [
    "SNo.",
    "Client Email",
    "Month",
    "Day",
    "Signin",
    "Signout",
    "Total Time",
    "Attendance Status",
    "Action",
    "Login Status",
    "Login Detail",
]


def _normalize_portal(portal: str) -> str:
    value = str(portal or "").strip().lower()
    if value in {"canvas", "connect"}:
        return value
    return "connect"


def set_active_portal(portal: str) -> str:
    global CURRENT_PORTAL, DB_PATH
    CURRENT_PORTAL = _normalize_portal(portal)
    DB_PATH = DATA_DIR / f"taha_bot_{CURRENT_PORTAL}.db"
    if CURRENT_PORTAL == "connect" and not DB_PATH.exists() and LEGACY_DB_PATH.exists():
        try:
            _ensure_parent(DB_PATH)
            shutil.copy(LEGACY_DB_PATH, DB_PATH)
        except Exception:
            pass
    return CURRENT_PORTAL


def get_db_path() -> Path:
    return DB_PATH


def delete_storage_data(options: dict) -> dict:
    _init_db()
    try:
        with sqlite3.connect(DB_PATH) as conn:
            if options.get("credentials"):
                conn.execute("DELETE FROM credentials")
            if options.get("login_status"):
                conn.execute("DELETE FROM login_results WHERE mode = 'login'")
            attendance_selected = options.get("attendance") or options.get("credit_hours")
            if attendance_selected:
                conn.execute("DELETE FROM login_results WHERE mode = 'attendance'")
            if options.get("report_logs"):
                conn.execute("DELETE FROM report_logs")
            conn.commit()

        if options.get("template_uploads"):
            if TEMPLATES_DIR.is_dir():
                for item in TEMPLATES_DIR.iterdir():
                    if item.is_file() and item.name.lower() != "login_template.xlsx":
                        try:
                            item.unlink()
                        except Exception:
                            pass

        return {"error": ""}
    except Exception as exc:
        return {"error": str(exc)}


def reset_all_data() -> dict:
    _init_db()
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("DELETE FROM credentials")
            conn.execute("DELETE FROM login_results")
            conn.execute("DELETE FROM report_logs")
            conn.commit()

        if REPORTS_DIR.is_dir():
            for item in REPORTS_DIR.iterdir():
                if item.is_file():
                    try:
                        item.unlink()
                    except Exception:
                        pass

        if TEMPLATES_DIR.is_dir():
            for item in TEMPLATES_DIR.iterdir():
                if item.is_file() and item.name.lower() != "login_template.xlsx":
                    try:
                        item.unlink()
                    except Exception:
                        pass

        return {"error": ""}
    except Exception as exc:
        return {"error": str(exc)}


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def _init_db():
    _ensure_parent(DB_PATH)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS login_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT,
                mode TEXT,
                status TEXT,
                detail TEXT,
                month TEXT,
                day TEXT,
                signin TEXT,
                signout TEXT,
                total_time TEXT,
                attendance_status TEXT,
                action TEXT,
                created_at TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS report_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                mode TEXT,
                report_type TEXT,
                total INTEGER,
                success INTEGER,
                failed INTEGER,
                errors INTEGER,
                report_path TEXT,
                report_error TEXT,
                created_at TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS credentials (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE,
                password TEXT,
                created_at TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at TEXT
            )
            """
        )
        _ensure_columns(
            conn,
            "login_results",
            [
                ("username", "TEXT"),
                ("mode", "TEXT"),
                ("status", "TEXT"),
                ("detail", "TEXT"),
                ("month", "TEXT"),
                ("day", "TEXT"),
                ("signin", "TEXT"),
                ("signout", "TEXT"),
                ("total_time", "TEXT"),
                ("attendance_status", "TEXT"),
                ("action", "TEXT"),
                ("created_at", "TEXT"),
            ],
        )
        _ensure_columns(
            conn,
            "report_logs",
            [
                ("mode", "TEXT"),
                ("report_type", "TEXT"),
                ("total", "INTEGER"),
                ("success", "INTEGER"),
                ("failed", "INTEGER"),
                ("errors", "INTEGER"),
                ("report_path", "TEXT"),
                ("report_error", "TEXT"),
                ("created_at", "TEXT"),
            ],
        )
        _ensure_columns(
            conn,
            "credentials",
            [
                ("username", "TEXT"),
                ("password", "TEXT"),
                ("created_at", "TEXT"),
            ],
        )
        _ensure_columns(
            conn,
            "settings",
            [
                ("key", "TEXT"),
                ("value", "TEXT"),
                ("updated_at", "TEXT"),
            ],
        )
        conn.commit()


def set_setting(key: str, value: str):
    _init_db()
    key = (key or "").strip()
    if not key:
        return
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            INSERT INTO settings (key, value, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
            """,
            (key, value or "", datetime.now().isoformat(timespec="seconds")),
        )
        conn.commit()


def get_setting(key: str) -> str:
    _init_db()
    key = (key or "").strip()
    if not key:
        return ""
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else ""


def _ensure_columns(conn: sqlite3.Connection, table: str, columns: list[tuple[str, str]]) -> None:
    existing = {
        row[1].lower()
        for row in conn.execute(f"PRAGMA table_info({table})").fetchall()
    }
    for name, col_type in columns:
        if name.lower() in existing:
            continue
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {col_type}")


def download_template(
    template_source: Path,
    columns: Sequence[str] | None = None,
    default_filename: str = "login_template.xlsx",
    target_path: Path | None = None,
):
    """
    Copy an existing Excel template or generate a fresh one with the expected columns.
    """
    if target_path:
        if not target_path.suffix:
            target_path = target_path.with_suffix(".xlsx")
    else:
        target_path = TEMPLATES_DIR / default_filename
    try:
        _ensure_parent(target_path)
        desired_cols = list(columns or ["Username", "Password"])
        # Always generate a fresh template with the requested columns so users see expected headers.
        df = pd.DataFrame(columns=desired_cols)
        df.to_excel(target_path, index=False)
        return {"saved": True, "path": str(target_path), "error": ""}
    except Exception as exc:  # pragma: no cover - surfaced via UI
        return {"saved": False, "path": "", "error": str(exc)}


def load_credentials(file_path: Path, id_column: str, password_column: str):
    """
    Load credential rows into dictionaries with string id/password entries.
    Extra columns are ignored.
    """
    if not file_path or not Path(file_path).is_file():
        raise FileNotFoundError(f"Template not found: {file_path}")

    suffix = file_path.suffix.lower()
    if suffix in {".xlsx", ".xls", ".xlsm"}:
        df = pd.read_excel(file_path)
    elif suffix == ".csv":
        df = pd.read_csv(file_path)
    else:
        raise ValueError("Unsupported file type. Use Excel or CSV.")

    def normalize(col: str) -> str:
        return col.strip().lower()

    columns = {normalize(col): col for col in df.columns}
    id_key = columns.get(normalize(id_column))
    password_key = columns.get(normalize(password_column))
    if not id_key or not password_key:
        raise ValueError(f"Columns '{id_column}' and '{password_column}' are required.")

    records = []
    for _, row in df.iterrows():
        identifier = str(row.get(id_key, "")).strip()
        password = str(row.get(password_key, "")).strip()
        if not identifier:
            continue

        records.append(
            {
                "id": identifier,
                "username": identifier,
                "password": password,
            }
        )
    return records


def _locate_local_driver():
    candidates = [
        os.environ.get("CHROMEDRIVER"),
        USER_DRIVER_DIR / "chromedriver.exe",
        DRIVER_DIR / "chromedriver.exe",
        RESOURCE_DIR / "chromedriver.exe",
    ]
    for candidate in candidates:
        if not candidate:
            continue
        path = Path(candidate)
        if path.is_file():
            return path

    cache_roots = [
        os.environ.get("LOCALAPPDATA"),
        os.path.join(os.environ.get("USERPROFILE", ""), ".cache"),
    ]
    cache_hits = []
    for root in cache_roots:
        if not root:
            continue
        root_path = Path(root)
        if not root_path.exists():
            continue
        for match in root_path.rglob("chromedriver.exe"):
            if match.is_file():
                cache_hits.append(match)

    if cache_hits:
        cache_hits.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        return cache_hits[0]
    return None


def _new_chrome_profile_dir() -> Path:
    """
    Create a unique, writable Chrome profile directory for this driver session.
    Using a fresh profile avoids "failed to write prefs file" and profile lock errors
    when multiple Chrome instances run concurrently.
    """
    try:
        CHROME_PROFILE_ROOT.mkdir(parents=True, exist_ok=True)
        return Path(tempfile.mkdtemp(prefix="profile_", dir=str(CHROME_PROFILE_ROOT)))
    except Exception:
        # Fall back to system temp if APP_DATA_DIR is not writable for any reason.
        return Path(tempfile.mkdtemp(prefix="taha_profile_"))


def _build_driver(
    incognito: bool = False,
    headless: bool = False,
):
    try:
        from selenium import webdriver as selenium_webdriver
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.chrome.service import Service
    except ImportError as exc:  # pragma: no cover - surfaced to UI
        raise RuntimeError("Selenium is required. Install via 'pip install selenium'.") from exc

    options = Options()
    viewport = f"--window-size={DEFAULT_WINDOW_SIZE[0]},{DEFAULT_WINDOW_SIZE[1]}"
    if headless:
        options.add_argument("--headless=new")
        options.add_argument(viewport)
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--disable-site-isolation-trials")
    options.add_argument("--autoplay-policy=no-user-gesture-required")
    options.add_argument("--disable-infobars")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("prefs", {"download_restrictions": 3}) 
    if incognito:
        options.add_argument("--incognito")

    profile_dir = _new_chrome_profile_dir()
    options.add_argument(f"--user-data-dir={profile_dir}")
    options.add_argument("--no-first-run")
    options.add_argument("--no-default-browser-check")

    local_driver = _locate_local_driver()
    service = Service(executable_path=str(local_driver)) if local_driver else None
    kwargs = {"options": options}
    if service:
        kwargs["service"] = service
    try:
        browser = selenium_webdriver.Chrome(**kwargs)
    except Exception as exc:
        raise RuntimeError(
            "Unable to launch ChromeDriver. Ensure Chrome is installed or place chromedriver in 'drivers'. "
            f"Original error: {exc}"
        ) from exc

    # Track profile dir so we can clean it up when the session closes.
    with suppress(Exception):
        setattr(browser, "_taha_profile_dir", str(profile_dir))

    _apply_window_bounds(browser)
    return browser


def _apply_window_bounds(driver):
    """Keep all automation windows on-screen with a consistent viewport."""
    try:
        driver.set_window_position(*DEFAULT_WINDOW_POS)
        driver.set_window_size(*DEFAULT_WINDOW_SIZE)
    except Exception:
        pass


def _close_active_drivers():
    global ACTIVE_DRIVERS
    for ctx in ACTIVE_DRIVERS:
        driver = ctx.get("driver")
        profile_dir = None
        with suppress(Exception):
            profile_dir = getattr(driver, "_taha_profile_dir", None)
        try:
            driver.quit()
        except Exception:
            pass
        if profile_dir:
            shutil.rmtree(profile_dir, ignore_errors=True)
    ACTIVE_DRIVERS = []


def _close_playwright_sessions():
    """Close Playwright browser sessions created for login automation."""
    global PLAYWRIGHT_SESSIONS
    for ctx in PLAYWRIGHT_SESSIONS:
        _close_playwright_session(ctx)
    PLAYWRIGHT_SESSIONS = []


def _build_playwright_session(
    login_url: str,
    incognito: bool = False,
    headless: bool = False,
):
    """
    Launch a Playwright Chromium page configured for the TAHA login flow.
    """
    try:
        from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError  # type: ignore
    except ImportError as exc:  # pragma: no cover - surfaced via UI
        raise RuntimeError(
            "Playwright is required. Install via 'pip install playwright' then run 'playwright install chromium'."
        ) from exc

    pw = sync_playwright().start()
    launch_kwargs = {
        "headless": headless,
        "args": [
            f"--window-size={DEFAULT_WINDOW_SIZE[0]},{DEFAULT_WINDOW_SIZE[1]}",
            "--disable-notifications",
            "--disable-extensions",
            "--disable-popup-blocking",
        ],
    }
    browser = pw.chromium.launch(**launch_kwargs)

    context_kwargs = {
        "viewport": {"width": DEFAULT_WINDOW_SIZE[0], "height": DEFAULT_WINDOW_SIZE[1]},
        "ignore_https_errors": True,
    }
    context = browser.new_context(**context_kwargs)
    page = context.new_page()
    page.set_default_timeout(20000)
    page.goto(login_url, wait_until="domcontentloaded")

    return {
        "playwright": pw,
        "browser": browser,
        "context": context,
        "page": page,
    }


def _close_playwright_session(ctx: dict):
    """Gracefully close Playwright handles."""
    if not ctx:
        return
    with suppress(Exception):
        ctx.get("page", None) and ctx["page"].close()
    with suppress(Exception):
        ctx.get("context", None) and ctx["context"].close()
    with suppress(Exception):
        ctx.get("browser", None) and ctx["browser"].close()
    with suppress(Exception):
        ctx.get("playwright", None) and ctx["playwright"].stop()


def close_zoom_sessions() -> dict:
    """Close all active browser sessions opened for Zoom automation."""
    total = len(ACTIVE_DRIVERS)
    _close_active_drivers()
    return {"closed": total, "error": ""}


def run_login_batch(
    credentials: List[dict],
    login_url: str,
    concurrency: int = 1,
    incognito: bool = False,
    headless: bool = False,
    mode: str = "attendance",
    store_results: bool = True,
):
    """
    Automate the TAHA login form with Playwright and feed Username/Password pairs sequentially.
    """
    global PLAYWRIGHT_SESSIONS

    try:
        from playwright.sync_api import TimeoutError as PlaywrightTimeoutError, Error as PlaywrightError  # type: ignore
    except ImportError as exc:  # pragma: no cover - surfaced to UI
        raise RuntimeError(
            "Playwright is required for automated logins. Install via 'pip install playwright' then run 'playwright install chromium'."
        ) from exc

    username_selector = "css=#emailForm"
    password_selector = "css=#pwdform"
    submit_selector = "css=button[type='submit']"
    attendance_selector = "xpath=//*[@id='navbar-navlist']/li[4]/a"
    attendance_row_selector = "xpath=/html/body/section[2]/div/div[2]/div/div/table/tbody/tr[1]"
    capture_attendance = mode != "login"

    start = perf_counter()
    results = []
    browser_error = ""
    sessions: list[dict] = []

    def _new_session():
        return _build_playwright_session(
            login_url=login_url,
            incognito=incognito,
            headless=headless,
        )

    try:
        _close_active_drivers()  # clear any Selenium leftovers
        _close_playwright_sessions()  # clear prior Playwright runs
        total_credentials = len(credentials)
        pool_size = max(1, min(concurrency or 1, total_credentials))
        for idx in range(pool_size):
            sessions.append(_new_session())

        if not sessions:
            raise RuntimeError("Unable to launch any browser instances.")

        # keep sessions alive after function returns (prevents auto-close)
        PLAYWRIGHT_SESSIONS = sessions

        for index, item in enumerate(credentials, 1):
            driver_idx = (index - 1) % len(sessions)
            ctx = sessions[driver_idx]

            page = ctx["page"]
            username_value = (item.get("username") or item.get("id") or "").strip()
            password_value = str(item.get("password", "")).strip()
            if not username_value:
                results.append(
                    {
                        "id": f"Row {index}",
                        "status": "Failed",
                        "message": "Missing username.",
                        "email": "",
                    }
                )
                continue

            attempt = 0
            while attempt < 2:
                attempt += 1
                try:
                    page.goto(login_url, wait_until="domcontentloaded")
                    page.wait_for_selector(username_selector, state="visible", timeout=20000)
                    page.wait_for_selector(password_selector, state="visible", timeout=20000)

                    page.fill(username_selector, username_value)
                    page.fill(password_selector, password_value)
                    page.press(password_selector, "Tab")
                    page.wait_for_timeout(500)
                    page.click(submit_selector)
                    page.wait_for_timeout(2500)

                    login_status = "Success"
                    login_detail = "Credentials submitted to TAHA portal."

                    for selector in [
                        "xpath=//*[contains(@class,'alert') and contains(@class,'alert-danger')]",
                        "xpath=//*[contains(@class,'alert') and contains(@class,'alert-error')]",
                        "xpath=//div[@role='alert']",
                        "xpath=//span[contains(@class,'error')]",
                    ]:
                        try:
                            alert_text = page.locator(selector).first.inner_text(timeout=1500).strip()
                            if alert_text:
                                login_status = "Failed"
                                login_detail = alert_text
                                break
                        except PlaywrightTimeoutError:
                            continue
                        except Exception:
                            continue

                    timestamp = datetime.now()
                    attendance_data: dict[str, str] = {}

                    if capture_attendance and login_status == "Success":
                        try:
                            page.click(attendance_selector, timeout=15000)
                            row_element = page.wait_for_selector(attendance_row_selector, timeout=20000)
                            cells = row_element.locator("xpath=./*")

                            def cell_text(idx: int) -> str:
                                try:
                                    return cells.nth(idx).inner_text(timeout=2000).strip()
                                except PlaywrightError:
                                    return ""

                            attendance_data = {
                                "month": cell_text(1),
                                "day": cell_text(2),
                                "signin": cell_text(3),
                                "signout": cell_text(4),
                                "total_time": cell_text(5),
                                "status": cell_text(6),
                                "action": cell_text(7),
                            }
                        except Exception as exc:
                            browser_error = f"Attendance capture failed: {exc}"

                    results.append(
                        {
                            "id": username_value,
                            "status": login_status,
                            "message": login_detail,
                            "email": username_value,
                            "timestamp": timestamp,
                            "attendance": attendance_data if capture_attendance else {},
                        }
                    )
                    break
                except (PlaywrightTimeoutError, PlaywrightError, Exception) as exc:  # pragma: no cover - automation issues
                    msg = str(exc)
                    browser_error = msg
                    if attempt == 1:
                        _close_playwright_session(ctx)
                        ctx = _new_session()
                        sessions[driver_idx] = ctx
                        page = ctx["page"]
                        continue  # retry this credential once with fresh session
                    results.append(
                        {
                            "id": username_value or f"Row {index}",
                            "status": "Error",
                            "message": f"Automation failed: {msg}",
                            "email": username_value,
                        }
                    )
                    break
    except Exception as exc:
        browser_error = str(exc)
    finally:
        if not KEEP_BROWSER_OPEN:
            _close_playwright_sessions()

    elapsed = perf_counter() - start
    if store_results:
        try:
            store_results_in_db(results, mode)
        except Exception as exc:
            browser_error = browser_error or f"DB store failed: {exc}"
    return {
        "results": results,
        "elapsed_seconds": round(elapsed, 3),
        "concurrency": concurrency,
        "browser_error": browser_error,
    }

def click_join_from_browser(driver, timeout=15) -> bool:
    """Click the landing-page 'Join from browser' / 'Join from your browser' CTA."""
    try:
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
    except Exception:
        return False

    end_time = time.time() + timeout
    locators = [
        (By.CSS_SELECTOR, "#btnOpenInBrowser,#wc-container-join-from-browser"),
        (By.XPATH, "//button[contains(., 'Join from browser')]"),
        (By.XPATH, "//a[contains(., 'Join from browser')]"),
        (By.XPATH, '//*[@id="zoom-ui-frame"]/div[2]/div/div[1]/div/button[2]/span'),
        (By.XPATH, "//span[contains(., 'Join from browser')]/ancestor::*[self::button or self::a]"),
        (By.XPATH, "//span[contains(., 'Join from your browser')]/ancestor::*[self::button or self::a]"),
        (By.CSS_SELECTOR, "button.joinFromBrowser, a.joinFromBrowser"),
        # Fallback to the static position used on the current landing page
        (By.XPATH, "/html/body/div[1]/div[2]/div/div[2]/div/div[1]/div/button[2]"),
    ]
    js_probe = """
        const phrases = [
            'join from browser',
            'join from your browser',
            'join from web',
            'join from web browser'
        ];
        const nodes = Array.from(document.querySelectorAll('button,a,span,div'));
        for (const node of nodes) {
            const text = (node.innerText || node.textContent || '').trim().toLowerCase();
            if (!text) continue;
            if (phrases.some(p => text.includes(p))) {
                try { node.scrollIntoView({behavior:'smooth', block:'center'}); } catch (e) {}
                try { node.click(); } catch (e) {}
                return true;
            }
        }
        return false;
    """

    while time.time() < end_time:
        for how, value in locators:
            try:
                btn = WebDriverWait(driver, 3).until(EC.element_to_be_clickable((how, value)))
                try:
                    driver.execute_script(
                        "arguments[0].scrollIntoView({behavior:'smooth', block:'center'});", btn
                    )
                except Exception:
                    pass
                btn.click()
                return True
            except Exception:
                continue
        try:
            if driver.execute_script(js_probe):
                return True
        except Exception:
            pass
        time.sleep(0.4)
    try:
        driver.switch_to.default_content()
    except Exception:
        pass
    return False


def click_continue_without_mic_camera(driver, timeout=20) -> bool:
    """Iterate through iframes to press any 'Continue without audio/video' control on Zoom join."""
    try:
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.common.exceptions import TimeoutException
    except Exception:
        return False

    clicked_join = False
    # If we're still on the landing page, hit the 'Join from browser' CTA first.
    try:
        clicked_join = click_join_from_browser(driver, timeout=5)
        if clicked_join:
            time.sleep(1)
    except Exception:
        pass
    end_time = time.time() + timeout
    selectors = [
        ".pepc-permission-dialog__footer-button",
        ".continue-without-mic-camera",
        "[role='button']",
        "button",
        "span",
        "a",
    ]
    keywords = [
        r"continue without",
        r"join without",
        r"use computer audio later",
        r"leave computer audio",
        r"join from browser",
        r"continue in browser",
        r"skip.*audio",
        r"skip.*video",
        r"not now",
    ]
    join_from_browser_xpath = "/html/body/div[1]/div[2]/div/div[2]/div/div[1]/div/button[2]"
    preferred_locators = [
        (By.XPATH, "//button[contains(., 'Join from browser')]"),
        (By.XPATH, "//a[contains(., 'Join from browser')]"),
        (By.XPATH, "//span[contains(., 'Join from browser')]/ancestor::*[self::button or self::a]"),
        (By.CSS_SELECTOR, "button.joinFromBrowser, a.joinFromBrowser"),
        (By.XPATH, join_from_browser_xpath),
    ]
    js_click = """
        const selectors = arguments[0];
        const keywords = arguments[1].map(k => new RegExp(k, 'i'));
        for (const selector of selectors) {
            const nodes = Array.from(document.querySelectorAll(selector));
            for (const node of nodes) {
                const text = (node.innerText || node.textContent || '').trim();
                if (!text) continue;
                if (keywords.some(re => re.test(text))) {
                    node.scrollIntoView({behavior:'smooth', block:'center'});
                    node.click();
                    return true;
                }
            }
        }
        return false;
    """
    clicked_once = clicked_join
    while time.time() < end_time:
        try:
            driver.switch_to.default_content()
        except Exception:
            return clicked_once
        contexts = [None]
        try:
            contexts.extend(driver.find_elements(By.TAG_NAME, "iframe"))
        except Exception:
            pass
        clicked_this_pass = False
        for frame in contexts:
            try:
                driver.switch_to.default_content()
                if frame is not None:
                    driver.switch_to.frame(frame)
                # Try explicit "Join from browser" locators first
                for how, value in preferred_locators:
                    try:
                        btn = WebDriverWait(driver, 1).until(
                            EC.element_to_be_clickable((how, value))
                        )
                        driver.execute_script(
                            "arguments[0].scrollIntoView({behavior:'smooth', block:'center'}); arguments[0].click();",
                            btn,
                        )
                        clicked_once = True
                        clicked_this_pass = True
                        break
                    except TimeoutException:
                        continue
                    except Exception:
                        continue
                if clicked_this_pass:
                    break
                if driver.execute_script(js_click, selectors, keywords):
                    clicked_once = True
                    clicked_this_pass = True
                    break
            except Exception:
                continue
        if clicked_this_pass:
            time.sleep(0.6)
            continue
        if clicked_once:
            try:
                driver.switch_to.default_content()
            except Exception:
                pass
            return True
        time.sleep(0.5)
    try:
        driver.switch_to.default_content()
    except Exception:
        pass
    return clicked_once


def find_name_input(driver, timeout=2):
    """Locate the meeting name input regardless of iframe nesting."""
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import TimeoutException

    end_time = time.time() + timeout
    selectors = [
        (By.CSS_SELECTOR, "input[name='name']"),
        (By.CSS_SELECTOR, "input#name"),
        (By.CSS_SELECTOR, "input#inputname"),
        (By.CSS_SELECTOR, "input.zm-input__input"),
        (By.XPATH, "//input[contains(@placeholder, 'Name')]"),
        (By.XPATH, "//input[contains(@aria-label, 'name')]"),
        (By.XPATH, "/html/body/div[2]/div[2]/div/div[1]/div/div[2]/div[2]/div/input"),
    ]
    last_error = None
    while time.time() < end_time:
        try:
            driver.switch_to.default_content()
        except Exception as exc:
            print(f"Error switching to default content: {exc}")
            last_error = exc
            break
        contexts = [None]
        try:
            contexts.extend(driver.find_elements(By.TAG_NAME, "iframe"))
        except Exception:
            print("Error finding iframes, proceeding with default content only.")
            pass
        for frame in contexts:
            try:
                driver.switch_to.default_content()
                if frame is not None:
                    driver.switch_to.frame(frame)
                for by, value in selectors:
                    try:
                        return WebDriverWait(driver, 3).until(EC.element_to_be_clickable((by, value)))
                    except TimeoutException:
                        continue
            except Exception as exc:
                last_error = exc
                continue
        time.sleep(0.5)
    try:
        driver.switch_to.default_content()
    except Exception:
        pass
    if last_error:
        raise TimeoutException(f"Name input not found: {last_error}")
    raise TimeoutException("Name input not found")


def disable_zoom_media_prompts(driver, timeout=20):
    """
    Ensure Zoom join page proceeds without requesting mic/camera by clicking
    any 'Join/Continue without audio/video' controls and toggling media buttons off.
    """
    try:
        from selenium.webdriver.common.by import By
    except Exception:
        return False
    end_time = time.time() + timeout
    attempted = False
    while time.time() < end_time:
        clicked = click_continue_without_mic_camera(driver, timeout=4)
        attempted = attempted or clicked
        try:
            driver.switch_to.default_content()
        except Exception:
            pass
        explicit_targets = [
            "/html/body/div[2]/div[2]/div/div[1]/div/div[1]/div/div[1]/div[1]/button[1]/div/div",
            "//*[@id='preview-video-control-button']",
            "//*[@id='preview-video-control-button']/svg",
            "//*[@id='root']/div/div[1]/div/div[2]/button",
        ]
        try:
            contexts = [None]
            try:
                contexts.extend(driver.find_elements(By.TAG_NAME, "iframe"))
            except Exception:
                pass
            for frame in contexts:
                try:
                    driver.switch_to.default_content()
                    if frame is not None:
                        driver.switch_to.frame(frame)
                    for xp in explicit_targets:
                        try:
                            target = driver.find_element(By.XPATH, xp)
                            target.location_once_scrolled_into_view
                            target.click()
                            attempted = True
                            raise StopIteration  # break both loops
                        except Exception:
                            continue
                except StopIteration:
                    raise
                except Exception:
                    continue
        except StopIteration:
            try:
                driver.switch_to.default_content()
            except Exception:
                pass
            return True
        try:
            mute_btns = driver.find_elements(By.CSS_SELECTOR, "[aria-label*='Mute'],[aria-label*='muted']")
            for btn in mute_btns:
                label = (btn.get_attribute("aria-pressed") or "").lower()
                if label == "false":
                    try:
                        btn.click()
                        attempted = True
                    except Exception:
                        pass
        except Exception:
            pass
        try:
            video_btns = driver.find_elements(By.CSS_SELECTOR, "[aria-label*='Start Video'],[aria-label*='Start video']")
            for btn in video_btns:
                pressed = (btn.get_attribute("aria-pressed") or "").lower()
                if pressed == "false":
                    try:
                        btn.click()
                        attempted = True
                    except Exception:
                        pass
        except Exception:
            pass
        if attempted:
            return True
        time.sleep(0.4)
    return attempted


def run_zoom_portal(credentials: list[dict], portal_url: str, target_xpath: str, threads: int = 1):
    """
    Open the portal in Chrome, sign in with one or more credentials, and click the target card.
    The number of browser instances is limited by `threads` and the credential count; all credentials are processed.
    """
    if not credentials:
        raise RuntimeError("No Zoom credentials available.")

    try:
        import time
        from selenium.webdriver.common.by import By
        from selenium.webdriver.common.keys import Keys
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.webdriver.support.ui import WebDriverWait
    except ImportError as exc:  # pragma: no cover - surfaced to UI
        raise RuntimeError("Selenium is required for Zoom portal automation.") from exc

    thread_count = max(1, min(int(threads or 1), len(credentials)))

    _close_active_drivers()
    errors: list[str] = []
    active_lock = threading.Lock()

    def find_first(driver, selectors):
        for by, sel in selectors:
            elements = driver.find_elements(by, sel)
            if elements:
                return elements[0]
        return None

    def wait_and_click(driver, by, selector, timeout=12) -> bool:
        try:
            el = WebDriverWait(driver, timeout).until(EC.element_to_be_clickable((by, selector)))
            driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
            try:
                el.click()
            except Exception:
                driver.execute_script("arguments[0].click();", el)
            return True
        except Exception:
            return False
        
    def try_selectors(driver, candidates, timeout_each=10) -> bool:
        """Try several selectors (list of (By, value)) until one clicks."""
        for by, value in candidates:
            if wait_and_click(driver, by, value, timeout=timeout_each):
                return True
        return False

    def join_class(cred):
        local_errors: list[str] = []

        def start_session():
            drv = _build_driver(incognito=False, headless=False)
            with suppress(Exception):
                drv.maximize_window()
            wt = WebDriverWait(drv, 25)
            with active_lock:
                ACTIVE_DRIVERS.append({"driver": drv, "wait": wt})
            drv.get(portal_url)
            time.sleep(1.5)
            return drv, wt

        def cleanup_driver(drv):
            if not drv:
                return
            with active_lock:
                ACTIVE_DRIVERS[:] = [ctx for ctx in ACTIVE_DRIVERS if ctx.get("driver") is not drv]
            with suppress(Exception):
                drv.quit()

        driver = None
        try:
            driver, wait = start_session()
        except Exception as exc:
            cleanup_driver(driver)
            local_errors.append(str(exc))
            return local_errors

        username_value = str(cred.get("username") or cred.get("id") or "").strip()
        password_value = str(cred.get("password") or "").strip()
        display_name = username_value or "Student"
        if not username_value or not password_value:
            local_errors.append("Excel file must include Username and Password columns.")
            return local_errors

        deadline = time.time() + 25
        username_input = None
        password_input = None
        while time.time() < deadline and (not username_input or not password_input):
            username_input = find_first(
                driver,
                [
                    (By.NAME, "username"),
                    (By.ID, "username"),
                    (By.CSS_SELECTOR, "input[type='email']"),
                    (By.CSS_SELECTOR, "input[type='text']"),
                ],
            )
            password_input = find_first(
                driver,
                [
                    (By.NAME, "password"),
                    (By.ID, "password"),
                    (By.CSS_SELECTOR, "input[type='password']"),
                ],
            )
            if username_input and password_input:
                break
            time.sleep(0.3)

        if not username_input or not password_input:
            local_errors.append("Login form not found on the portal.")
            cleanup_driver(driver)
            return local_errors

        username_input.clear()
        username_input.send_keys(username_value)
        password_input.clear()
        password_input.send_keys(password_value)
        password_input.send_keys(Keys.TAB)
        time.sleep(0.4)

        sign_in = find_first(
            driver,
            [
                (By.XPATH, "//button[normalize-space()='Sign In']"),
                (By.XPATH, "//button[normalize-space()='Sign in']"),
                (By.XPATH, "//button[normalize-space()='Signin']"),
                (By.CSS_SELECTOR, "input[type='submit']"),
            ],
        )
        if sign_in:
            sign_in.click()

        try:
            target = wait.until(EC.element_to_be_clickable((By.XPATH, target_xpath)))
            try:
                driver.execute_script("arguments[0].scrollIntoView({behavior:'smooth', block:'center'});", target)
            except Exception:
                pass
            target.click()
        except Exception as exc:
            local_errors.append(f"Target card not found: {exc}")
            cleanup_driver(driver)
            return local_errors

        followup_xpath = "/html/body/div[1]/div[2]/div/div[2]/div/div[2]/h3[2]/span/a"
        try:
            handles_before = set(driver.window_handles)
            deadline = time.time() + 15
            while time.time() < deadline:
                handles_now = set(driver.window_handles)
                new_handles = list(handles_now - handles_before)
                if new_handles:
                    driver.switch_to.window(new_handles[0])
                    break
                time.sleep(0.3)

            zoom_handle = None
            for handle in driver.window_handles:
                driver.switch_to.window(handle)
                if "zoom.us" in (driver.current_url or ""):
                    zoom_handle = handle
                    break
            if zoom_handle:
                driver.switch_to.window(zoom_handle)

            try:
                click_join_from_browser(driver, timeout=5)
            except Exception:
                pass

            followup = None
            # try:
            #     followup = wait.until(EC.element_to_be_clickable((By.XPATH, followup_xpath)))
            # except Exception:
            #     pass
            # if followup:
            #     followup.click()
            # else:
            # driver.current_window_handle
            try_selectors(driver, [
                (By.CSS_SELECTOR, "zoom-button zoom-button--large zoom-button--secondary g7nkJFrV"),
                (By.CLASS_NAME, "zoom-button zoom-button--large zoom-button--secondary g7nkJFrV"),
                (By.XPATH, "/html/body/div[1]/div[2]/div/div[2]/div/div[1]/div/button[2]"),
                (By.XPATH, '//*[@id="zoom-ui-frame"]/div[2]/div/div[1]/div/button[2]'),
            ], timeout_each=8)


            try:
                click_continue_without_mic_camera(driver, timeout=20)
            except Exception:
                pass

            # try:
            #     followup_button = wait.until(
            #         EC.element_to_be_clickable(
            #             (By.XPATH, "/html/body/div[2]/div[2]/div/div[1]/div/div[2]/button")
            #         )
            #     )
            #     followup_button.click()
            # except Exception:
            #     pass

            # try:
            #     disable_zoom_media_prompts(driver, timeout=10)
            # except Exception:
            #     pass

            try:
                name_input = find_name_input(driver, timeout=10)
                name_input.send_keys(Keys.RETURN)
                time.sleep(2)
            except Exception as e:
                print(e)
                pass
        except Exception as exc:
            local_errors.append(f"Follow-up target not found: {exc}")
            cleanup_driver(driver)
            return local_errors
        return local_errors

    with ThreadPoolExecutor(max_workers=thread_count) as executor:
        futures = [executor.submit(join_class, cred) for cred in credentials]
        for future in as_completed(futures):
            try:
                errs = future.result()
                if errs:
                    errors.extend(errs)
            except Exception as exc:  # pragma: no cover - worker crash
                errors.append(str(exc))

    if errors:
        raise RuntimeError("; ".join(errors))


def save_login_course_report(results: Iterable[dict]):
    """
    Persist login attempt summaries to CSV for later reference.
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = REPORTS_DIR / f"login_report_{timestamp}.csv"
    try:
        _ensure_parent(report_path)
        with report_path.open("w", newline="", encoding="utf-8") as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=ATTENDANCE_HEADERS)
            writer.writeheader()
            for idx, row in enumerate(results, 1):
                row_data = {header: "" for header in ATTENDANCE_HEADERS}
                row_data["SNo."] = idx
                row_data["Client Email"] = row.get("email", "")
                if row.get("status") == "Success":
                    attendance = row.get("attendance") or {}
                    if attendance:
                        row_data["Month"] = attendance.get("month", "")
                        row_data["Day"] = attendance.get("day", "")
                        row_data["Signin"] = attendance.get("signin", "")
                        row_data["Signout"] = attendance.get("signout", "")
                        row_data["Total Time"] = attendance.get("total_time", "")
                        row_data["Attendance Status"] = attendance.get("status", "")
                        row_data["Action"] = attendance.get("action", "")
                    else:
                        ts = row.get("timestamp") or datetime.now()
                        row_data["Month"] = ts.strftime("%Y-%m-%d")
                        row_data["Day"] = ts.strftime("%A")
                        row_data["Signin"] = ts.strftime("%H:%M:%S")
                        row_data["Signout"] = ts.strftime("%H:%M:%S")
                        row_data["Total Time"] = "00:00:00"
                        row_data["Attendance Status"] = "P"
                        row_data["Action"] = "Logs"
                else:
                    row_data["Attendance Status"] = ""
                    row_data["Action"] = ""
                row_data["Login Status"] = row.get("status", "")
                row_data["Login Detail"] = row.get("message", "Credentials submitted to TAHA portal.")
                writer.writerow(row_data)
        return {"saved": True, "path": str(report_path), "error": ""}
    except Exception as exc:  # pragma: no cover - surfaced via UI
        return {"saved": False, "path": "", "error": str(exc)}


def save_login_status_report(results: Iterable[dict]):
    """
    Export a simple login status sheet with Username and Login Status columns.
    """
    timestamp = datetime.now().strftime("%Y%m%d")
    report_path = REPORTS_DIR / f"login_status_{timestamp}.xlsx"
    try:
        _ensure_parent(report_path)
        rows = []
        for row in results:
            username = row.get("email") or row.get("id", "")
            status = "Login Success" if row.get("status") == "Success" else "Login Error"
            rows.append({"Username": username, "Login Status": status})
        if not rows:
            rows = [{"Username": "", "Login Status": ""}]
        df = pd.DataFrame(rows)
        df.to_excel(report_path, index=False)
        return {"saved": True, "path": str(report_path), "error": ""}
    except Exception as exc:  # pragma: no cover - surfaced via UI
        return {"saved": False, "path": "", "error": str(exc)}


def store_results_in_db(results: Iterable[dict], mode: str):
    _init_db()
    payload = []
    created = datetime.now().isoformat(timespec="seconds")
    for row in results:
        attendance = row.get("attendance") or {}
        payload.append(
            (
                row.get("email") or row.get("id", ""),
                mode,
                row.get("status", ""),
                row.get("message", ""),
                attendance.get("month", ""),
                attendance.get("day", ""),
                attendance.get("signin", ""),
                attendance.get("signout", ""),
                attendance.get("total_time", ""),
                attendance.get("status", ""),
                attendance.get("action", ""),
                created,
            )
        )

    if not payload:
        return

    with sqlite3.connect(DB_PATH) as conn:
        conn.executemany(
            """
            INSERT INTO login_results (
                username,
                mode,
                status,
                detail,
                month,
                day,
                signin,
                signout,
                total_time,
                attendance_status,
                action,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            payload,
        )
        conn.commit()


def store_credentials_in_db(credentials: Iterable[dict]):
    _init_db()
    created = datetime.now().isoformat(timespec="seconds")
    payload = []
    for row in credentials:
        username = (row.get("username") or row.get("id") or "").strip()
        password = str(row.get("password", "")).strip()
        if not username:
            continue
        payload.append((username, password, created))

    if not payload:
        return

    with sqlite3.connect(DB_PATH) as conn:
        conn.executemany(
            """
            INSERT OR REPLACE INTO credentials (
                username,
                password,
                created_at
            ) VALUES (?, ?, ?)
            """,
            payload,
        )
        conn.commit()


def load_credentials_from_db() -> list[dict]:
    _init_db()
    if not DB_PATH.is_file():
        return []
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT username, password
            FROM credentials
            ORDER BY id DESC
            """
        ).fetchall()
    seen = set()
    results = []
    for row in rows:
        username = row["username"]
        if not username:
            continue
        key = str(username).strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        results.append(
            {"id": username, "username": username, "password": row["password"]}
        )
    return results


def store_report_metadata(
    mode: str,
    report_type: str,
    total: int,
    success: int,
    failed: int,
    errors: int,
    report_path: str,
    report_error: str,
):
    _init_db()
    created = datetime.now().isoformat(timespec="seconds")
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            INSERT INTO report_logs (
                mode,
                report_type,
                total,
                success,
                failed,
                errors,
                report_path,
                report_error,
                created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                mode,
                report_type,
                total,
                success,
                failed,
                errors,
                report_path,
                report_error,
                created,
            ),
        )
        conn.commit()
