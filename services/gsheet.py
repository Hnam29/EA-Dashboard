"""
Google Sheets service – kết nối và các thao tác CRUD với Google Sheets API.
Dữ liệu được cache 5 phút để tránh vượt quá quota API.
"""

import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

SCOPES = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive",
]

# ── Kết nối ──────────────────────────────────────────────────────────────────

@st.cache_resource(show_spinner=False)
def _get_client() -> gspread.Client:
    """Tạo và cache gspread client (chỉ khởi tạo 1 lần)."""
    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=SCOPES,
    )
    return gspread.authorize(creds)


def _get_spreadsheet() -> gspread.Spreadsheet:
    """Mở spreadsheet chính theo ID trong secrets."""
    client = _get_client()
    spreadsheet_id = st.secrets["google_sheets"]["spreadsheet_id"]
    return client.open_by_key(spreadsheet_id)


def _get_worksheet(sheet_name: str) -> gspread.Worksheet:
    """Lấy worksheet theo tên."""
    return _get_spreadsheet().worksheet(sheet_name)


# ── Đọc dữ liệu (có cache) ───────────────────────────────────────────────────

@st.cache_data(ttl=300, show_spinner=False)
def read_sheet_as_df(sheet_name: str, header_row: int = 1) -> pd.DataFrame:
    """
    Đọc toàn bộ sheet thành DataFrame. Cached 5 phút.
    header_row: dòng tiêu đề (mặc định 1, dùng 2 cho sheet có 2 dòng header).
    Trả về DataFrame rỗng nếu sheet không tồn tại hoặc lỗi.
    """
    try:
        ws = _get_worksheet(sheet_name)
        records = ws.get_all_records(head=header_row, expected_headers=[])
        df = pd.DataFrame(records)
        # Chuẩn hóa tên cột: bỏ khoảng trắng thừa
        df.columns = [str(c).strip() for c in df.columns]
        # Cột STATUS có thể có tên dài nhiều dòng – rút gọn về 'STATUS'
        for col in df.columns:
            if col.startswith("STATUS"):
                df.rename(columns={col: "STATUS"}, inplace=True)
                break
        return df
    except gspread.WorksheetNotFound:
        st.warning(f"Sheet '{sheet_name}' không tồn tại trong Spreadsheet.")
        return pd.DataFrame()
    except Exception as exc:
        st.error(f"Lỗi khi đọc sheet '{sheet_name}': {exc}")
        return pd.DataFrame()


def _clear_cache():
    """Xóa toàn bộ cache sau khi ghi dữ liệu."""
    read_sheet_as_df.clear()


# ── Ghi dữ liệu ──────────────────────────────────────────────────────────────

def append_row(sheet_name: str, data: Dict[str, Any]) -> bool:
    """
    Thêm 1 dòng mới vào cuối sheet.
    data: dict {column_header: value}
    """
    try:
        ws = _get_worksheet(sheet_name)
        headers = ws.row_values(1)
        if not headers:
            st.error(f"Sheet '{sheet_name}' chưa có dòng tiêu đề.")
            return False
        row = [str(data.get(h, "")) for h in headers]
        ws.append_row(row, value_input_option="USER_ENTERED")
        _clear_cache()
        return True
    except Exception as exc:
        st.error(f"Lỗi khi thêm dữ liệu vào '{sheet_name}': {exc}")
        return False


def update_row_by_index(sheet_name: str, sheet_row: int, data: Dict[str, Any]) -> bool:
    """
    Cập nhật dòng dữ liệu (sheet_row là chỉ số dòng thực tế trên sheet, bắt đầu từ 2).
    """
    try:
        ws = _get_worksheet(sheet_name)
        headers = ws.row_values(1)
        row = [str(data.get(h, "")) for h in headers]
        end_col = chr(ord("A") + len(headers) - 1)
        ws.update(f"A{sheet_row}:{end_col}{sheet_row}", [row])
        _clear_cache()
        return True
    except Exception as exc:
        st.error(f"Lỗi khi cập nhật dòng {sheet_row} trong '{sheet_name}': {exc}")
        return False


def delete_row_by_index(sheet_name: str, sheet_row: int) -> bool:
    """
    Xóa dòng theo chỉ số thực tế trên sheet (bắt đầu từ 2 cho dòng dữ liệu đầu tiên).
    """
    try:
        ws = _get_worksheet(sheet_name)
        ws.delete_rows(sheet_row)
        _clear_cache()
        return True
    except Exception as exc:
        st.error(f"Lỗi khi xóa dòng {sheet_row} trong '{sheet_name}': {exc}")
        return False


def export_df_to_new_sheet(df: pd.DataFrame, new_sheet_name: str) -> bool:
    """
    Export DataFrame thành sheet mới trong cùng Spreadsheet.
    Nếu sheet đã tồn tại sẽ ghi đè.
    """
    try:
        sp = _get_spreadsheet()
        # Xóa sheet cũ nếu có
        try:
            old_ws = sp.worksheet(new_sheet_name)
            sp.del_worksheet(old_ws)
        except gspread.WorksheetNotFound:
            pass
        ws = sp.add_worksheet(title=new_sheet_name, rows=len(df) + 1, cols=len(df.columns))
        data = [df.columns.tolist()] + df.values.tolist()
        ws.update(data, value_input_option="USER_ENTERED")
        return True
    except Exception as exc:
        st.error(f"Lỗi khi export sang sheet '{new_sheet_name}': {exc}")
        return False


# ── Audit Log ─────────────────────────────────────────────────────────────────

def log_action(username: str, action: str, details: str) -> None:
    """Ghi lại thao tác người dùng vào sheet audit_log (không hiện lỗi ra UI)."""
    try:
        vn_tz = timezone(timedelta(hours=7))
        append_row("audit_log", {
            "timestamp": datetime.now(vn_tz).strftime("%Y-%m-%d %H:%M:%S"),
            "username":  username,
            "action":    action,
            "details":   details,
        })
    except Exception:
        pass  # Không để lỗi audit làm hỏng luồng chính


# ── User Management ───────────────────────────────────────────────────────────

def get_users() -> pd.DataFrame:
    """Đọc danh sách user từ sheet 'users' (không cache để luôn mới nhất)."""
    try:
        ws = _get_worksheet("users")
        records = ws.get_all_records(expected_headers=[])
        return pd.DataFrame(records)
    except Exception as exc:
        st.error(f"Lỗi khi đọc danh sách user: {exc}")
        return pd.DataFrame()


def find_user_row(username: str) -> Optional[int]:
    """Tìm chỉ số dòng (1-indexed) của user trong sheet 'users'. Trả về None nếu không tìm thấy."""
    try:
        ws = _get_worksheet("users")
        cell = ws.find(username, in_column=1)  # cột 1 = username
        return cell.row if cell else None
    except Exception:
        return None
