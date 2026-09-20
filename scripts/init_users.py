#!/usr/bin/env python3
"""
Script khởi tạo tài khoản Admin đầu tiên vào Google Sheet 'users'.

Cách dùng:
    1. Điền SPREADSHEET_ID và SERVICE_ACCOUNT_FILE bên dưới
    2. Chạy: python scripts/init_users.py
    3. Nhập username, tên, mật khẩu khi được hỏi

Sheet 'users' cần có các cột (theo thứ tự):
    username | password_hash | full_name | role | is_active
"""

import sys
import getpass
import bcrypt
import gspread
from google.oauth2.service_account import Credentials

# ── Cấu hình ──────────────────────────────────────────────────────────────────
SPREADSHEET_ID       = "1YdblYk8ovrtLmbkGBJAtdNoAXqYXKILGLJH9GTvbtpE"
SERVICE_ACCOUNT_FILE = "/Users/vuhainam/Downloads/ea-dashboard-509204-a873ebd38c6a.json"

SCOPES = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive",
]

# Tên các sheet cần đảm bảo tồn tại
REQUIRED_SHEETS = {
    "users":     ["username", "password_hash", "full_name", "role", "is_active"],
    "audit_log": ["timestamp", "username", "action", "details"],
}
# ─────────────────────────────────────────────────────────────────────────────


def ensure_sheet(spreadsheet: gspread.Spreadsheet, name: str, headers: list) -> gspread.Worksheet:
    """Tạo sheet nếu chưa có, thêm dòng tiêu đề nếu còn trống."""
    try:
        ws = spreadsheet.worksheet(name)
        print(f"  ✓ Sheet '{name}' đã tồn tại.")
    except gspread.WorksheetNotFound:
        ws = spreadsheet.add_worksheet(title=name, rows=1000, cols=len(headers))
        print(f"  + Đã tạo sheet '{name}'.")

    existing_headers = ws.row_values(1)
    if not existing_headers:
        ws.append_row(headers)
        print(f"    → Đã thêm tiêu đề: {headers}")
    return ws


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def main():
    print("=" * 55)
    print("  EA Dashboard – Khởi tạo tài khoản Admin")
    print("=" * 55)

    # Kết nối
    try:
        creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
        client = gspread.authorize(creds)
        sp = client.open_by_key(SPREADSHEET_ID)
        print(f"\n✅ Kết nối thành công: {sp.title}\n")
    except FileNotFoundError:
        print(f"\n❌ Không tìm thấy file '{SERVICE_ACCOUNT_FILE}'.")
        print("   Hãy tải file JSON Service Account từ Google Cloud Console.")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Lỗi kết nối: {e}")
        sys.exit(1)

    # Đảm bảo các sheet cần thiết
    print("📋 Kiểm tra và tạo các sheet cần thiết...")
    for sheet_name, headers in REQUIRED_SHEETS.items():
        ensure_sheet(sp, sheet_name, headers)

    # Nhập thông tin admin
    print("\n👤 Nhập thông tin tài khoản Admin đầu tiên:")
    username  = input("   Username: ").strip()
    full_name = input("   Họ và tên: ").strip()
    while True:
        password  = getpass.getpass("   Mật khẩu (ẩn): ")
        password2 = getpass.getpass("   Xác nhận mật khẩu: ")
        if password == password2 and len(password) >= 6:
            break
        if password != password2:
            print("   ⚠️ Mật khẩu không khớp, nhập lại.")
        else:
            print("   ⚠️ Mật khẩu cần ít nhất 6 ký tự.")

    if not username or not full_name:
        print("\n❌ Username và Họ tên không được để trống.")
        sys.exit(1)

    # Kiểm tra username đã tồn tại chưa
    ws_users = sp.worksheet("users")
    existing = ws_users.get_all_records()
    if any(u.get("username", "").lower() == username.lower() for u in existing):
        print(f"\n⚠️ Username '{username}' đã tồn tại trong sheet 'users'.")
        sys.exit(1)

    # Thêm vào sheet
    pwd_hash = hash_password(password)
    ws_users.append_row([username, pwd_hash, full_name, "admin", "TRUE"])

    print(f"\n✅ Đã tạo tài khoản Admin:")
    print(f"   Username : {username}")
    print(f"   Tên      : {full_name}")
    print(f"   Role     : admin")
    print(f"   Active   : TRUE")
    print("\n🚀 Bạn có thể đăng nhập ngay vào EA Dashboard!")
    print("=" * 55)


if __name__ == "__main__":
    main()
