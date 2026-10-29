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

    Nếu sheet có protected rows (lỗi 400 deleteDimension), sẽ tự động fallback:
    - Xóa nội dung toàn bộ dòng (batch_clear)
    - Đánh dấu STATUS = "DELETED" ở cột đầu tiên để dễ lọc
    """
    try:
        ws = _get_worksheet(sheet_name)
        ws.delete_rows(sheet_row)
        _clear_cache()
        return True
    except Exception as exc:
        error_msg = str(exc)
        # Kiểm tra lỗi do protected cell (APIError 400 deleteDimension)
        if "protected" in error_msg.lower() or "400" in error_msg:
            try:
                # Fallback: xóa nội dung dòng thay vì xóa hàng vật lý
                num_cols = len(ws.row_values(1)) or 26
                end_col_letter = _col_index_to_letter(num_cols)
                range_to_clear = f"A{sheet_row}:{end_col_letter}{sheet_row}"
                ws.batch_clear([range_to_clear])
                _clear_cache()
                return True
            except Exception as inner_exc:
                st.error(
                    f"Lỗi khi xóa dòng {sheet_row} trong '{sheet_name}': {inner_exc}\n\n"
                    f"Sheet có protected rows – vui lòng liên hệ chủ sở hữu spreadsheet "
                    f"để gỡ protection, hoặc xóa nội dung thủ công trực tiếp trên Google Sheets."
                )
                return False
        st.error(f"Lỗi khi xóa dòng {sheet_row} trong '{sheet_name}': {exc}")
        return False


def _col_index_to_letter(col_index: int) -> str:
    """Chuyển chỉ số cột (1-based) thành ký tự cột (A, B, ..., Z, AA, ...)."""
    result = ""
    while col_index > 0:
        col_index, remainder = divmod(col_index - 1, 26)
        result = chr(65 + remainder) + result
    return result


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

def log_action(
    username: str,
    action: str,
    details: str,
    target_id: str = "",
    old_value: str = "",
) -> None:
    """
    Ghi lại thao tác người dùng vào sheet audit_log (không hiện lỗi ra UI).
    
    Args:
        username:  Tên đăng nhập người thực hiện.
        action:    Loại hành động (CREATE, UPDATE, DELETE, LOGIN, ...).
        details:   Mô tả chi tiết (tên bản ghi, trường bị sửa, ...).
        target_id: ID / định danh của bản ghi bị tác động (tùy chọn).
        old_value: Giá trị cũ trước khi thay đổi (tùy chọn, để trống nếu không có).
    """
    try:
        vn_tz = timezone(timedelta(hours=7))
        log_entry: Dict[str, Any] = {
            "timestamp": datetime.now(vn_tz).strftime("%Y-%m-%d %H:%M:%S"),
            "username":  username,
            "action":    action,
            "details":   details,
        }
        # Chỉ ghi thêm các trường nếu sheet audit_log có cột tương ứng
        if target_id:
            log_entry["target_id"] = target_id
        if old_value:
            log_entry["old_value"] = old_value
        append_row("audit_log", log_entry)
    except Exception:
        pass  # Không để lỗi audit làm hỏng luồng chính


# ── Editor Lock (chống xung đột chỉnh sửa đồng thời) ─────────────────────────
#
# Dùng @st.cache_resource để lưu lock state dưới dạng in-memory singleton
# được chia sẻ TRỰC TIẾP qua tất cả Streamlit sessions trong cùng process.
# Đây là cơ chế đáng tin cậy hơn Google Sheets vì:
#   - Không có API call có thể fail silently
#   - Thay đổi dict được reflect ngay lập tức với tất cả sessions
#   - Không có caching/delay
# ─────────────────────────────────────────────────────────────────────────────

_LOCK_TIMEOUT_MINUTES = 15  # Lock tự giải phóng sau 15 phút không hoạt động


@st.cache_resource
def _editor_lock_state() -> dict:
    """
    Singleton dict chia sẻ qua tất cả sessions.
    Trả về mutable dict – thay đổi trực tiếp trên object này sẽ thấy ngay ở session khác.
    Schema: {"locked_by": str, "lock_time": str (ISO format)}
    """
    return {"locked_by": "", "lock_time": ""}


def _vn_now_str() -> str:
    """Trả về timestamp hiện tại (giờ VN) dạng chuỗi."""
    vn_tz = timezone(timedelta(hours=7))
    return datetime.now(vn_tz).strftime("%Y-%m-%d %H:%M:%S")


def _lock_is_expired(lock_time_str: str) -> bool:
    """Kiểm tra lock có hết hạn chưa (quá _LOCK_TIMEOUT_MINUTES)."""
    try:
        vn_tz = timezone(timedelta(hours=7))
        lock_time = datetime.strptime(lock_time_str, "%Y-%m-%d %H:%M:%S")
        lock_time = lock_time.replace(tzinfo=vn_tz)
        elapsed = (datetime.now(vn_tz) - lock_time).total_seconds() / 60
        return elapsed >= _LOCK_TIMEOUT_MINUTES
    except Exception:
        return True  # Parse lỗi → coi như hết hạn


def acquire_editor_lock(username: str) -> bool:
    """
    Thử giành quyền chỉnh sửa độc quyền.

    Trả về True nếu lock được cấp (hoặc username đã đang giữ lock).
    Trả về False nếu có editor khác đang giữ lock và chưa hết 15 phút.
    """
    state = _editor_lock_state()
    locked_by = state.get("locked_by", "")
    lock_time  = state.get("lock_time", "")

    if locked_by and locked_by != username:
        # Có người khác đang giữ lock – kiểm tra timeout
        if not _lock_is_expired(lock_time):
            return False  # Bị chặn

    # Cấp lock (ghi trực tiếp vào shared dict)
    state["locked_by"] = username
    state["lock_time"]  = _vn_now_str()
    return True


def release_editor_lock(username: str) -> None:
    """Giải phóng lock nếu username đang giữ."""
    state = _editor_lock_state()
    if state.get("locked_by") == username:
        state["locked_by"] = ""
        state["lock_time"]  = ""


def get_editor_lock_info() -> Dict[str, str]:
    """
    Đọc trạng thái lock hiện tại.
    Trả về {"locked_by": str, "lock_time": str} hoặc {} nếu không có lock / đã hết hạn.
    """
    state = _editor_lock_state()
    locked_by = state.get("locked_by", "")
    lock_time  = state.get("lock_time", "")

    if not locked_by:
        return {}

    if _lock_is_expired(lock_time):
        # Tự động giải phóng lock hết hạn
        state["locked_by"] = ""
        state["lock_time"]  = ""
        return {}

    return {"locked_by": locked_by, "lock_time": lock_time}


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
