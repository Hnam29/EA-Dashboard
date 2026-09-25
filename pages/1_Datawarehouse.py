"""
Trang Datawarehouse – Tổng hợp dữ liệu khách hàng EdTech Agency.

Cột Google Sheet: STATUS, ID, Tên trường/công ty, Người phụ trách/đại diện,
                  Nhóm, Chức vụ, Email, Tình trạng Email, SĐT, Website,
                  Địa chỉ, Loại hình CSĐT, Loại trường, Khối, Quận, Tỉnh/TP
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
    metrics_row, chart_bar_h, chart_donut, chart_funnel,
)

# ── Cấu hình trang ────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Datawarehouse – EA Dashboard",
    page_icon="📊",
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
SHEET_NAME = "All_Businesses2"
COL_STATUS  = "STATUS"
COL_ID      = "ID"
COL_TEN     = "Tên trường/công ty"
COL_NGUOI   = "Người phụ trách/đại diện"
COL_NHOM    = "Nhóm"
COL_CHUCVU  = "Chức vụ"
COL_EMAIL   = "Email"
COL_EMAIL_STATUS = "Tình trạng Email"
COL_SDT     = "SĐT"
COL_WEBSITE = "Website"
COL_DIACHI  = "Địa chỉ"
COL_LOAI_HINH = "Loại hình CSĐT"
COL_LOAI_TRUONG = "Loại trường"
COL_KHOI    = "Khối"
COL_QUAN    = "Quận"
COL_TINH    = "Tỉnh/TP"

ALL_COLUMNS = [
    COL_STATUS, COL_ID, COL_TEN, COL_NGUOI, COL_NHOM, COL_CHUCVU,
    COL_EMAIL, COL_EMAIL_STATUS, COL_SDT, COL_WEBSITE, COL_DIACHI,
    COL_LOAI_HINH, COL_LOAI_TRUONG, COL_KHOI, COL_QUAN, COL_TINH,
]

# ── Load data ──────────────────────────────────────────────────────────────────

@st.cache_data(ttl=300, show_spinner="Đang tải dữ liệu Datawarehouse...")
def load_data() -> pd.DataFrame:
    # All_Businesses2 có 2 dòng header: dòng 1 = nhóm (GENERAL/SCHOOL...),
    # dòng 2 = tên cột thực tế – nên dùng header_row=2
    df = read_sheet_as_df(SHEET_NAME, header_row=2)
    # Đảm bảo các cột string
    for c in [COL_STATUS, COL_ID, COL_TEN, COL_NHOM, COL_CHUCVU,
              COL_EMAIL, COL_EMAIL_STATUS, COL_TINH]:
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
    if st.button("🚪 Đăng xuất", use_container_width=True, key="dw_logout"):
        logout(); st.rerun()
    st.divider()

    # ── Filters ──────────────────────────────────────────────────────────────
    section_header("Trạng thái")
    unique_statuses = sorted({
        str(v).strip().upper() for v in df_raw.get(COL_STATUS, pd.Series()).dropna().unique()
        if v and str(v).strip().lower() != "nan" and str(v).strip().upper() not in ["INACTIVE", "CONSIDER"]
    })
    if not unique_statuses:
        unique_statuses = ["OK", "REMOVE"]
    status_opts = ["Tất cả"] + unique_statuses
    sel_status = st.selectbox("STATUS", status_opts, label_visibility="collapsed", key="dw_status")

    section_header("ID / Phân khúc")
    with st.expander("ℹ️ Ý nghĩa các mã ID", expanded=False):
        st.markdown("""
        - **EDVN**: doanh nghiệp Edtech tại Việt Nam
        - **EDQT**: doanh nghiệp Edtech ở nước ngoài
        - **FLC**: trung tâm đào tạo ngoại ngữ
        - **SC**: trung tâm đào tạo kỹ năng
        - **ASC**: hiệp hội, viện
        - **PRS**: tạp chí, toà soạn (báo chí)
        - **GOV**: các cơ quan thuộc chính phủ
        - **OCP**: doanh nghiệp KHÔNG thuộc mảng Edtech
        - **K12**: trường từ tiểu học đến THPT
        - **HE**: trường cao đẳng, đại học
        - **KD**: trường mầm non
        - **AC**: đơn vị, trung tâm tư vấn (du học)
        - **FU**: các quỹ, đơn vị đầu tư
        """)
    id_opts = sorted({str(v).split('-')[0] for v in df_raw.get(COL_ID, pd.Series()).dropna().unique() if v and str(v) != "nan"})
    sel_ids = st.multiselect("ID", id_opts, placeholder="Tất cả", key="dw_id")

    sel_loai_truong = []
    if "K12" in sel_ids:
        loai_truong_opts = sorted({str(v) for v in df_raw.get(COL_LOAI_TRUONG, pd.Series()).dropna().unique() if v and str(v).lower() != "nan" and str(v).strip() != ""})
        sel_loai_truong = st.multiselect("Loại trường (K12)", loai_truong_opts, placeholder="Tất cả", key="dw_loai_truong")

    section_header("Nhóm (Dự án)")
    nhom_opts = sorted({v for v in df_raw.get(COL_NHOM, pd.Series()).dropna().unique() if v and str(v) != "nan"})
    sel_nhom = st.multiselect("Nhóm", nhom_opts, placeholder="Tất cả", key="dw_nhom")

    section_header("Tỉnh/TP")
    tinh_opts = ["Tất cả"] + sorted({v for v in df_raw.get(COL_TINH, pd.Series()).dropna().unique() if v and v != "nan" and str(v).strip() != "0"})
    sel_tinh = st.selectbox("Tỉnh/TP", tinh_opts, label_visibility="collapsed", key="dw_tinh")

    section_header("Tìm kiếm")
    search_ten   = st.text_input("Tên trường/công ty", placeholder="Nhập tên...", key="dw_ten")
    search_email = st.text_input("Email", placeholder="Nhập email...", key="dw_email")
    only_with_email = st.checkbox("Chỉ hiển thị dòng có Email", key="dw_only_email")

    if st.button("🔄 Làm mới cache", use_container_width=True, key="dw_refresh"):
        load_data.clear()
        st.rerun()

# ── Áp dụng filter ────────────────────────────────────────────────────────────
df = df_raw.copy()

if sel_status != "Tất cả" and COL_STATUS in df.columns:
    df = df[df[COL_STATUS].str.upper() == sel_status]
if sel_ids and COL_ID in df.columns:
    df = df[df[COL_ID].apply(lambda x: str(x).split('-')[0]).isin(sel_ids)]
if sel_loai_truong and COL_LOAI_TRUONG in df.columns:
    df = df[df[COL_LOAI_TRUONG].isin(sel_loai_truong)]
if sel_nhom and COL_NHOM in df.columns:
    df = df[df[COL_NHOM].isin(sel_nhom)]
if sel_tinh != "Tất cả" and COL_TINH in df.columns:
    df = df[df[COL_TINH] == sel_tinh]
if search_ten and COL_TEN in df.columns:
    df = df[df[COL_TEN].str.contains(search_ten, case=False, na=False)]
if search_email and COL_EMAIL in df.columns:
    df = df[df[COL_EMAIL].str.contains(search_email, case=False, na=False)]
if only_with_email and COL_EMAIL in df.columns:
    df = df[(df[COL_EMAIL] != "") & (df[COL_EMAIL].str.lower() != "nan")]

# ── Header ────────────────────────────────────────────────────────────────────
render_page_header("DATAWAREHOUSE", "Tổng hợp dữ liệu khách hàng EdTech Agency")

# ── Metrics ───────────────────────────────────────────────────────────────────
total_all = len(df_raw)
biz_all   = df_raw[COL_TEN].nunique() if COL_TEN in df_raw.columns else 0
total_flt = len(df)
biz_flt   = df[COL_TEN].nunique() if COL_TEN in df.columns else 0

metrics_row([
    ("Tổng số Data",             total_all, "🗄️",  "Toàn bộ"),
    ("Tổng số Business",         biz_all,   "🏢",  "Toàn bộ"),
    ("Data (đã lọc)",            total_flt, "📋",  "Sau filter"),
    ("Business (đã lọc)",        biz_flt,   "🔍",  "Sau filter"),
])

st.markdown("<br>", unsafe_allow_html=True)

# ── Charts ────────────────────────────────────────────────────────────────────
c1, c2, c3 = st.columns([2.2, 1.6, 1.2])
with c1:
    chart_bar_h(df, COL_NHOM,   "📊 Số lượng data theo dự án (Nhóm)", max_rows=15)
with c2:
    chart_donut(df, COL_ID,     "🔵 Top 6 ID theo số lượng data",     max_slices=6)
with c3:
    chart_funnel(df, COL_CHUCVU, "📊 Tỷ lệ các loại chức vụ")

st.divider()

# ── Toolbar ───────────────────────────────────────────────────────────────────
section_header(f"📋 Bảng dữ liệu khách hàng – {len(df):,} bản ghi")

btn_cols = st.columns([1, 1, 1, 5])
with btn_cols[0]:
    if has_permission(role, "can_create"):
        add_clicked = st.button("➕ Thêm", type="primary", use_container_width=True, key="dw_add_btn")
    else:
        add_clicked = False

with btn_cols[1]:
    if has_permission(role, "can_export") and not df.empty:
        with st.popover("⬇️ Export Excel"):
            st.markdown("**Chọn cột để export**")
            cols_to_export = st.multiselect(
                "Các cột",
                options=df.columns.tolist(),
                default=df.columns.tolist(),
                key="dw_export_cols"
            )
            if cols_to_export:
                df_export = df[cols_to_export].copy()
                # Remove illegal characters for Excel
                df_export = df_export.replace(r'[\x00-\x08\x0b-\x0c\x0e-\x1f]', '', regex=True)
                
                buf = io.BytesIO()
                with pd.ExcelWriter(buf, engine='openpyxl') as writer:
                    df_export.to_excel(writer, index=False, sheet_name='Data')
                
                st.download_button(
                    "Tải xuống Excel",
                    data=buf.getvalue(),
                    file_name=f"datawarehouse_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                )

with btn_cols[2]:
    if has_permission(role, "can_export") and not df.empty:
        if st.button("📤 → GSheet", use_container_width=True, key="dw_gsheet_export"):
            sheet_name = f"Export_{datetime.now().strftime('%d%m%Y_%H%M')}"
            if export_df_to_new_sheet(df, sheet_name):
                log_action(uname, "EXPORT", f"Export {len(df):,} bản ghi → sheet '{sheet_name}'")
                st.success(f"Đã export sang sheet: **{sheet_name}**")

# ── Add record dialog ─────────────────────────────────────────────────────────
if add_clicked:
    st.session_state["dw_show_add"] = True

if st.session_state.get("dw_show_add"):
    with st.expander("➕ Thêm bản ghi mới", expanded=True):
        with st.form("dw_add_form", clear_on_submit=True):
            fc1, fc2 = st.columns(2)
            new_status  = fc1.selectbox("STATUS", unique_statuses)
            new_id      = fc2.text_input("ID (Phân khúc)")
            new_ten     = fc1.text_input("Tên trường/công ty")
            new_nguoi   = fc2.text_input("Người phụ trách/đại diện")
            new_nhom    = fc1.text_input("Nhóm (Dự án)")
            new_cv      = fc2.text_input("Chức vụ")
            new_email   = fc1.text_input("Email")
            new_es      = fc2.text_input("Tình trạng Email")
            new_sdt     = fc1.text_input("SĐT")
            new_web     = fc2.text_input("Website")
            new_diachi  = fc1.text_input("Địa chỉ")
            new_lh      = fc2.text_input("Loại hình CSĐT")
            new_lt      = fc1.text_input("Loại trường")
            new_khoi    = fc2.text_input("Khối")
            new_quan    = fc1.text_input("Quận")
            new_tinh    = fc2.text_input("Tỉnh/TP")

            sub_add = st.form_submit_button("💾 Lưu", type="primary")
            can_add = st.form_submit_button("❌ Hủy")

            if sub_add:
                row_data = {
                    COL_STATUS: new_status, COL_ID: new_id,
                    COL_TEN: new_ten, COL_NGUOI: new_nguoi, COL_NHOM: new_nhom,
                    COL_CHUCVU: new_cv, COL_EMAIL: new_email,
                    COL_EMAIL_STATUS: new_es, COL_SDT: new_sdt,
                    COL_WEBSITE: new_web, COL_DIACHI: new_diachi,
                    COL_LOAI_HINH: new_lh, COL_LOAI_TRUONG: new_lt,
                    COL_KHOI: new_khoi, COL_QUAN: new_quan, COL_TINH: new_tinh,
                }
                if append_row(SHEET_NAME, row_data):
                    log_action(uname, "CREATE", f"Thêm bản ghi: {new_ten} – {new_email}")
                    st.success("✅ Đã thêm bản ghi mới!")
                    st.session_state.pop("dw_show_add", None)
                    load_data.clear()
                    st.rerun()
            if can_add:
                st.session_state.pop("dw_show_add", None)
                st.rerun()

# ── Data Table ────────────────────────────────────────────────────────────────
if df.empty:
    st.info("Không có dữ liệu phù hợp với bộ lọc hiện tại.")
else:
    # Column config cho dataframe
    col_cfg = {}
    if COL_EMAIL in df.columns:
        col_cfg[COL_EMAIL] = st.column_config.TextColumn("Email", width="medium")
    if COL_WEBSITE in df.columns:
        col_cfg[COL_WEBSITE] = st.column_config.LinkColumn("Website", width="small")
    if COL_SDT in df.columns:
        col_cfg[COL_SDT] = st.column_config.TextColumn("SĐT", width="small")
    if COL_STATUS in df.columns:
        col_cfg[COL_STATUS] = st.column_config.TextColumn("Status", width="small")

    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        height=520,
        column_config=col_cfg,
    )

# ── Edit / Delete (Admin/Editor) ───────────────────────────────────────────────
if has_permission(role, "can_update") and not df.empty:
    st.divider()
    section_header("✏️ Chỉnh sửa / Xóa bản ghi")

    with st.expander("Chỉnh sửa hoặc xóa bản ghi (nhập số thứ tự dòng trong Google Sheet)", expanded=False):
        row_num = st.number_input(
            "Số thứ tự dòng trong Sheet (bắt đầu từ 2, dòng 1 là tiêu đề)",
            min_value=2, step=1, value=2, key="dw_edit_row",
        )
        action = st.radio("Thao tác", ["Chỉnh sửa", "Xóa"], horizontal=True, key="dw_action")

        if action == "Xóa":
            if has_permission(role, "can_delete"):
                st.warning(f"⚠️ Xác nhận xóa dòng **{row_num}** khỏi sheet `{SHEET_NAME}`?")
                if st.button("🗑️ Xác nhận xóa", type="primary", key="dw_del_btn"):
                    if delete_row_by_index(SHEET_NAME, int(row_num)):
                        log_action(uname, "DELETE", f"Xóa dòng {row_num} trong {SHEET_NAME}")
                        st.success(f"✅ Đã xóa dòng {row_num}")
                        load_data.clear()
                        st.rerun()
            else:
                st.error("Bạn không có quyền xóa dữ liệu.")
        else:
            st.info("Nhập dữ liệu mới rồi nhấn Lưu để cập nhật dòng đã chọn.")
            with st.form("dw_edit_form"):
                ec1, ec2 = st.columns(2)
                e_status = ec1.selectbox("STATUS", unique_statuses)
                e_id     = ec2.text_input("ID")
                e_ten    = ec1.text_input("Tên trường/công ty")
                e_nguoi  = ec2.text_input("Người phụ trách/đại diện")
                e_nhom   = ec1.text_input("Nhóm")
                e_cv     = ec2.text_input("Chức vụ")
                e_email  = ec1.text_input("Email")
                e_es     = ec2.text_input("Tình trạng Email")
                e_sdt    = ec1.text_input("SĐT")
                e_web    = ec2.text_input("Website")
                e_diachi = ec1.text_input("Địa chỉ")
                e_lh     = ec2.text_input("Loại hình CSĐT")
                e_lt     = ec1.text_input("Loại trường")
                e_khoi   = ec2.text_input("Khối")
                e_quan   = ec1.text_input("Quận")
                e_tinh   = ec2.text_input("Tỉnh/TP")

                if st.form_submit_button("💾 Lưu thay đổi", type="primary"):
                    edit_data = {
                        COL_STATUS: e_status, COL_ID: e_id, COL_TEN: e_ten,
                        COL_NGUOI: e_nguoi, COL_NHOM: e_nhom, COL_CHUCVU: e_cv,
                        COL_EMAIL: e_email, COL_EMAIL_STATUS: e_es, COL_SDT: e_sdt,
                        COL_WEBSITE: e_web, COL_DIACHI: e_diachi, COL_LOAI_HINH: e_lh,
                        COL_LOAI_TRUONG: e_lt, COL_KHOI: e_khoi, COL_QUAN: e_quan,
                        COL_TINH: e_tinh,
                    }
                    if update_row_by_index(SHEET_NAME, int(row_num), edit_data):
                        log_action(uname, "UPDATE", f"Cập nhật dòng {row_num}: {e_ten}")
                        st.success(f"✅ Đã cập nhật dòng {row_num}")
                        load_data.clear()
                        st.rerun()
