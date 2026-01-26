from __future__ import annotations

import csv
import os
import shutil
import sys
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
import sqlite3
from pathlib import Path
from time import perf_counter
from typing import Iterable, List, Sequence

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
DATA_DIR = APP_DATA_DIR / "data"
TEMPLATES_DIR = APP_DATA_DIR / "templates"
CURRENT_PORTAL = "connect"
LEGACY_DB_PATH = DATA_DIR / "taha_bot.db"
DB_PATH = DATA_DIR / "taha_bot_connect.db"
DEFAULT_WINDOW_SIZE = (1400, 900)
DEFAULT_WINDOW_POS = (0, 0)
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
        conn.commit()


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
        if template_source and template_source.is_file():
            shutil.copy(template_source, target_path)
        else:
            df = pd.DataFrame(columns=list(columns or ["Username", "Password"]))
            df.to_excel(target_path, index=False)
        return {"saved": True, "path": str(target_path), "error": ""}
    except Exception as exc:  # pragma: no cover - surfaced via UI
        return {"saved": False, "path": "", "error": str(exc)}


def load_credentials(file_path: Path, id_column: str, password_column: str):
    """
    Load credential rows into dictionaries with string id/password entries.
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
        records.append({"id": identifier, "username": identifier, "password": password})
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


def _build_driver(incognito: bool = False, headless: bool = False):
    try:
        from selenium import webdriver
        from selenium.common.exceptions import WebDriverException
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.chrome.service import Service
    except ImportError as exc:  # pragma: no cover - surfaced to UI
        raise RuntimeError("Selenium is required. Install via 'pip install selenium'.") from exc

    options = Options()
    viewport = f"--window-size={DEFAULT_WINDOW_SIZE[0]},{DEFAULT_WINDOW_SIZE[1]}"
    if headless:
        options.add_argument("--headless=new")
        options.add_argument(viewport)
    else:
        options.add_argument(viewport)
        options.add_argument(f"--window-position={DEFAULT_WINDOW_POS[0]},{DEFAULT_WINDOW_POS[1]}")
    options.add_argument("--disable-notifications")
    options.add_argument("--disable-geolocation")
    options.add_argument("--disable-infobars")
    options.add_argument("--disable-extensions")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_argument("--use-fake-ui-for-media-stream")
    options.add_argument("--use-fake-device-for-media-stream")
    prefs = {
        "profile.default_content_setting_values.notifications": 2,
        "profile.default_content_setting_values.popups": 2,
        "profile.default_content_setting_values.geolocation": 2,
        "profile.default_content_setting_values.media_stream_mic": 2,
        "profile.default_content_setting_values.media_stream_camera": 2,
    }
    options.add_experimental_option("prefs", prefs)
    if incognito:
        options.add_argument("--incognito")

    local_driver = _locate_local_driver()
    if local_driver:
        try:
            browser = webdriver.Chrome(service=Service(executable_path=str(local_driver)), options=options)
        except WebDriverException as nested_exc:
            raise RuntimeError(
                "ChromeDriver was found locally but could not be started. "
                f"Original error: {nested_exc}"
            ) from nested_exc
        _apply_window_bounds(browser)
        return browser

    try:
        browser = webdriver.Chrome(options=options)
        _apply_window_bounds(browser)
        return browser
    except WebDriverException as exc:  # pragma: no cover
        raise RuntimeError(
            "Unable to launch ChromeDriver automatically. Install Google Chrome, ensure Selenium Manager "
            "dependencies (including PowerShell) are available, or manually download chromedriver.exe "
            "and place it in the 'drivers' folder (or set CHROMEDRIVER env). "
            f"Original error: {exc}"
        ) from exc


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
        try:
            ctx["driver"].quit()
        except Exception:
            pass
    ACTIVE_DRIVERS = []


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
    Automate the TAHA login form and feed Username/Password pairs sequentially.
    """
    try:
        from selenium.webdriver.common.by import By
        from selenium.webdriver.common.keys import Keys
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.webdriver.support.ui import WebDriverWait
    except ImportError as exc:  # pragma: no cover - surfaced to UI
        raise RuntimeError("Selenium is required for automated logins. Install via 'pip install selenium'.") from exc

    username_selector = (By.ID, "emailForm")
    password_selector = (By.ID, "pwdform")
    submit_selector = (By.CSS_SELECTOR, "button[type='submit']")
    attendance_selector = (By.XPATH, '//*[@id="navbar-navlist"]/li[4]/a')
    attendance_row_selector = (By.XPATH, "/html/body/section[2]/div/div[2]/div/div/table/tbody/tr[1]")
    capture_attendance = mode != "login"

    start = perf_counter()
    results = []
    browser_error = ""
    drivers: list[dict] = []

    def _new_driver():
        browser = _build_driver(incognito=incognito, headless=headless)
        wait_obj = WebDriverWait(browser, 20)
        browser.get(login_url)
        time.sleep(2)
        return {"driver": browser, "wait": wait_obj}

    try:
        _close_active_drivers()
        total_credentials = len(credentials)
        pool_size = max(1, min(concurrency or 1, total_credentials))
        for _ in range(pool_size):
            drivers.append(_new_driver())
        ACTIVE_DRIVERS = drivers

        if not drivers:
            raise RuntimeError("Unable to launch any browser instances.")

        for index, item in enumerate(credentials, 1):
            driver_idx = (index - 1) % len(drivers)
            ctx = drivers[driver_idx]
            browser = ctx["driver"]
            wait = ctx["wait"]

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
                    username_input = wait.until(EC.presence_of_element_located(username_selector))
                    password_input = wait.until(EC.presence_of_element_located(password_selector))
                    submit_btn = wait.until(EC.element_to_be_clickable(submit_selector))

                    username_input.clear()
                    username_input.send_keys(username_value)
                    password_input.clear()
                    password_input.send_keys(password_value)
                    password_input.send_keys(Keys.TAB)
                    time.sleep(0.5)
                    try:
                        browser.execute_script(
                            "arguments[0].scrollIntoView({behavior:'smooth', block:'center'});",
                            submit_btn,
                        )
                    except Exception:
                        pass
                    submit_btn.click()
                    time.sleep(2.5)

                    login_status = "Success"
                    login_detail = "Credentials submitted to TAHA portal."

                    for selector in [
                        "//*[contains(@class,'alert') and contains(@class,'alert-danger')]",
                        "//*[contains(@class,'alert') and contains(@class,'alert-error')]",
                        "//div[@role='alert']",
                        "//span[contains(@class,'error')]",
                    ]:
                        try:
                            alert_element = browser.find_element(By.XPATH, selector)
                            alert_text = alert_element.text.strip()
                            if alert_text:
                                login_status = "Failed"
                                login_detail = alert_text
                                break
                        except Exception:
                            continue

                    timestamp = datetime.now()
                    attendance_data: dict[str, str] = {}

                    if capture_attendance and login_status == "Success":
                        try:
                            attendance_link = wait.until(EC.element_to_be_clickable(attendance_selector))
                            try:
                                browser.execute_script(
                                    "arguments[0].scrollIntoView({behavior:'smooth', block:'center'});",
                                    attendance_link,
                                )
                            except Exception:
                                pass
                            attendance_link.click()
                            time.sleep(1.2)
                            row_element = wait.until(EC.presence_of_element_located(attendance_row_selector))
                            cells = row_element.find_elements(By.TAG_NAME, "td")
                            if not cells:
                                cells = row_element.find_elements(By.XPATH, "./*")

                            def cell_text(idx: int) -> str:
                                if idx < len(cells):
                                    return cells[idx].text.strip()
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
                except Exception as exc:  # pragma: no cover - automation issues
                    msg = str(exc)
                    if "invalid session id" in msg.lower() and attempt == 1:
                        try:
                            if ctx.get("driver"):
                                try:
                                    ctx["driver"].quit()
                                except Exception:
                                    pass
                        finally:
                            drivers[driver_idx] = ctx = _new_driver()
                            browser = ctx["driver"]
                            wait = ctx["wait"]
                        continue  # retry this credential once with fresh session
                    browser_error = msg
                    results.append(
                        {
                            "id": username_value or f"Row {index}",
                            "status": "Error",
                            "message": f"Automation failed: {msg}",
                            "email": username_value,
                        }
                    )
                    break

            if index + len(drivers) <= total_credentials:
                try:
                    browser.get(login_url)
                    time.sleep(1.5)
                except Exception as exc:
                    if "invalid session id" in str(exc).lower():
                        drivers[driver_idx] = ctx = _new_driver()
                        browser = ctx["driver"]
                        wait = ctx["wait"]
                        time.sleep(1.0)
    except Exception as exc:
        browser_error = str(exc)
    finally:
        if not KEEP_BROWSER_OPEN:
            _close_active_drivers()

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


def click_continue_without_mic_camera(driver, timeout=20) -> bool:
    """Iterate through iframes to press any 'Continue without audio/video' control on Zoom join."""
    try:
        from selenium.webdriver.common.by import By
    except Exception:
        return False
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
    clicked_once = False
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


def find_name_input(driver, timeout=20):
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
            last_error = exc
            break
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

    def join_class(cred):
        local_errors: list[str] = []
        try:
            # create a fresh browser per credential so existing joined classes stay open
            driver = _build_driver(incognito=False, headless=False)
            wait = WebDriverWait(driver, 25)
            with active_lock:
                ACTIVE_DRIVERS.append({"driver": driver, "wait": wait})

            driver.get(portal_url)
            time.sleep(1.5)

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

                followup = None
                try:
                    followup = wait.until(EC.element_to_be_clickable((By.XPATH, followup_xpath)))
                except Exception:
                    pass
                if followup:
                    followup.click()
                else:
                    join_link = wait.until(
                        EC.element_to_be_clickable(
                            (By.XPATH, "//a[contains(normalize-space(),'Join from your browser')]")
                        )
                    )
                    join_link.click()

                try:
                    click_continue_without_mic_camera(driver, timeout=20)
                except Exception:
                    pass

                try:
                    followup_button = wait.until(
                        EC.element_to_be_clickable(
                            (By.XPATH, "/html/body/div[2]/div[2]/div/div[1]/div/div[2]/button")
                        )
                    )
                    followup_button.click()
                except Exception:
                    pass

                try:
                    disable_zoom_media_prompts(driver, timeout=10)
                except Exception:
                    pass

                try:
                    name_input = find_name_input(driver, timeout=10)
                    try:
                        name_input.clear()
                    except Exception:
                        pass
                    try:
                        name_input.send_keys(display_name)
                    except Exception:
                        pass
                    name_input.send_keys(Keys.RETURN)
                    time.sleep(2)
                except Exception as e:
                    print(e)
                    pass
            except Exception as exc:
                local_errors.append(f"Follow-up target not found: {exc}")
                return local_errors
        except Exception as exc:
            local_errors.append(str(exc))
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
