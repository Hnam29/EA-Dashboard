# EA Dashboard

Dashboard nội bộ dành cho **EdTech Agency**, xây dựng bằng **Streamlit** với **Google Sheets** làm backend.

---

## ✨ Tính năng

| Tính năng | Mô tả |
|---|---|
| 🔐 Đăng nhập phân quyền | 3 cấp: Admin / Editor / Viewer |
| 📊 Datawarehouse | Tổng hợp data khách hàng, biểu đồ, filter đa chiều |
| 👨‍🏫 GV-K12 | Danh sách giáo viên K12 với filter Sở GD |
| ✏️ CRUD | Thêm/Sửa/Xóa dữ liệu trực tiếp lên Google Sheets |
| ⬇️ Export | Export CSV hoặc tạo sheet mới trên Google Sheets |
| 📜 Audit Log | Ghi lại mọi thao tác của từng user |
| ⚙️ Admin Panel | Quản lý tài khoản, đặt lại mật khẩu |

---

## 🚀 Cài đặt và chạy local

### 1. Clone project và cài dependencies

```bash
cd EA_Dashboard
python -m venv venv
source venv/bin/activate          # macOS/Linux
# venv\Scripts\activate           # Windows

pip install -r requirements.txt
```

### 2. Chuẩn bị Google Sheets

**Tạo Google Spreadsheet** với các sheet con:

| Sheet name | Cột |
|---|---|
| `users` | `username`, `password_hash`, `full_name`, `role`, `is_active` |
| `datawarehouse` | `STATUS`, `ID`, `Tên trường/công ty`, `Người phụ trách/đại diện`, `Nhóm`, `Chức vụ`, `Email`, `Tình trạng Email`, `SĐT`, `Website`, `Địa chỉ`, `Loại hình CSĐT`, `Loại trường`, `Khối`, `Quận`, `Tỉnh/TP` |
| `gv_k12` | `Sở GD`, `ID`, `Tên`, `Email`, `SĐT`, `Trường`, `Phòng GD` |
| `audit_log` | `timestamp`, `username`, `action`, `details` |

### 3. Tạo Service Account Google

1. Vào [Google Cloud Console](https://console.cloud.google.com) → **APIs & Services** → **Credentials**
2. Tạo **Service Account** → Tải file JSON về
3. Vào Google Spreadsheet → **Share** → thêm email của Service Account (quyền Editor)
4. Bật **Google Sheets API** và **Google Drive API** trong Console

### 4. Cấu hình Secrets

```bash
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
```

Điền thông tin vào `secrets.toml`:
```toml
[gcp_service_account]
type = "service_account"
project_id = "..."
private_key_id = "..."
private_key = "-----BEGIN RSA PRIVATE KEY-----\n...\n-----END RSA PRIVATE KEY-----\n"
client_email = "your-sa@your-project.iam.gserviceaccount.com"
# ... (copy toàn bộ nội dung file JSON)

[google_sheets]
spreadsheet_id = "1xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
```

### 5. Tạo tài khoản Admin đầu tiên

```bash
# Điền SPREADSHEET_ID và SERVICE_ACCOUNT_FILE vào scripts/init_users.py
python scripts/init_users.py
```

### 6. Chạy Dashboard

```bash
streamlit run app.py
```

---

## ☁️ Deploy lên Streamlit Cloud

1. Push code lên **GitHub** (đảm bảo `.gitignore` đã loại `secrets.toml`)
2. Vào [share.streamlit.io](https://share.streamlit.io) → **New app**
3. Chọn repo, branch, file chính: `app.py`
4. Vào **Advanced settings** → **Secrets** → Paste toàn bộ nội dung `secrets.toml`
5. Click **Deploy**!

---

## 📋 Phân quyền

| Quyền | Admin | Editor | Viewer |
|---|:---:|:---:|:---:|
| Xem dữ liệu | ✅ | ✅ | ✅ |
| Thêm bản ghi | ✅ | ✅ | ❌ |
| Sửa bản ghi | ✅ | ✅ | ❌ |
| Xóa bản ghi | ✅ | ❌ | ❌ |
| Export dữ liệu | ✅ | ✅ | ❌ |
| Quản lý tài khoản | ✅ | ❌ | ❌ |
| Xem Audit Log | ✅ | ❌ | ❌ |

---

## 🗂️ Cấu trúc thư mục

```
EA_Dashboard/
├── app.py                    # Entry point, trang chủ
├── requirements.txt
├── .gitignore
├── .streamlit/
│   ├── config.toml           # Theme dark EA green
│   └── secrets.toml.example  # Mẫu secrets
├── auth/
│   ├── login.py              # Xác thực, session, UI đăng nhập
│   └── roles.py              # Ma trận phân quyền
├── services/
│   └── gsheet.py             # Google Sheets API (CRUD, cache, log)
├── components/
│   └── ui.py                 # CSS, metric cards, biểu đồ Plotly
├── pages/
│   ├── 1_Datawarehouse.py    # Trang Datawarehouse
│   ├── 2_GV_K12.py           # Trang GV-K12
│   └── 3_Admin.py            # Trang quản trị (Admin only)
└── scripts/
    └── init_users.py         # Script tạo Admin user đầu tiên
```

---

## ⚡ Cache & Performance

- Dữ liệu từ Google Sheets được **cache 5 phút** (`@st.cache_data(ttl=300)`)
- Sau mỗi thao tác ghi, cache tự động xóa để dữ liệu luôn mới nhất
- Nút **🔄 Làm mới cache** trong sidebar để tải lại thủ công

---

*© 2024 EdTech Agency – EA Dashboard v1.0*
