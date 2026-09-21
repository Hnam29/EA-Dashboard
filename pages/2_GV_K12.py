"""
Trang GV-K12 – Danh sách Giáo viên K12 toàn quốc.

Cột Google Sheet: Sở GD, ID, Tên, Email, SĐT, Trường, Phòng GD
"""

import io
import streamlit as st
import pandas as pd
from datetime import datetime

from auth.login   import require_auth, get_current_user, get_current_role, logout
from auth.roles   import has_permission, get_role_label, get_role_color
from services.gsheet import (
    read_sheet_as_df, append_row, update_row_by_index,
    delete_row_by_index, export_df_to_new_sheet, log_action,
)
from components.ui import (
    inject_css, render_page_header, render_user_card, section_header,
    metrics_row,
)

# ── Cấu hình trang ────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="GV-K12 – EA Dashboard",
    page_icon="👨‍🏫",
    layout="wide",
    initial_sidebar_state="expanded",
)

require_auth()
inject_css()

user  = get_current_user()
role  = get_current_role()
color = get_role_color(role)
uname = user.get("username", "?")

# ── Sheet columns ──────────────────────────────────────────────────────────────
SHEET_NAME   = "Teacher_K12"
COL_SO_GD    = "Sở GD"
COL_ID       = "ID"
COL_TEN      = "Tên"
COL_EMAIL    = "Email"
COL_SDT      = "SĐT"
COL_TRUONG   = "Trường"
COL_PHONG_GD = "Phòng GD"

ALL_COLUMNS = [COL_SO_GD, COL_ID, COL_TEN, COL_EMAIL, COL_SDT, COL_TRUONG, COL_PHONG_GD]

# ── Load data ──────────────────────────────────────────────────────────────────

@st.cache_data(ttl=300, show_spinner="Đang tải dữ liệu GV-K12...")
def load_data() -> pd.DataFrame:
    df = read_sheet_as_df(SHEET_NAME)
    for c in [COL_SO_GD, COL_TEN, COL_EMAIL, COL_SDT, COL_TRUONG, COL_PHONG_GD]:
        if c in df.columns:
            df[c] = df[c].astype(str).str.strip()
    return df


df_raw = load_data()

# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    render_user_card(
        full_name=user.get("full_name", uname),
        role=get_role_label(role),
        role_color=color,
    )
    if st.button("🚪 Đăng xuất", use_container_width=True, key="gv_logout"):
        logout(); st.rerun()
    st.divider()

    # ── Filter: Sở GD (checkbox list) ────────────────────────────────────────
    section_header("Filter theo Sở Giáo Dục")

    so_gd_list = sorted({v for v in df_raw.get(COL_SO_GD, pd.Series()).dropna().unique()
                          if v and v not in ("nan", "")})
    select_all = st.checkbox("☑ Chọn tất cả Sở GD", value=True, key="gv_all_so")
    if select_all:
        sel_so_gd = so_gd_list
    else:
        # Hiện checkbox list
        sel_so_gd = []
        with st.container(height=280):
            for s in so_gd_list:
                if st.checkbox(s, value=True, key=f"gv_so_{s}"):
                    sel_so_gd.append(s)

    st.divider()

    # ── Filter: Phòng GD, Trường, Tên, Email ─────────────────────────────────
    section_header("Tìm kiếm chi tiết")

    phong_opts = ["Tất cả"] + sorted({v for v in df_raw.get(COL_PHONG_GD, pd.Series()).dropna().unique()
                                       if v and v not in ("nan", "")})
    sel_phong = st.selectbox("Phòng GD", phong_opts, label_visibility="visible", key="gv_phong")

    truong_opts = ["Tất cả"] + sorted({v for v in df_raw.get(COL_TRUONG, pd.Series()).dropna().unique()
                                        if v and v not in ("nan", "")})
    sel_truong = st.selectbox("Trường", truong_opts, label_visibility="visible", key="gv_truong")

    search_ten   = st.text_input("Tên giáo viên", placeholder="Nhập tên...", key="gv_ten")
    search_email = st.text_input("Email", placeholder="Nhập email...", key="gv_email")

    if st.button("🔄 Làm mới cache", use_container_width=True, key="gv_refresh"):
        load_data.clear()
        st.rerun()

# ── Áp dụng filter ────────────────────────────────────────────────────────────
df = df_raw.copy()

if sel_so_gd and COL_SO_GD in df.columns:
    df = df[df[COL_SO_GD].isin(sel_so_gd)]
if sel_phong != "Tất cả" and COL_PHONG_GD in df.columns:
    df = df[df[COL_PHONG_GD] == sel_phong]
if sel_truong != "Tất cả" and COL_TRUONG in df.columns:
    df = df[df[COL_TRUONG] == sel_truong]
if search_ten and COL_TEN in df.columns:
    df = df[df[COL_TEN].str.contains(search_ten, case=False, na=False)]
if search_email and COL_EMAIL in df.columns:
    df = df[df[COL_EMAIL].str.contains(search_email, case=False, na=False)]

# ── Helper đếm non-empty ──────────────────────────────────────────────────────
def _count_nonempty(d: pd.DataFrame, col: str) -> int:
    if col not in d.columns:
        return 0
    return int(d[col].replace({"nan": "", "": pd.NA}).dropna().count())

# ── Header ────────────────────────────────────────────────────────────────────
render_page_header("GV – K12", "Danh sách Giáo viên K12 toàn quốc")

# ── Metrics (2 hàng: toàn bộ + đã lọc) ───────────────────────────────────────
all_so   = df_raw[COL_SO_GD].nunique()    if COL_SO_GD    in df_raw.columns else 0
all_phong= df_raw[COL_PHONG_GD].nunique() if COL_PHONG_GD in df_raw.columns else 0
all_email= _count_nonempty(df_raw, COL_EMAIL)
all_sdt  = _count_nonempty(df_raw, COL_SDT)

flt_so   = df[COL_SO_GD].nunique()    if COL_SO_GD    in df.columns else 0
flt_phong= df[COL_PHONG_GD].nunique() if COL_PHONG_GD in df.columns else 0
flt_email= _count_nonempty(df, COL_EMAIL)
flt_sdt  = _count_nonempty(df, COL_SDT)

metrics_row([
    ("Tổng số Sở GD",     all_so,    "🏛️", "Toàn bộ"),
    ("Tổng số Phòng GD",  all_phong, "🏫", "Toàn bộ"),
    ("Tổng Email",         all_email, "📧", "Toàn bộ"),
    ("Tổng SĐT",           all_sdt,   "📱", "Toàn bộ"),
])
st.markdown("<br>", unsafe_allow_html=True)
metrics_row([
    ("Sở GD (đã lọc)",    flt_so,    "🏛️", "Sau filter"),
    ("Phòng GD (đã lọc)", flt_phong, "🏫", "Sau filter"),
    ("Email (đã lọc)",     flt_email, "📧", "Sau filter"),
    ("SĐT (đã lọc)",       flt_sdt,   "📱", "Sau filter"),
])

st.markdown("<br>", unsafe_allow_html=True)
st.divider()

# ── Toolbar ───────────────────────────────────────────────────────────────────
section_header(f"📋 Danh sách Giáo viên K12 Toàn Quốc – {len(df):,} bản ghi")

btn_cols = st.columns([1, 1, 1, 5])
with btn_cols[0]:
    if has_permission(role, "can_create"):
        add_clicked = st.button("➕ Thêm", type="primary", use_container_width=True, key="gv_add_btn")
    else:
        add_clicked = False
with btn_cols[1]:
    if has_permission(role, "can_export") and not df.empty:
        buf = io.StringIO()
        df.to_csv(buf, index=False, encoding="utf-8-sig")
        st.download_button(
            "⬇️ Export",
            data=buf.getvalue().encode("utf-8-sig"),
            file_name=f"gv_k12_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
            mime="text/csv",
            use_container_width=True,
        )
with btn_cols[2]:
    if has_permission(role, "can_export") and not df.empty:
        if st.button("📤 → GSheet", use_container_width=True, key="gv_gsheet_export"):
            sheet_name = f"GV_K12_Export_{datetime.now().strftime('%d%m%Y_%H%M')}"
            if export_df_to_new_sheet(df, sheet_name):
                log_action(uname, "EXPORT", f"Export GV-K12 {len(df):,} bản ghi → '{sheet_name}'")
                st.success(f"Đã export sang sheet: **{sheet_name}**")

# ── Add record ────────────────────────────────────────────────────────────────
if add_clicked:
    st.session_state["gv_show_add"] = True

if st.session_state.get("gv_show_add"):
    with st.expander("➕ Thêm giáo viên mới", expanded=True):
        with st.form("gv_add_form", clear_on_submit=True):
            gc1, gc2 = st.columns(2)
            n_so    = gc1.text_input("Sở GD")
            n_id    = gc2.text_input("ID")
            n_ten   = gc1.text_input("Tên giáo viên")
            n_email = gc2.text_input("Email")
            n_sdt   = gc1.text_input("SĐT")
            n_truong= gc2.text_input("Trường")
            n_phong = gc1.text_input("Phòng GD")
            sub_add = st.form_submit_button("💾 Lưu", type="primary")
            can_add = st.form_submit_button("❌ Hủy")
            if sub_add:
                row_data = {
                    COL_SO_GD: n_so, COL_ID: n_id, COL_TEN: n_ten,
                    COL_EMAIL: n_email, COL_SDT: n_sdt,
                    COL_TRUONG: n_truong, COL_PHONG_GD: n_phong,
                }
                if append_row(SHEET_NAME, row_data):
                    log_action(uname, "CREATE", f"Thêm GV: {n_ten} – {n_truong}")
                    st.success("✅ Đã thêm giáo viên mới!")
                    st.session_state.pop("gv_show_add", None)
                    load_data.clear()
                    st.rerun()
            if can_add:
                st.session_state.pop("gv_show_add", None)
                st.rerun()

# ── Data Table ────────────────────────────────────────────────────────────────
if df.empty:
    st.info("Không tìm thấy dữ liệu phù hợp.")
else:
    # Thêm cột Index hiển thị
    df_display = df.reset_index(drop=True)
    df_display.index = df_display.index + 1

    col_cfg = {}
    if COL_EMAIL in df_display.columns:
        col_cfg[COL_EMAIL] = st.column_config.TextColumn("Email", width="medium")
    if COL_SDT in df_display.columns:
        col_cfg[COL_SDT] = st.column_config.TextColumn("SĐT", width="small")
    if COL_SO_GD in df_display.columns:
        col_cfg[COL_SO_GD] = st.column_config.TextColumn("Sở GD", width="large")
    if COL_PHONG_GD in df_display.columns:
        col_cfg[COL_PHONG_GD] = st.column_config.TextColumn("Phòng GD", width="large")

    st.dataframe(
        df_display,
        use_container_width=True,
        height=600,
        column_config=col_cfg,
    )

# ── Edit / Delete ─────────────────────────────────────────────────────────────
if has_permission(role, "can_update") and not df.empty:
    st.divider()
    section_header("✏️ Chỉnh sửa / Xóa bản ghi")
    with st.expander("Chỉnh sửa hoặc xóa (nhập số dòng thực tế trong Google Sheet)", expanded=False):
        row_num = st.number_input("Số dòng (từ 2)", min_value=2, step=1, value=2, key="gv_edit_row")
        action  = st.radio("Thao tác", ["Chỉnh sửa", "Xóa"], horizontal=True, key="gv_action")

        if action == "Xóa":
            if has_permission(role, "can_delete"):
                st.warning(f"⚠️ Xác nhận xóa dòng **{row_num}**?")
                if st.button("🗑️ Xác nhận xóa", type="primary", key="gv_del_btn"):
                    if delete_row_by_index(SHEET_NAME, int(row_num)):
                        log_action(uname, "DELETE", f"Xóa dòng {row_num} trong {SHEET_NAME}")
                        st.success(f"✅ Đã xóa dòng {row_num}")
                        load_data.clear()
                        st.rerun()
            else:
                st.error("Bạn không có quyền xóa.")
        else:
            with st.form("gv_edit_form"):
                ec1, ec2 = st.columns(2)
                e_so    = ec1.text_input("Sở GD")
                e_id    = ec2.text_input("ID")
                e_ten   = ec1.text_input("Tên")
                e_email = ec2.text_input("Email")
                e_sdt   = ec1.text_input("SĐT")
                e_truong= ec2.text_input("Trường")
                e_phong = ec1.text_input("Phòng GD")
                if st.form_submit_button("💾 Lưu thay đổi", type="primary"):
                    edit_data = {
                        COL_SO_GD: e_so, COL_ID: e_id, COL_TEN: e_ten,
                        COL_EMAIL: e_email, COL_SDT: e_sdt,
                        COL_TRUONG: e_truong, COL_PHONG_GD: e_phong,
                    }
                    if update_row_by_index(SHEET_NAME, int(row_num), edit_data):
                        log_action(uname, "UPDATE", f"Cập nhật dòng {row_num}: {e_ten}")
                        st.success(f"✅ Đã cập nhật dòng {row_num}")
                        load_data.clear()
                        st.rerun()
