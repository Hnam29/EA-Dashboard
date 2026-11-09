"""
Trang GV-K12 – Danh sách Giáo viên K12 toàn quốc.

Cột Google Sheet: Sở GD, ID, Tên, Email, SĐT, Trường, Phòng GD
"""

import io
import re
import unicodedata
from rapidfuzz import fuzz, process
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
# ── Loại trường & Cấp học (K12) – tra từ sheet Datawarehouse ─────────────────
COL_KHOI        = "Khối"
COL_LOAI_TRUONG = "Loại trường"
DW_SHEET_NAME   = "All_Businesses2"
DW_COL_TEN      = "Tên trường/công ty"
DW_COL_TINH     = "Tỉnh/TP"
MATCH_THRESHOLD = 90   # độ giống tối thiểu (%) khi ghép tên trường

CAP_HOC_PATTERNS = {
    "Tiểu học": r"tiểu học|\bth\b|cấp 1",
    "THCS":     r"thcs|trung học cơ sở|cấp 2",
    "THPT":     r"thpt|trung học phổ thông|cấp 3",
}

def _norm(s) -> str:
    return unicodedata.normalize("NFC", str(s)).strip().lower()

def _clean(v) -> str:
    v = str(v).strip()
    return "" if v.lower() == "nan" else v

def _strip_accents(s: str) -> str:
    s = unicodedata.normalize("NFD", s.replace("đ", "d"))
    return "".join(ch for ch in s if unicodedata.category(ch) != "Mn")

def _school_key(s) -> str:
    """Chuẩn hóa tên trường: thường hóa, bỏ 'Trường', thống nhất viết tắt, bỏ ký tự đặc biệt."""
    k = re.sub(r"^trường\s+", "", _norm(s))
    k = (k.replace("trung học cơ sở", "thcs")
          .replace("trung học phổ thông", "thpt")
          .replace("tiểu học", "th"))
    return re.sub(r"[^\w]+", " ", k).strip()

def _prov_key(s) -> str:
    """'Sở Giáo dục và Đào tạo Tỉnh Hưng Yên' / 'Hưng Yên' -> 'hung yen'."""
    k = _strip_accents(_norm(s))
    k = re.sub(r"^so giao duc va dao tao\s*", "", k)
    k = re.sub(r"^(tinh|thanh pho|tp\.?)\s+", "", k)
    return re.sub(r"\s+", " ", k).strip()

def _cap_sig(key: str) -> frozenset:
    """Tập cấp học nhận diện được từ tên trường – dùng để không ghép nhầm THCS với THPT."""
    return frozenset(lv for lv, pat in CAP_HOC_PATTERNS.items() if re.search(pat, key))

def _build_lookup() -> dict:
    """{(tỉnh, cấp): ({tên chuẩn hóa: [loại trường, khối]}, [danh sách tên])} từ các dòng K12."""
    dw = read_sheet_as_df(DW_SHEET_NAME, header_row=2)
    need = {"ID", DW_COL_TEN, DW_COL_TINH, COL_LOAI_TRUONG}
    if dw.empty or not need.issubset(dw.columns):
        return {}
    dw = dw[dw["ID"].astype(str).str.split("-").str[0].str.strip().str.upper() == "K12"]
    khoi = dw[COL_KHOI] if COL_KHOI in dw.columns else pd.Series("", index=dw.index)
    groups: dict = {}
    for ten, tinh, lt, kh in zip(dw[DW_COL_TEN], dw[DW_COL_TINH], dw[COL_LOAI_TRUONG], khoi):
        key = _school_key(ten)
        if not key:
            continue
        cur = groups.setdefault((_prov_key(tinh), _cap_sig(key)), {}).setdefault(key, ["", ""])
        cur[0] = cur[0] or _clean(lt)   # 1 trường có nhiều dòng → lấy giá trị không trống đầu tiên
        cur[1] = cur[1] or _clean(kh)
    return {k: (d, list(d)) for k, d in groups.items()}

def _match_school(truong, so_gd, groups) -> tuple:
    key = _school_key(truong)
    grp = groups.get((_prov_key(so_gd), _cap_sig(key)))
    if not key or not grp:
        return ("", "")
    d, choices = grp
    hit = process.extractOne(key, choices, scorer=fuzz.ratio, score_cutoff=MATCH_THRESHOLD)
    return tuple(d[hit[0]]) if hit else ("", "")

def match_cap_hoc(d: pd.DataFrame, levels: list) -> pd.Series:
    """True nếu dòng thuộc ít nhất một cấp học được chọn (ưu tiên cột Khối, fallback tên trường)."""
    ten = (d[COL_TRUONG].fillna("").astype(str).map(_norm)
           if COL_TRUONG in d.columns else pd.Series("", index=d.index))
    if COL_KHOI in d.columns:
        khoi = d[COL_KHOI].fillna("").astype(str).map(_norm).replace("nan", "")
        text = khoi.where(khoi != "", ten)
    else:
        text = ten
    mask = pd.Series(False, index=d.index)
    for lv in levels:
        mask |= text.str.contains(CAP_HOC_PATTERNS[lv], regex=True, na=False)
    return mask

# ── Load data ──────────────────────────────────────────────────────────────────

@st.cache_data(ttl=300, show_spinner="Đang tải dữ liệu GV-K12...")
def load_data() -> pd.DataFrame:
    df = read_sheet_as_df(SHEET_NAME)
    for c in [COL_SO_GD, COL_TEN, COL_EMAIL, COL_SDT, COL_TRUONG, COL_PHONG_GD]:
        if c in df.columns:
            df[c] = df[c].astype(str).str.strip()

    # Tra Loại trường + Khối từ Datawarehouse (khớp tên ≥ 90%, cùng tỉnh, cùng cấp)
    if not df.empty and COL_TRUONG in df.columns and COL_SO_GD in df.columns:
        groups = _build_lookup()
        pairs = df[[COL_TRUONG, COL_SO_GD]].drop_duplicates()
        res = {(t, s): _match_school(t, s, groups)
               for t, s in zip(pairs[COL_TRUONG], pairs[COL_SO_GD])}
        matched = [res[(t, s)] for t, s in zip(df[COL_TRUONG], df[COL_SO_GD])]
        df[COL_LOAI_TRUONG] = [m[0] for m in matched]
        df[COL_KHOI]        = [m[1] for m in matched]
    return df


df_raw = load_data()
# Tính số dòng thực tế trên Google Sheet:
# header_row=1 → 1 dòng header → dữ liệu bắt đầu từ sheet row 2
# df_raw.iloc[i] tương ứng với sheet row = i + 2
if not df_raw.empty:
    df_raw.insert(0, "Sheet Row #", range(2, 2 + len(df_raw)))


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

    section_header("Loại trường / Cấp học (K12)")
    loai_truong_opts = sorted({str(v) for v in df_raw.get(COL_LOAI_TRUONG, pd.Series()).dropna().unique()
                               if v and str(v).lower() != "nan" and str(v).strip() != ""})
    sel_loai_truong = st.multiselect("Loại trường (K12)", loai_truong_opts,
                                     placeholder="Tất cả", key="gv_loai_truong")
    sel_cap_hoc = st.multiselect("Cấp học (K12)", list(CAP_HOC_PATTERNS),
                                 placeholder="Tất cả", key="gv_cap_hoc")
    if COL_LOAI_TRUONG in df_raw.columns and not df_raw.empty:
        st.caption(f"Tra được Loại trường: {(df_raw[COL_LOAI_TRUONG] != '').mean():.0%} số dòng")

    # ── Filter: Sở GD ────────────────────────────────────────────────────────
    section_header("Filter theo Sở Giáo Dục")

    so_gd_list = sorted({v for v in df_raw.get(COL_SO_GD, pd.Series()).dropna().unique()
                          if v and v not in ("nan", "")})
    select_all = st.checkbox("☑ Chọn tất cả Sở GD", value=True, key="gv_all_so")
    if select_all:
        sel_so_gd = so_gd_list
    else:
        sel_so_gd = []
        with st.container(height=280):
            for s in so_gd_list:
                if st.checkbox(s, value=True, key=f"gv_so_{s}"):
                    sel_so_gd.append(s)

    st.divider()

    section_header("Tìm kiếm chi tiết")

    phong_opts = ["Tất cả"] + sorted({v for v in df_raw.get(COL_PHONG_GD, pd.Series()).dropna().unique()
                                       if v and v not in ("nan", "")})
    sel_phong = st.selectbox("Phòng GD", phong_opts, label_visibility="visible", key="gv_phong")

    truong_opts = ["Tất cả"] + sorted({v for v in df_raw.get(COL_TRUONG, pd.Series()).dropna().unique()
                                        if v and v not in ("nan", "")})
    sel_truong = st.selectbox("Trường", truong_opts, label_visibility="visible", key="gv_truong")

    search_ten   = st.text_input("Tên giáo viên", placeholder="Nhập tên...", key="gv_ten")
    search_email = st.text_input("Email", placeholder="Nhập email...", key="gv_email")
    only_with_email = st.checkbox("Chỉ hiển thị dòng có Email", key="gv_only_email")
    only_with_sdt   = st.checkbox("Chỉ hiển thị dòng có SĐT", key="gv_only_sdt")

    if st.button("🔄 Làm mới cache", use_container_width=True, key="gv_refresh"):
        load_data.clear()
        st.rerun()

_EMPTY_VALUES = {"", "nan", "none", "<na>", "null"}

def _has_value(s: pd.Series) -> pd.Series:
    """True where the cell has real content."""
    return ~s.astype(str).str.strip().str.lower().isin(_EMPTY_VALUES)

# ── Áp dụng filter ────────────────────────────────────────────────────────────
df = df_raw.copy()

if sel_so_gd and COL_SO_GD in df.columns:
    df = df[df[COL_SO_GD].isin(sel_so_gd)]
if sel_phong != "Tất cả" and COL_PHONG_GD in df.columns:
    df = df[df[COL_PHONG_GD] == sel_phong]
if sel_truong != "Tất cả" and COL_TRUONG in df.columns:
    if sel_loai_truong and COL_LOAI_TRUONG in df.columns:
        df = df[df[COL_LOAI_TRUONG].isin(sel_loai_truong)]
    if sel_cap_hoc:
        df = df[match_cap_hoc(df, sel_cap_hoc)]
if search_ten and COL_TEN in df.columns:
    df = df[df[COL_TEN].str.contains(search_ten, case=False, na=False)]
if search_email and COL_EMAIL in df.columns:
    df = df[df[COL_EMAIL].str.contains(search_email, case=False, na=False)]
if only_with_email and COL_EMAIL in df.columns:
    df = df[_has_value(df[COL_EMAIL])]
if only_with_sdt and COL_SDT in df.columns:
    df = df[_has_value(df[COL_SDT])]

# ── Helper đếm non-empty ──────────────────────────────────────────────────────
def _count_nonempty(d: pd.DataFrame, col: str) -> int:
    if col not in d.columns:
        return 0
    return int(_has_value(d[col]).sum())

# ── Header ────────────────────────────────────────────────────────────────────
render_page_header("GV – K12", "Danh sách Giáo viên K12 toàn quốc")

# ── Metrics ───────────────────────────────────────────────────────────────────
all_so    = df_raw[COL_SO_GD].nunique()    if COL_SO_GD    in df_raw.columns else 0
all_phong = df_raw[COL_PHONG_GD].nunique() if COL_PHONG_GD in df_raw.columns else 0
all_email = _count_nonempty(df_raw, COL_EMAIL)
all_sdt   = _count_nonempty(df_raw, COL_SDT)

flt_so    = df[COL_SO_GD].nunique()    if COL_SO_GD    in df.columns else 0
flt_phong = df[COL_PHONG_GD].nunique() if COL_PHONG_GD in df.columns else 0
flt_email = _count_nonempty(df, COL_EMAIL)
flt_sdt   = _count_nonempty(df, COL_SDT)

metrics_row([
    ("Tổng số Sở GD",    flt_so,    "🏛️", f"/ {all_so:,} toàn bộ"),
    ("Tổng số Phòng GD", flt_phong, "🏫", f"/ {all_phong:,} toàn bộ"),
    ("Tổng Email",       flt_email, "📧", f"/ {all_email:,} toàn bộ"),
    ("Tổng SĐT",         flt_sdt,   "📱", f"/ {all_sdt:,} toàn bộ"),
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
        with st.popover("⬇️ Export Excel"):
            st.markdown("**Chọn cột để export**")
            cols_to_export = st.multiselect(
                "Các cột",
                options=df.columns.tolist(),
                default=df.columns.tolist(),
                key="gv_export_cols"
            )
            if cols_to_export:
                df_export = df[cols_to_export].copy()
                df_export = df_export.replace(r'[\x00-\x08\x0b-\x0c\x0e-\x1f]', '', regex=True)
                buf = io.BytesIO()
                with pd.ExcelWriter(buf, engine='openpyxl') as writer:
                    df_export.to_excel(writer, index=False, sheet_name='Data')
                st.download_button(
                    "Tải xuống Excel",
                    data=buf.getvalue(),
                    file_name=f"gv_k12_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
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
    col_cfg = {}
    if "Sheet Row #" in df.columns:
        col_cfg["Sheet Row #"] = st.column_config.NumberColumn(
            "Sheet Row #",
            help="Số dòng thực tế trên Google Sheet – dùng số này để chỉnh sửa/xóa",
            width="small",
        )
    if COL_EMAIL in df.columns:
        col_cfg[COL_EMAIL] = st.column_config.TextColumn("Email", width="medium")
    if COL_SDT in df.columns:
        col_cfg[COL_SDT] = st.column_config.TextColumn("SĐT", width="small")
    if COL_SO_GD in df.columns:
        col_cfg[COL_SO_GD] = st.column_config.TextColumn("Sở GD", width="large")
    if COL_PHONG_GD in df.columns:
        col_cfg[COL_PHONG_GD] = st.column_config.TextColumn("Phòng GD", width="large")

    st.caption("💡 Cột **Sheet Row #** là số dòng thực tế trên Google Sheet – dùng để chỉnh sửa/xóa bên dưới.")
    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        height=600,
        column_config=col_cfg,
    )

# ── Edit / Delete ─────────────────────────────────────────────────────────────
if has_permission(role, "can_update") and not df.empty:
    st.divider()
    section_header("✏️ Chỉnh sửa / Xóa bản ghi")

    with st.expander("Chỉnh sửa hoặc xóa (nhập số dòng thực tế trong Google Sheet)", expanded=False):

        # ── Áp dụng reset sau khi xóa – PHẢI làm TRƯỚC khi render widget ──────
        if st.session_state.pop("gv_reset_row", False):
            st.session_state["gv_edit_row"] = 2
        if st.session_state.pop("gv_reset_action", False):
            st.session_state["gv_action"] = "Chỉnh sửa"

        # ── Thông báo xóa thành công (hiện sau rerun, TRƯỚC khi render form) ──
        just_deleted = False
        if st.session_state.get("gv_delete_success_msg"):
            st.success(st.session_state.pop("gv_delete_success_msg"))
            just_deleted = True

        row_num = st.number_input(
            "Số dòng trên Google Sheet (xem cột **Sheet Row #** trong bảng để biết số chính xác)",
            min_value=2, step=1, value=2, key="gv_edit_row"
        )

        # Xem dữ liệu dòng hiện tại – header_row=1 → iloc_idx = row_num - 2
        sheet_iloc_idx = int(row_num) - 2
        if 0 <= sheet_iloc_idx < len(df_raw):
            current_row = df_raw.iloc[sheet_iloc_idx]
            with st.expander("👁 Xem dữ liệu hiện tại của dòng này", expanded=False):
                st.dataframe(current_row.to_frame().T, use_container_width=True, hide_index=True)

        action = st.radio("Thao tác", ["Chỉnh sửa", "Xóa"], horizontal=True, key="gv_action")

        # Vừa xóa xong → chỉ hiện thông báo, KHÔNG render form bên dưới
        if just_deleted:
            st.stop()

        # ── Xóa ───────────────────────────────────────────────────────────────
        if action == "Xóa":
            if has_permission(role, "can_delete"):
                del_name   = ""
                del_truong = ""
                del_email  = ""
                iloc_idx   = int(row_num) - 2
                if 0 <= iloc_idx < len(df_raw):
                    del_row    = df_raw.iloc[iloc_idx]
                    del_name   = str(del_row.get(COL_TEN, ""))
                    del_truong = str(del_row.get(COL_TRUONG, ""))
                    del_email  = str(del_row.get(COL_EMAIL, ""))
                st.warning(
                    f"⚠️ Xác nhận xóa dòng **{row_num}** khỏi sheet `{SHEET_NAME}`?  \n"
                    f"Tên GV: **{del_name}** | Trường: {del_truong} | Email: {del_email}"
                )
                if st.button("🗑️ Xác nhận xóa", type="primary", key="gv_del_btn"):
                    if delete_row_by_index(SHEET_NAME, int(row_num)):
                        log_action(
                            uname, "DELETE",
                            f"Xóa dòng {row_num} | Sheet: {SHEET_NAME} | "
                            f"Tên GV: {del_name} | Trường: {del_truong} | Email: {del_email}",
                            target_id=del_name,
                            old_value=f"Tên={del_name}; Trường={del_truong}; Email={del_email}",
                        )
                        st.session_state["gv_delete_success_msg"] = (
                            f"✅ Đã xóa dòng {row_num} | Tên GV: **{del_name}** | Trường: {del_truong} | Email: {del_email}"
                        )
                        st.session_state["gv_reset_action"] = True
                        st.session_state["gv_reset_row"]   = True
                        load_data.clear()
                        st.rerun()
            else:
                st.error("Bạn không có quyền xóa.")

        # ── Chỉnh sửa ─────────────────────────────────────────────────────────
        else:
            prefill: dict = {}
            iloc_idx = int(row_num) - 2
            if 0 <= iloc_idx < len(df_raw):
                prefill = df_raw.iloc[iloc_idx].to_dict()

            with st.form("gv_edit_form"):
                ec1, ec2 = st.columns(2)
                e_so    = ec1.text_input("Sở GD",   value=str(prefill.get(COL_SO_GD, "")))
                e_id    = ec2.text_input("ID",       value=str(prefill.get(COL_ID, "")))
                e_ten   = ec1.text_input("Tên",      value=str(prefill.get(COL_TEN, "")))
                e_email = ec2.text_input("Email",    value=str(prefill.get(COL_EMAIL, "")))
                e_sdt   = ec1.text_input("SĐT",      value=str(prefill.get(COL_SDT, "")))
                e_truong= ec2.text_input("Trường",   value=str(prefill.get(COL_TRUONG, "")))
                e_phong = ec1.text_input("Phòng GD", value=str(prefill.get(COL_PHONG_GD, "")))
                if st.form_submit_button("💾 Lưu thay đổi", type="primary"):
                    old_ten   = str(prefill.get(COL_TEN, ""))
                    old_email = str(prefill.get(COL_EMAIL, ""))
                    edit_data = {
                        COL_SO_GD: e_so, COL_ID: e_id, COL_TEN: e_ten,
                        COL_EMAIL: e_email, COL_SDT: e_sdt,
                        COL_TRUONG: e_truong, COL_PHONG_GD: e_phong,
                    }
                    if update_row_by_index(SHEET_NAME, int(row_num), edit_data):
                        log_action(
                            uname, "UPDATE",
                            f"Cập nhật dòng {row_num} | Sheet: {SHEET_NAME} | "
                            f"Tên mới: {e_ten} | Trường: {e_truong} | Email mới: {e_email}",
                            target_id=e_id,
                            old_value=f"Tên={old_ten}; Email={old_email}",
                        )
                        st.success(f"✅ Đã cập nhật dòng {row_num} ({e_ten})")
                        load_data.clear()
                        st.rerun()
