"""
Trang Admin – Quản lý tài khoản và xem audit log.
Chỉ Admin mới có quyền truy cập trang này.

Sheet 'users' cần có cột: username, password_hash, full_name, role, is_active
Sheet 'audit_log' cần có cột: timestamp, username, action, details
"""

import streamlit as st
import bcrypt
import pandas as pd
from datetime import datetime

from auth.login   import require_auth, get_current_user, get_current_role, logout
from auth.roles   import has_permission, get_role_label, get_role_color, Role
from services.gsheet import (
    get_users, append_row, update_row_by_index, read_sheet_as_df,
    find_user_row, log_action,
)
from components.ui import (
    inject_css, render_page_header, render_user_card, section_header, metrics_row,
    render_sidebar_toggle,
)

# ── Cấu hình trang ────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Admin – EA Dashboard",
    page_icon="⚙️",
    layout="wide",
    initial_sidebar_state="expanded",
)

require_auth()
inject_css()
render_sidebar_toggle()

user  = get_current_user()
role  = get_current_role()
uname = user.get("username", "?")

# Chỉ Admin mới vào được
if role != "admin":
    st.error("⛔ Bạn không có quyền truy cập trang này. Chỉ Admin mới được phép.")
    st.stop()

color = get_role_color(role)

# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    render_user_card(
        full_name=user.get("full_name", uname),
        role=get_role_label(role),
        role_color=color,
    )
    if st.button("🚪 Đăng xuất", use_container_width=True, key="adm_logout"):
        logout(); st.rerun()

# ── Header ────────────────────────────────────────────────────────────────────
render_page_header("QUẢN TRỊ HỆ THỐNG", "Quản lý tài khoản và nhật ký hoạt động")

# ── Tab layout ────────────────────────────────────────────────────────────────
tab_users, tab_add, tab_pwd, tab_log = st.tabs([
    "👥 Danh sách tài khoản",
    "➕ Thêm tài khoản",
    "🔑 Đổi mật khẩu",
    "📜 Audit Log",
])

# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 – DANH SÁCH TÀI KHOẢN
# ══════════════════════════════════════════════════════════════════════════════
with tab_users:
    section_header("Danh sách tài khoản hệ thống")

    df_users = get_users()

    if df_users.empty:
        st.warning("Chưa có tài khoản nào. Dùng tab 'Thêm tài khoản' để tạo tài khoản đầu tiên.")
    else:
        # Ẩn password_hash
        display_cols = [c for c in df_users.columns if c != "password_hash"]
        df_show = df_users[display_cols].copy()

        # Metrics
        total  = len(df_show)
        active = int(df_show["is_active"].astype(str).str.upper().isin(["TRUE", "1", "YES"]).sum()) if "is_active" in df_show.columns else total
        admins = int((df_show["role"].str.lower() == "admin").sum())  if "role" in df_show.columns else 0
        editors= int((df_show["role"].str.lower() == "editor").sum()) if "role" in df_show.columns else 0

        metrics_row([
            ("Tổng tài khoản",  total,   "👥", ""),
            ("Đang hoạt động",  active,  "✅", ""),
            ("Admin",           admins,  "🔴", ""),
            ("Editor",          editors, "🟡", ""),
        ])
        st.markdown("<br>", unsafe_allow_html=True)
        st.dataframe(df_show, use_container_width=True, hide_index=True, height=400)

    # Kích hoạt / Vô hiệu hóa tài khoản
    st.divider()
    section_header("Thay đổi trạng thái / Đổi role tài khoản")
    with st.form("adm_toggle_form"):
        col1, col2, col3 = st.columns(3)
        t_username = col1.text_input("Username cần thay đổi")
        t_role     = col2.selectbox("Role mới", [r.value for r in Role])
        t_active   = col3.selectbox("Trạng thái", ["TRUE", "FALSE"])
        if st.form_submit_button("💾 Cập nhật", type="primary"):
            if not t_username:
                st.warning("Vui lòng nhập username.")
            else:
                row_idx = find_user_row(t_username)
                if row_idx:
                    df_u = get_users()
                    matched = df_u[df_u["username"].str.lower() == t_username.lower()]
                    if not matched.empty:
                        row_data = matched.iloc[0].to_dict()
                        row_data["role"]      = t_role
                        row_data["is_active"] = t_active
                        if update_row_by_index("users", row_idx, row_data):
                            log_action(uname, "UPDATE_USER",
                                       f"Cập nhật {t_username}: role={t_role}, active={t_active}")
                            st.success(f"✅ Đã cập nhật tài khoản **{t_username}**")
                            st.rerun()
                else:
                    st.error(f"Không tìm thấy username **{t_username}**.")

# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 – THÊM TÀI KHOẢN
# ══════════════════════════════════════════════════════════════════════════════
with tab_add:
    section_header("Tạo tài khoản mới")
    with st.form("adm_add_user_form", clear_on_submit=True):
        a1, a2 = st.columns(2)
        new_username  = a1.text_input("Username *", placeholder="vd: nguyen.van.a")
        new_fullname  = a2.text_input("Họ và tên *", placeholder="vd: Nguyễn Văn A")
        new_password  = a1.text_input("Mật khẩu *", type="password", placeholder="Tối thiểu 6 ký tự")
        new_password2 = a2.text_input("Xác nhận mật khẩu *", type="password")
        new_role      = a1.selectbox("Role", [r.value for r in Role])
        new_active    = a2.selectbox("Trạng thái", ["TRUE", "FALSE"])

        submitted = st.form_submit_button("✅ Tạo tài khoản", type="primary")

        if submitted:
            errors = []
            if not new_username.strip(): errors.append("Username không được để trống.")
            if not new_fullname.strip(): errors.append("Họ và tên không được để trống.")
            if not new_password:         errors.append("Mật khẩu không được để trống.")
            if len(new_password) < 6:    errors.append("Mật khẩu cần ít nhất 6 ký tự.")
            if new_password != new_password2: errors.append("Mật khẩu xác nhận không khớp.")

            if errors:
                for e in errors:
                    st.error(e)
            else:
                # Kiểm tra trùng username
                df_u = get_users()
                if not df_u.empty and new_username.lower() in df_u["username"].str.lower().values:
                    st.error(f"Username **{new_username}** đã tồn tại.")
                else:
                    pwd_hash = bcrypt.hashpw(new_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
                    row_data = {
                        "username":      new_username.strip(),
                        "password_hash": pwd_hash,
                        "full_name":     new_fullname.strip(),
                        "role":          new_role,
                        "is_active":     new_active,
                    }
                    if append_row("users", row_data):
                        log_action(uname, "CREATE_USER",
                                   f"Tạo tài khoản mới: {new_username} ({new_role})")
                        st.success(f"✅ Đã tạo tài khoản **{new_username}** thành công!")
                    else:
                        st.error("Lỗi khi lưu tài khoản vào Google Sheets.")

    st.markdown("""
    <div style="background:rgba(245,158,11,0.08);border:1px solid rgba(245,158,11,0.2);
                border-radius:12px;padding:1rem 1.2rem;margin-top:1rem;">
        <strong style="color:#F59E0B;">⚠️ Lưu ý bảo mật</strong><br>
        <span style="color:#94A3B8;font-size:0.85rem;">
        Mật khẩu được lưu dưới dạng hash bcrypt – không thể đọc ngược.
        Hãy yêu cầu người dùng đổi mật khẩu sau lần đăng nhập đầu tiên.
        </span>
    </div>
    """, unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# TAB 3 – ĐỔI MẬT KHẨU
# ══════════════════════════════════════════════════════════════════════════════
with tab_pwd:
    section_header("Đặt lại mật khẩu cho tài khoản")
    with st.form("adm_pwd_form", clear_on_submit=True):
        p1, p2 = st.columns(2)
        pwd_username = p1.text_input("Username cần đặt lại mật khẩu")
        new_pwd      = p2.text_input("Mật khẩu mới", type="password")
        new_pwd2     = p1.text_input("Xác nhận mật khẩu mới", type="password")

        if st.form_submit_button("🔑 Đặt lại mật khẩu", type="primary"):
            errors = []
            if not pwd_username: errors.append("Vui lòng nhập username.")
            if not new_pwd:      errors.append("Vui lòng nhập mật khẩu mới.")
            if len(new_pwd) < 6: errors.append("Mật khẩu mới cần ít nhất 6 ký tự.")
            if new_pwd != new_pwd2: errors.append("Mật khẩu xác nhận không khớp.")

            if errors:
                for e in errors: st.error(e)
            else:
                row_idx = find_user_row(pwd_username)
                if not row_idx:
                    st.error(f"Không tìm thấy username **{pwd_username}**.")
                else:
                    df_u = get_users()
                    matched = df_u[df_u["username"].str.lower() == pwd_username.lower()]
                    if matched.empty:
                        st.error("Không tìm thấy tài khoản.")
                    else:
                        row_data = matched.iloc[0].to_dict()
                        row_data["password_hash"] = bcrypt.hashpw(
                            new_pwd.encode("utf-8"), bcrypt.gensalt()
                        ).decode("utf-8")
                        if update_row_by_index("users", row_idx, row_data):
                            log_action(uname, "RESET_PWD",
                                       f"Đặt lại mật khẩu cho {pwd_username}")
                            st.success(f"✅ Đã đặt lại mật khẩu cho **{pwd_username}**")

# ══════════════════════════════════════════════════════════════════════════════
# TAB 4 – AUDIT LOG
# ══════════════════════════════════════════════════════════════════════════════
with tab_log:
    section_header("Nhật ký hoạt động hệ thống")

    col_filter, col_refresh = st.columns([4, 1])
    with col_refresh:
        if st.button("🔄 Tải lại", use_container_width=True, key="adm_log_refresh"):
            st.rerun()
    with col_filter:
        log_search = st.text_input("Tìm kiếm trong log", placeholder="Nhập username hoặc action...", key="adm_log_search")

    df_log = read_sheet_as_df("audit_log")

    if df_log.empty:
        st.info("Chưa có nhật ký hoạt động.")
    else:
        if log_search:
            mask = df_log.apply(lambda row: row.astype(str).str.contains(log_search, case=False).any(), axis=1)
            df_log = df_log[mask]

        # Hiển thị mới nhất trước
        if "timestamp" in df_log.columns:
            df_log = df_log.sort_values("timestamp", ascending=False)

        st.dataframe(
            df_log,
            use_container_width=True,
            hide_index=True,
            height=550,
            column_config={
                "timestamp": st.column_config.TextColumn("Thời gian", width="medium"),
                "username":  st.column_config.TextColumn("Người dùng", width="small"),
                "action":    st.column_config.TextColumn("Hành động", width="small"),
                "details":   st.column_config.TextColumn("Chi tiết", width="large"),
            },
        )
        st.caption(f"Tổng: {len(df_log):,} bản ghi")
