from __future__ import annotations

from pathlib import Path
from datetime import datetime
import shutil
import sqlite3

import webview

from utility import (
    DB_PATH,
    _init_db,
    _ensure_parent,
    REPORTS_DIR,
    download_template,
    load_credentials_from_db,
    load_credentials,
    run_login_batch,
    save_login_course_report,
    save_login_status_report,
    store_credentials_in_db,
    store_report_metadata,
)


APP_TITLE = "TAHA College Detail Bot"
BASE_DIR = Path(__file__).resolve().parent
WEB_DIR = BASE_DIR / "web"
TEMPLATE_SOURCE = BASE_DIR / "login_template.xlsx"
LOGIN_URL = "https://students.tahacollege.ca/studentportal/login/?msg="


class Api:
    def __init__(self, template_source: Path):
        # Keep Path private so pywebview does not try to serialize it
        self._template_source = Path(template_source)
        self.upload_path = ""

    @staticmethod
    def _read_columns(file_path: Path):
        suffix = file_path.suffix.lower()
        try:
            import pandas as pd
        except Exception as exc:
            raise RuntimeError(f"Pandas is required to read templates: {exc}") from exc

        if suffix in {".xlsx", ".xls", ".xlsm"}:
            df = pd.read_excel(file_path, nrows=0)
        elif suffix == ".csv":
            df = pd.read_csv(file_path, nrows=0)
        else:
            raise ValueError("Unsupported file type. Use .xlsx, .xls, or .csv.")

        return [str(col) for col in df.columns]

    def select_upload_file(self):
        file_types = (
            "Excel Files (*.xlsx;*.xls)",
            "CSV Files (*.csv)",
            "All Files (*.*)",
        )
        selection = webview.windows[0].create_file_dialog(
            webview.FileDialog.OPEN, allow_multiple=False, file_types=file_types
        )
        if not selection:
            return {"path": "", "columns": []}

        selected_path = Path(selection[0])
        try:
            columns = self._read_columns(selected_path)
            self.upload_path = str(selected_path)
            return {"path": str(selected_path), "columns": columns}
        except Exception as exc:
            self.upload_path = str(selected_path)
            return {
                "path": str(selected_path),
                "columns": [],
                "error": f"Failed to read columns: {exc}",
            }

    def save_template(self):
        file_types = ("Excel Files (*.xlsx)", "All Files (*.*)")
        selection = webview.windows[0].create_file_dialog(
            webview.FileDialog.SAVE,
            save_filename="login_template.xlsx",
            file_types=file_types,
        )
        if not selection:
            return {"saved": False, "path": "", "error": "Save cancelled."}
        selected_path = Path(selection[0]) if isinstance(selection, (list, tuple)) else Path(selection)
        return download_template(
            template_source=self._template_source,
            columns=["Username", "Password"],
            default_filename="login_template.xlsx",
            target_path=selected_path,
        )

    def _normalize_query(self, value: str) -> str:
        return str(value or "").strip().lower()

    def save_client_report(self, query: str):
        normalized = self._normalize_query(query)
        if not normalized:
            return {"saved": False, "path": "", "error": "Client query is required."}

        data = self.get_report_data(limit=2000)
        credentials = [
            row for row in data.get("credentials", [])
            if self._normalize_query(row.get("username")).find(normalized) != -1
        ]
        login_status = [
            row for row in data.get("login_status", [])
            if self._normalize_query(row.get("username")).find(normalized) != -1
        ]
        attendance = [
            row for row in data.get("attendance", [])
            if self._normalize_query(row.get("username")).find(normalized) != -1
        ]
        if not credentials and not login_status and not attendance:
            return {"saved": False, "path": "", "error": "No matching client data found."}

        try:
            import pandas as pd
        except Exception as exc:
            return {"saved": False, "path": "", "error": f"Pandas is required: {exc}"}

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_query = "".join(ch for ch in normalized if ch.isalnum() or ch in {"_", "-"}).strip("-_")
        if not safe_query:
            safe_query = "client"
        report_path = REPORTS_DIR / f"client_{safe_query}_{timestamp}.xlsx"
        _ensure_parent(report_path)

        try:
            with pd.ExcelWriter(report_path, engine="openpyxl") as writer:
                if credentials:
                    pd.DataFrame(credentials).to_excel(writer, sheet_name="Credentials", index=False)
                if login_status:
                    pd.DataFrame(login_status).to_excel(writer, sheet_name="Login Status", index=False)
                if attendance:
                    pd.DataFrame(attendance).to_excel(writer, sheet_name="Attendance", index=False)
                if not credentials and not login_status and not attendance:
                    pd.DataFrame([{"Message": "No data"}]).to_excel(writer, sheet_name="Report", index=False)
        except Exception as exc:
            return {"saved": False, "path": "", "error": str(exc)}

        return {"saved": True, "path": str(report_path), "error": ""}

    def list_client_reports(self):
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        files = sorted(REPORTS_DIR.glob("client_*.xlsx"), key=lambda p: p.stat().st_mtime, reverse=True)
        result = [
            {
                "name": file.name,
                "path": str(file),
                "modified_at": datetime.fromtimestamp(file.stat().st_mtime).isoformat(timespec="seconds"),
            }
            for file in files
            if file.is_file()
        ]
        return {"files": result}

    def export_report_file(self, path: str):
        try:
            source = Path(path)
        except Exception:
            return {"saved": False, "path": "", "error": "Invalid file path."}
        if not source.is_file():
            return {"saved": False, "path": "", "error": "File not found."}
        file_types = ("Excel Files (*.xlsx)", "All Files (*.*)")
        selection = webview.windows[0].create_file_dialog(
            webview.FileDialog.SAVE,
            save_filename=source.name,
            file_types=file_types,
        )
        if not selection:
            return {"saved": False, "path": "", "error": "Save cancelled."}
        destination = Path(selection[0]) if isinstance(selection, (list, tuple)) else Path(selection)
        try:
            shutil.copy(source, destination)
        except Exception as exc:
            return {"saved": False, "path": "", "error": str(exc)}
        return {"saved": True, "path": str(destination), "error": ""}

    def save_excel_report(self, rows: list, filename: str = "login_status_filtered.xlsx"):
        file_types = ("Excel Files (*.xlsx)", "All Files (*.*)")
        selection = webview.windows[0].create_file_dialog(
            webview.FileDialog.SAVE,
            save_filename=filename or "login_status_filtered.xlsx",
            file_types=file_types,
        )
        if not selection:
            return {"saved": False, "path": "", "error": "Save cancelled."}
        destination = Path(selection[0]) if isinstance(selection, (list, tuple)) else Path(selection)
        try:
            import pandas as pd
        except Exception as exc:
            pd = None
        try:
            if pd is not None:
                df = pd.DataFrame(rows or [])
                df.to_excel(destination, index=False)
            else:
                from openpyxl import Workbook
                workbook = Workbook()
                sheet = workbook.active
                sheet.title = "Filtered Results"
                rows = rows or []
                headers = list(rows[0].keys()) if rows else []
                if headers:
                    sheet.append(headers)
                    for row in rows:
                        sheet.append([row.get(header, "") for header in headers])
                workbook.save(destination)
        except Exception as exc:
            return {"saved": False, "path": "", "error": str(exc)}
        return {"saved": True, "path": str(destination), "error": ""}

    def start_login(self, options=None):
        options = options or {}
        concurrency = int(options.get("threads", 1) or 1)
        incognito = bool(options.get("incognito", False))
        mode = options.get("mode") or "attendance"
        source = options.get("source") or "file"
        testing = bool(options.get("testing", False))
        if mode not in {"attendance", "login"}:
            return {"error": "Select a login or attendance status option."}

        if testing and source != "file":
            return {"error": "Testing mode requires a file upload."}

        if source == "stored":
            credentials = load_credentials_from_db()
        else:
            if not self.upload_path:
                return {"error": "Upload a template first."}
            try:
                credentials = load_credentials(Path(self.upload_path), id_column="Username", password_column="Password")
            except Exception as exc:
                return {"error": f"Failed to load credentials: {exc}"}

        if not credentials:
            if source == "stored":
                return {"error": "No credentials found in stored data."}
            return {"error": "No credentials found in the template."}

        if source == "file" and not testing:
            try:
                store_credentials_in_db(credentials)
            except Exception:
                pass

        try:
            result = run_login_batch(
                credentials,
                login_url=LOGIN_URL,
                concurrency=concurrency,
                incognito=incognito,
                mode=mode,
                store_results=not testing,
            )
        except Exception as exc:
            return {"error": f"Automation failed: {exc}"}

        counts = {"Success": 0, "Failed": 0, "Error": 0}
        for item in result.get("results", []):
            status = item.get("status")
            if status in counts:
                counts[status] += 1

        report_result = {"saved": False, "path": "", "error": ""}
        if not testing:
            if mode == "attendance":
                report_result = save_login_course_report(result.get("results", []))
                report_type = "attendance"
            else:
                report_result = save_login_status_report(result.get("results", []))
                report_type = "login"

            try:
                store_report_metadata(
                    mode=mode,
                    report_type=report_type,
                    total=len(credentials),
                    success=counts["Success"],
                    failed=counts["Failed"],
                    errors=counts["Error"],
                    report_path=report_result.get("path", ""),
                    report_error=report_result.get("error", ""),
                )
            except Exception:
                pass

        testing_rows = []
        if testing:
            for row in result.get("results", []):
                created_at = row.get("timestamp")
                if hasattr(created_at, "isoformat"):
                    created_at = created_at.isoformat(timespec="seconds")
                attendance = row.get("attendance") or {}
                base = {
                    "Username": row.get("email") or row.get("id", ""),
                    "Status": row.get("status", ""),
                    "Detail": row.get("message", ""),
                    "Created": created_at or "",
                }
                if mode == "attendance":
                    base.update(
                        {
                            "Month": attendance.get("month", ""),
                            "Day": attendance.get("day", ""),
                            "Signin": attendance.get("signin", ""),
                            "Signout": attendance.get("signout", ""),
                            "Total Time": attendance.get("total_time", ""),
                            "Attendance Status": attendance.get("status", ""),
                            "Action": attendance.get("action", ""),
                        }
                    )
                testing_rows.append(base)

        return {
            "total": len(credentials),
            "success": counts["Success"],
            "failed": counts["Failed"],
            "errors": counts["Error"],
            "elapsed_seconds": result.get("elapsed_seconds", 0),
            "report_saved": report_result.get("saved", False),
            "report_path": report_result.get("path", ""),
            "report_error": report_result.get("error", ""),
            "browser_error": result.get("browser_error", ""),
            "mode": mode,
            "testing": testing,
            "testing_rows": testing_rows,
        }

    def get_report_data(self, limit: int = 200):
        safe_limit = max(1, int(limit or 200))
        _init_db()
        if not DB_PATH.is_file():
            return {
                "login_results": [],
                "report_logs": [],
                "credentials": [],
                "login_status": [],
                "attendance": [],
                "limit": safe_limit,
            }

        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            login_rows = conn.execute(
                """
                SELECT
                    id,
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
                FROM login_results
                ORDER BY id DESC
                LIMIT ?
                """,
                (safe_limit,),
            ).fetchall()
            report_rows = conn.execute(
                """
                SELECT
                    id,
                    mode,
                    report_type,
                    total,
                    success,
                    failed,
                    errors,
                    report_path,
                    report_error,
                    created_at
                FROM report_logs
                ORDER BY id DESC
                LIMIT ?
                """,
                (safe_limit,),
            ).fetchall()
            credential_rows = conn.execute(
                """
                SELECT
                    id,
                    username,
                    password,
                    created_at
                FROM credentials
                ORDER BY id DESC
                LIMIT ?
                """,
                (safe_limit,),
            ).fetchall()
            login_status_rows = conn.execute(
                """
                SELECT
                    id,
                    username,
                    status,
                    detail,
                    created_at
                FROM login_results
                WHERE mode = 'login'
                ORDER BY id DESC
                LIMIT ?
                """,
                (safe_limit,),
            ).fetchall()
            attendance_rows = conn.execute(
                """
                SELECT
                    id,
                    username,
                    month,
                    day,
                    signin,
                    signout,
                    total_time,
                    attendance_status,
                    action,
                    created_at
                FROM login_results
                WHERE mode = 'attendance'
                ORDER BY id DESC
                LIMIT ?
                """,
                (safe_limit,),
            ).fetchall()

        return {
            "login_results": [dict(row) for row in login_rows],
            "report_logs": [dict(row) for row in report_rows],
            "credentials": [dict(row) for row in credential_rows],
            "login_status": [dict(row) for row in login_status_rows],
            "attendance": [dict(row) for row in attendance_rows],
            "limit": safe_limit,
        }

    def update_credential(self, old_username: str, new_username: str, password: str):
        _init_db()
        old_username = (old_username or "").strip()
        new_username = (new_username or "").strip()
        password = (password or "").strip()
        if not old_username or not new_username:
            return {"saved": False, "error": "Username is required."}

        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            existing = conn.execute(
                "SELECT id FROM credentials WHERE username = ?",
                (new_username,),
            ).fetchone()
            if existing and new_username != old_username:
                return {"saved": False, "error": "Username already exists."}

            cursor = conn.execute(
                """
                UPDATE credentials
                SET username = ?, password = ?
                WHERE username = ?
                """,
                (new_username, password, old_username),
            )
            conn.commit()

        if cursor.rowcount == 0:
            return {"saved": False, "error": "Credential not found."}
        return {"saved": True, "error": ""}

    def delete_credential(self, username: str):
        _init_db()
        username = (username or "").strip()
        if not username:
            return {"deleted": False, "error": "Username is required."}

        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.execute(
                "DELETE FROM credentials WHERE username = ?",
                (username,),
            )
            conn.commit()

        if cursor.rowcount == 0:
            return {"deleted": False, "error": "Credential not found."}
        return {"deleted": True, "error": ""}

    def update_login_status(self, row_id: int, status: str, detail: str):
        _init_db()
        try:
            row_id = int(row_id)
        except (TypeError, ValueError):
            return {"saved": False, "error": "Invalid record id."}

        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.execute(
                """
                UPDATE login_results
                SET status = ?, detail = ?
                WHERE id = ?
                """,
                (status or "", detail or "", row_id),
            )
            conn.commit()

        if cursor.rowcount == 0:
            return {"saved": False, "error": "Record not found."}
        return {"saved": True, "error": ""}

    def update_attendance(self, row_id: int, payload: dict):
        _init_db()
        try:
            row_id = int(row_id)
        except (TypeError, ValueError):
            return {"saved": False, "error": "Invalid record id."}

        allowed = [
            "month",
            "day",
            "signin",
            "signout",
            "total_time",
            "attendance_status",
            "action",
        ]
        updates = {key: str(payload.get(key, "")).strip() for key in allowed}

        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.execute(
                """
                UPDATE login_results
                SET month = ?, day = ?, signin = ?, signout = ?, total_time = ?,
                    attendance_status = ?, action = ?
                WHERE id = ?
                """,
                (
                    updates["month"],
                    updates["day"],
                    updates["signin"],
                    updates["signout"],
                    updates["total_time"],
                    updates["attendance_status"],
                    updates["action"],
                    row_id,
                ),
            )
            conn.commit()

        if cursor.rowcount == 0:
            return {"saved": False, "error": "Record not found."}
        return {"saved": True, "error": ""}

    def update_credit_hours(self, row_id: int, total_time: str):
        _init_db()
        try:
            row_id = int(row_id)
        except (TypeError, ValueError):
            return {"saved": False, "error": "Invalid record id."}

        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.execute(
                """
                UPDATE login_results
                SET total_time = ?
                WHERE id = ?
                """,
                (total_time or "", row_id),
            )
            conn.commit()

        if cursor.rowcount == 0:
            return {"saved": False, "error": "Record not found."}
        return {"saved": True, "error": ""}

    def delete_login_result(self, row_id: int):
        _init_db()
        try:
            row_id = int(row_id)
        except (TypeError, ValueError):
            return {"deleted": False, "error": "Invalid record id."}

        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.execute(
                "DELETE FROM login_results WHERE id = ?",
                (row_id,),
            )
            conn.commit()

        if cursor.rowcount == 0:
            return {"deleted": False, "error": "Record not found."}
        return {"deleted": True, "error": ""}

    def delete_login_results_by_username(self, username: str):
        _init_db()
        username = (username or "").strip()
        if not username:
            return {"deleted": False, "error": "Username is required."}

        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.execute(
                "DELETE FROM login_results WHERE username = ?",
                (username,),
            )
            conn.commit()

        if cursor.rowcount == 0:
            return {"deleted": False, "error": "Record not found."}
        return {"deleted": True, "error": ""}

    def get_report_summary(self):
        _init_db()
        if not DB_PATH.is_file():
            return {"login_total": 0, "report_total": 0, "latest_report": None, "credential_total": 0}

        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            login_total = conn.execute("SELECT COUNT(*) AS total FROM login_results").fetchone()["total"]
            report_total = conn.execute("SELECT COUNT(*) AS total FROM report_logs").fetchone()["total"]
            credential_total = conn.execute("SELECT COUNT(*) AS total FROM credentials").fetchone()["total"]
            latest_report = conn.execute(
                """
                SELECT
                    id,
                    mode,
                    report_type,
                    total,
                    success,
                    failed,
                    errors,
                    report_path,
                    report_error,
                    created_at
                FROM report_logs
                ORDER BY id DESC
                LIMIT 1
                """
            ).fetchone()

        return {
            "login_total": int(login_total or 0),
            "report_total": int(report_total or 0),
            "credential_total": int(credential_total or 0),
            "latest_report": dict(latest_report) if latest_report else None,
        }

    def get_credentials_count(self):
        _init_db()
        if not DB_PATH.is_file():
            return {"total": 0}
        with sqlite3.connect(DB_PATH) as conn:
            total = conn.execute("SELECT COUNT(*) FROM credentials").fetchone()[0]
        return {"total": int(total or 0)}


def main():
    api = Api(TEMPLATE_SOURCE)
    index_path = WEB_DIR / "index.html"
    if not index_path.is_file():
        raise FileNotFoundError(f"Missing UI file: {index_path}")
    webview.create_window(APP_TITLE, url=index_path.as_uri(), js_api=api, width=980, height=640)
    webview.start()


if __name__ == "__main__":
    main()
