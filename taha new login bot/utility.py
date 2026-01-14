from __future__ import annotations

import csv
import os
import shutil
import time
from datetime import datetime
import sqlite3
from pathlib import Path
from time import perf_counter
from typing import Iterable, List, Sequence

import pandas as pd


BASE_DIR = Path(__file__).resolve().parent
REPORTS_DIR = BASE_DIR / "reports"
DRIVER_DIR = BASE_DIR / "drivers"
KEEP_BROWSER_OPEN = True
ACTIVE_DRIVERS: list[dict] = []
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "taha_bot.db"
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
):
    """
    Copy an existing Excel template or generate a fresh one with the expected columns.
    """
    downloads_dir = BASE_DIR / "templates"
    target_path = downloads_dir / default_filename
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
        DRIVER_DIR / "chromedriver.exe",
        BASE_DIR / "chromedriver.exe",
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


def _build_driver(incognito: bool = False):
    try:
        from selenium import webdriver
        from selenium.common.exceptions import WebDriverException
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.chrome.service import Service
    except ImportError as exc:  # pragma: no cover - surfaced to UI
        raise RuntimeError("Selenium is required. Install via 'pip install selenium'.") from exc

    options = Options()
    options.add_argument("--start-maximized")
    options.add_argument("--disable-notifications")
    options.add_argument("--disable-infobars")
    options.add_argument("--disable-extensions")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    if incognito:
        options.add_argument("--incognito")

    local_driver = _locate_local_driver()
    if local_driver:
        try:
            return webdriver.Chrome(service=Service(executable_path=str(local_driver)), options=options)
        except WebDriverException as nested_exc:
            raise RuntimeError(
                "ChromeDriver was found locally but could not be started. "
                f"Original error: {nested_exc}"
            ) from nested_exc

    try:
        return webdriver.Chrome(options=options)
    except WebDriverException as exc:  # pragma: no cover
        raise RuntimeError(
            "Unable to launch ChromeDriver automatically. Install Google Chrome, ensure Selenium Manager "
            "dependencies (including PowerShell) are available, or manually download chromedriver.exe "
            "and place it in the 'drivers' folder (or set CHROMEDRIVER env). "
            f"Original error: {exc}"
        ) from exc


def _close_active_drivers():
    global ACTIVE_DRIVERS
    for ctx in ACTIVE_DRIVERS:
        try:
            ctx["driver"].quit()
        except Exception:
            pass
    ACTIVE_DRIVERS = []


def run_login_batch(
    credentials: List[dict],
    login_url: str,
    concurrency: int = 1,
    incognito: bool = False,
    mode: str = "attendance",
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

    try:
        _close_active_drivers()
        total_credentials = len(credentials)
        pool_size = max(1, min(concurrency or 1, total_credentials))
        for _ in range(pool_size):
            browser = _build_driver(incognito=incognito)
            wait = WebDriverWait(browser, 20)
            browser.get(login_url)
            time.sleep(2)
            drivers.append({"driver": browser, "wait": wait})
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
            except Exception as exc:  # pragma: no cover - automation issues
                browser_error = str(exc)
                results.append(
                    {
                        "id": username_value or f"Row {index}",
                        "status": "Error",
                        "message": f"Automation failed: {exc}",
                        "email": username_value,
                    }
                )

            if index + len(drivers) <= total_credentials:
                browser.get(login_url)
                time.sleep(1.5)
    except Exception as exc:
        browser_error = str(exc)
    finally:
        if not KEEP_BROWSER_OPEN:
            _close_active_drivers()

    elapsed = perf_counter() - start
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
