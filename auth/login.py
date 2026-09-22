"""
Module xác thực và quản lý phiên đăng nhập.
Sử dụng bcrypt để kiểm tra mật khẩu và st.session_state để giữ phiên.
"""

import base64
import os
import streamlit as st
import bcrypt
from datetime import datetime, timedelta
from services.gsheet import read_sheet_as_df, append_row, log_action

# Phiên hết hạn sau 8 tiếng
SESSION_TIMEOUT_HOURS = 8

# ── Kiểm tra phiên ────────────────────────────────────────────────────────────

def check_login() -> bool:
    """Trả về True nếu người dùng đang đăng nhập và phiên còn hạn."""
    if "user" not in st.session_state or "login_time" not in st.session_state:
        return False
    elapsed = datetime.now() - st.session_state["login_time"]
    if elapsed > timedelta(hours=SESSION_TIMEOUT_HOURS):
        _clear_session()
        return False
    return True


def get_current_user() -> dict:
    """Lấy thông tin người dùng hiện tại từ session."""
    return st.session_state.get("user", {})


def get_current_role() -> str:
    """Lấy role của người dùng hiện tại."""
    return get_current_user().get("role", "viewer").lower()


# ── Xác thực ─────────────────────────────────────────────────────────────────

def authenticate(username: str, password: str) -> dict | None:
    """
    Xác thực username/password với dữ liệu trong sheet 'users'.
    Trả về dict thông tin user nếu hợp lệ, None nếu không.
    """
    try:
        df = read_sheet_as_df("users")
        if df.empty or "username" not in df.columns:
            st.error("Không thể đọc danh sách tài khoản. Kiểm tra kết nối Google Sheets.")
            return None

        # Tìm user theo username (case-insensitive)
        matched = df[df["username"].str.strip().str.lower() == username.strip().lower()]
        if matched.empty:
            return None

        user = matched.iloc[0].to_dict()

        # Kiểm tra tài khoản có active không
        if str(user.get("is_active", "FALSE")).upper() not in ("TRUE", "1", "YES"):
            return None

        # Kiểm tra mật khẩu
        stored_hash = str(user.get("password_hash", "")).encode("utf-8")
        if not stored_hash:
            return None
        if bcrypt.checkpw(password.encode("utf-8"), stored_hash):
            return user
        return None

    except Exception as exc:
        st.error(f"Lỗi xác thực: {exc}")
        return None


# ── Đăng nhập / Đăng xuất ────────────────────────────────────────────────────

def login(user: dict) -> None:
    """Lưu thông tin user vào session và ghi audit log."""
    st.session_state["user"] = user
    st.session_state["login_time"] = datetime.now()
    log_action(user.get("username", "?"), "LOGIN", "Đăng nhập thành công")


def logout() -> None:
    """Xóa session và ghi audit log đăng xuất."""
    username = get_current_user().get("username", "unknown")
    log_action(username, "LOGOUT", "Đăng xuất")
    _clear_session()


def _clear_session() -> None:
    for key in list(st.session_state.keys()):
        del st.session_state[key]


def require_auth() -> None:
    """
    Gọi hàm này ở đầu mỗi page để bắt buộc đăng nhập.
    Nếu chưa đăng nhập, hiện trang login và dừng lại.
    """
    if not check_login():
        _render_login_page()
        st.stop()


# ── Giao diện trang đăng nhập ─────────────────────────────────────────────────

def _get_logo_base64() -> str:
    """Encode EA-logo.png thành base64 để nhúng vào HTML."""
    logo_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "EA-logo.png")
    if os.path.exists(logo_path):
        with open(logo_path, "rb") as f:
            return base64.b64encode(f.read()).decode()
    return ""


def _render_login_page() -> None:
    """Vẽ giao diện trang đăng nhập."""
    logo_b64 = _get_logo_base64()
    logo_html = (
        f'<img src="data:image/png;base64,{logo_b64}" '
        f'style="width:110px;height:auto;margin-bottom:0.5rem;">'
        if logo_b64
        else '<div class="ea-logo-text">EA</div>'
    )
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap');

    html, body, [class*="css"] { font-family: 'Inter', sans-serif !important; }

    .stApp {
        background: radial-gradient(ellipse at 20% 50%, rgba(0,179,126,0.08) 0%, transparent 50%),
                    radial-gradient(ellipse at 80% 20%, rgba(6,182,212,0.06) 0%, transparent 50%),
                    linear-gradient(135deg, #060D1A 0%, #0A1628 50%, #050C18 100%);
        min-height: 100vh;
    }

    #MainMenu, footer, header { visibility: hidden; }

    /* Ẩn hoàn toàn sidebar trên trang login */
    section[data-testid="stSidebar"] { display: none !important; }
    [data-testid="collapsedControl"]  { display: none !important; }

    .login-wrap {
        display: flex;
        align-items: center;
        justify-content: center;
        min-height: 85vh;
    }

    [data-testid="stForm"] {
        background: rgba(255,255,255,0.03);
        border: 1px solid rgba(0,179,126,0.2);
        border-radius: 20px;
        padding: 3rem 2.5rem;
        max-width: 420px;
        width: 100%;
        backdrop-filter: blur(20px);
        box-shadow: 0 40px 80px rgba(0,0,0,0.6), inset 0 1px 0 rgba(255,255,255,0.05);
        position: relative;
        overflow: hidden;
    }

    [data-testid="stForm"]::before {
        content: '';
        position: absolute;
        top: 0; left: 0; right: 0;
        height: 3px;
        background: linear-gradient(90deg, #00B37E, #06B6D4, #00B37E);
        background-size: 200% 100%;
        animation: shimmer 3s linear infinite;
    }

    @keyframes shimmer {
        0%   { background-position: -200% center; }
        100% { background-position:  200% center; }
    }

    .ea-logo {
        text-align: center;
        margin-bottom: 2rem;
    }

    .ea-logo-text {
        font-size: 3.5rem;
        font-weight: 900;
        background: linear-gradient(135deg, #00B37E, #06B6D4);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        line-height: 1;
        letter-spacing: -2px;
    }

    .ea-logo-sub {
        font-size: 0.65rem;
        color: #64748B;
        letter-spacing: 0.25em;
        text-transform: uppercase;
        margin-top: 4px;
    }

    .login-title {
        text-align: center;
        font-size: 1.4rem;
        font-weight: 700;
        color: #E2E8F0;
        margin-bottom: 0.35rem;
    }

    .login-sub {
        text-align: center;
        font-size: 0.82rem;
        color: #64748B;
        margin-bottom: 2rem;
    }

    .footer-text {
        text-align: center;
        color: #334155;
        font-size: 0.72rem;
        margin-top: 2.5rem;
    }
    </style>
    """, unsafe_allow_html=True)

    col_l, col_mid, col_r = st.columns([1, 1.4, 1])
    with col_mid:

        # Logo
        st.markdown(f"""
        <div class="ea-logo">
            {logo_html}
            <div class="ea-logo-sub">EdTech Agency Dashboard</div>
        </div>
        <div class="login-title">Đăng nhập hệ thống</div>
        <div class="login-sub">Nhập thông tin tài khoản để tiếp tục</div>
        """, unsafe_allow_html=True)

        # Form
        with st.form("ea_login_form", clear_on_submit=False):
            username = st.text_input(
                "Tên đăng nhập",
                placeholder="username...",
                label_visibility="visible",
            )
            password = st.text_input(
                "Mật khẩu",
                type="password",
                placeholder="••••••••",
                label_visibility="visible",
            )
            st.markdown("<br>", unsafe_allow_html=True)
            submitted = st.form_submit_button(
                "🚀  Đăng nhập",
                use_container_width=True,
                type="primary",
            )

            if submitted:
                if not username.strip() or not password.strip():
                    st.warning("⚠️ Vui lòng nhập đầy đủ tên đăng nhập và mật khẩu.")
                else:
                    with st.spinner("Đang xác thực..."):
                        user = authenticate(username, password)
                    if user:
                        login(user)
                        # Xóa localStorage để sidebar luôn mở sau khi đăng nhập
                        st.markdown("""
                        <script>
                        try {
                            Object.keys(localStorage).forEach(function(k) {
                                if (k.indexOf('sidebar') !== -1) localStorage.removeItem(k);
                            });
                        } catch(e) {}
                        </script>
                        """, unsafe_allow_html=True)
                        st.success(f"✅ Chào mừng **{user.get('full_name', username)}**!")
                        st.rerun()
                    else:
                        st.error("❌ Tên đăng nhập hoặc mật khẩu không chính xác.")

        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown(
        '<div class="footer-text">© 2024 EdTech Agency &nbsp;•&nbsp; Phiên bản 1.0</div>',
        unsafe_allow_html=True,
    )
