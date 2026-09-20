"""
app.py – Entry point chính của EA Dashboard.
Xử lý routing: nếu chưa đăng nhập → hiển thị trang login;
nếu đã đăng nhập → hiển thị trang Welcome + sidebar điều hướng.
"""

import streamlit as st
from auth.login import require_auth, get_current_user, get_current_role, logout
from auth.roles import get_role_label, get_role_color
from components.ui import inject_css, render_user_card, render_page_header, section_header

st.set_page_config(
    page_title="EA Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Bắt buộc đăng nhập
require_auth()

# CSS
inject_css()

# Thông tin user
user  = get_current_user()
role  = get_current_role()
color = get_role_color(role)

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    render_user_card(
        full_name=user.get("full_name", user.get("username", "User")),
        role=get_role_label(role),
        role_color=color,
    )
    if st.button("🚪 Đăng xuất", use_container_width=True):
        logout()
        st.rerun()
    st.divider()
    section_header("Điều hướng")
    st.page_link("app.py",                    label="🏠 Trang chủ",       icon=None)
    st.page_link("pages/1_Datawarehouse.py",  label="📊 Datawarehouse",   icon=None)
    st.page_link("pages/2_GV_K12.py",         label="👨‍🏫 GV-K12",         icon=None)
    if role == "admin":
        st.page_link("pages/3_Admin.py",      label="⚙️ Quản trị",        icon=None)
    st.divider()
    st.markdown(
        "<div style='font-size:0.68rem;color:#334155;text-align:center;'>© 2024 EdTech Agency v1.0</div>",
        unsafe_allow_html=True,
    )

# ── Trang chủ ─────────────────────────────────────────────────────────────────
render_page_header(
    title="Chào mừng trở lại!",
    subtitle=f"Xin chào, {user.get('full_name', 'bạn')} – {get_role_label(role)}",
)

st.markdown("""
<div style="
    background: linear-gradient(135deg, rgba(0,179,126,0.06), rgba(6,182,212,0.04));
    border: 1px solid rgba(0,179,126,0.15);
    border-radius: 16px;
    padding: 2rem 2.5rem;
    margin-top: 1rem;
">
    <h2 style="color:#E2E8F0; margin-top:0; font-size:1.2rem;">📋 Tổng quan hệ thống</h2>
    <p style="color:#94A3B8; line-height:1.8;">
        EA Dashboard là hệ thống quản lý và phân tích dữ liệu khách hàng của <strong style="color:#00B37E;">EdTech Agency</strong>.
        Toàn bộ dữ liệu được lưu trữ trên Google Sheets và đồng bộ theo thời gian thực.
    </p>
</div>
""", unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# Shortcut cards
c1, c2, c3 = st.columns(3)
with c1:
    st.markdown("""
    <div style="background:rgba(0,179,126,0.06);border:1px solid rgba(0,179,126,0.15);
                border-radius:14px;padding:1.5rem;text-align:center;cursor:pointer;">
        <div style="font-size:2.5rem;margin-bottom:0.6rem;">📊</div>
        <div style="font-weight:700;color:#E2E8F0;font-size:1rem;">Datawarehouse</div>
        <div style="color:#64748B;font-size:0.8rem;margin-top:0.3rem;">Tổng hợp dữ liệu khách hàng,<br>biểu đồ phân tích</div>
    </div>
    """, unsafe_allow_html=True)
with c2:
    st.markdown("""
    <div style="background:rgba(6,182,212,0.06);border:1px solid rgba(6,182,212,0.15);
                border-radius:14px;padding:1.5rem;text-align:center;cursor:pointer;">
        <div style="font-size:2.5rem;margin-bottom:0.6rem;">👨‍🏫</div>
        <div style="font-weight:700;color:#E2E8F0;font-size:1rem;">GV-K12</div>
        <div style="color:#64748B;font-size:0.8rem;margin-top:0.3rem;">Danh sách giáo viên K12<br>toàn quốc</div>
    </div>
    """, unsafe_allow_html=True)
with c3:
    if role == "admin":
        st.markdown("""
        <div style="background:rgba(239,68,68,0.06);border:1px solid rgba(239,68,68,0.12);
                    border-radius:14px;padding:1.5rem;text-align:center;cursor:pointer;">
            <div style="font-size:2.5rem;margin-bottom:0.6rem;">⚙️</div>
            <div style="font-weight:700;color:#E2E8F0;font-size:1rem;">Quản trị</div>
            <div style="color:#64748B;font-size:0.8rem;margin-top:0.3rem;">Quản lý tài khoản,<br>audit log</div>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown("""
        <div style="background:rgba(139,92,246,0.06);border:1px solid rgba(139,92,246,0.12);
                    border-radius:14px;padding:1.5rem;text-align:center;">
            <div style="font-size:2.5rem;margin-bottom:0.6rem;">📅</div>
            <div style="font-weight:700;color:#E2E8F0;font-size:1rem;">Dữ liệu cập nhật</div>
            <div style="color:#64748B;font-size:0.8rem;margin-top:0.3rem;">Tự động đồng bộ từ<br>Google Sheets mỗi 5 phút</div>
        </div>
        """, unsafe_allow_html=True)
