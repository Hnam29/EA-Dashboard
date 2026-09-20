"""
UI components: CSS toàn cục, metric cards, biểu đồ Plotly, sidebar helper.
Tất cả biểu đồ dùng dark theme nhất quán với màu brand EA (#00B37E).
"""

import base64
import os
import streamlit as st
import streamlit.components.v1 as components
import plotly.graph_objects as go
import pandas as pd
from typing import List, Tuple, Any

# Đường dẫn logo (tương đối từ root project)
_LOGO_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "EA-logo.png")


def _logo_b64() -> str:
    """Trả về base64 của EA-logo.png, hoặc chuỗi rỗng nếu không tìm thấy file."""
    if os.path.exists(_LOGO_PATH):
        with open(_LOGO_PATH, "rb") as f:
            return base64.b64encode(f.read()).decode()
    return ""

# ── Màu sắc brand ──────────────────────────────────────────────────────────────

PALETTE = [
    "#00B37E", "#06B6D4", "#8B5CF6",
    "#F59E0B", "#EF4444", "#EC4899",
    "#10B981", "#3B82F6", "#A78BFA",
]

CHART_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(color="#94A3B8", family="Inter, sans-serif"),
    margin=dict(l=12, r=12, t=42, b=12),
    hoverlabel=dict(
        bgcolor="#1E293B",
        bordercolor="rgba(0,179,126,0.3)",
        font=dict(color="#E2E8F0", size=12),
    ),
)


# ── CSS toàn cục ──────────────────────────────────────────────────────────────

def inject_css() -> None:
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap');

    html, body, [class*="css"] { font-family: 'Inter', sans-serif !important; }

    /* Hide branding */
    #MainMenu, footer, header { visibility: hidden; }

    /* Sidebar background */
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0A1628 0%, #0A0F1E 100%);
        border-right: 1px solid rgba(255,255,255,0.04);
    }


    /* Scrollbar */
    ::-webkit-scrollbar { width: 6px; height: 6px; }
    ::-webkit-scrollbar-track { background: #0A0F1E; }
    ::-webkit-scrollbar-thumb { background: rgba(0,179,126,0.4); border-radius: 3px; }

    /* Metric card */
    .metric-card {
        background: linear-gradient(135deg, rgba(0,179,126,0.06) 0%, rgba(6,182,212,0.04) 100%);
        border: 1px solid rgba(0,179,126,0.18);
        border-radius: 14px;
        padding: 1.2rem 1.4rem;
        text-align: center;
        position: relative;
        overflow: hidden;
        transition: transform 0.2s ease, box-shadow 0.2s ease;
        height: 100%;
    }
    .metric-card::before {
        content: '';
        position: absolute; top: 0; left: 0; right: 0; height: 3px;
        background: linear-gradient(90deg, #00B37E, #06B6D4);
    }
    .metric-card:hover {
        transform: translateY(-3px);
        box-shadow: 0 10px 30px rgba(0,179,126,0.15);
    }
    .mc-icon  { font-size: 1.4rem; margin-bottom: 0.4rem; }
    .mc-label { font-size: 0.68rem; color: #64748B; font-weight: 600;
                text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 0.3rem; }
    .mc-value { font-size: 1.9rem; font-weight: 800; color: #00B37E;
                line-height: 1.1; margin-bottom: 0.15rem; }
    .mc-sub   { font-size: 0.68rem; color: #475569; }

    /* Section header */
    .sec-header {
        font-size: 0.8rem; font-weight: 700; color: #E2E8F0;
        padding: 0.55rem 0.9rem;
        background: rgba(0,179,126,0.08);
        border-left: 3px solid #00B37E;
        border-radius: 0 8px 8px 0;
        margin-bottom: 0.65rem;
        text-transform: uppercase; letter-spacing: 0.06em;
    }

    /* Page title */
    .page-header {
        display: flex; align-items: center; gap: 1.2rem;
        padding: 0.8rem 0 1rem;
        border-bottom: 1px solid rgba(255,255,255,0.05);
        margin-bottom: 1.2rem;
    }
    .ea-mark {
        font-size: 2.2rem; font-weight: 900; line-height: 1;
        background: linear-gradient(135deg, #00B37E, #06B6D4);
        -webkit-background-clip: text; -webkit-text-fill-color: transparent;
        background-clip: text;
        letter-spacing: -1px;
    }
    .ea-mark-sub { font-size: 0.58rem; color: #475569; letter-spacing: 0.2em;
                   text-transform: uppercase; margin-top: 2px; }
    .page-title   { font-size: 1.45rem; font-weight: 800; color: #E2E8F0; margin: 0; }
    .page-subtitle{ font-size: 0.8rem; color: #64748B; margin: 0.2rem 0 0; }

    /* Status badge */
    .badge {
        display: inline-block; padding: 0.18rem 0.55rem; border-radius: 20px;
        font-size: 0.68rem; font-weight: 700; letter-spacing: 0.04em;
    }
    .badge-ok      { background: rgba(0,179,126,0.18); color: #00B37E; }
    .badge-consider{ background: rgba(245,158,11,0.18); color: #F59E0B; }
    .badge-remove  { background: rgba(239,68,68,0.18);  color: #EF4444; }

    /* User card in sidebar */
    .user-card {
        background: rgba(0,179,126,0.06);
        border: 1px solid rgba(0,179,126,0.12);
        border-radius: 12px;
        padding: 1rem;
        text-align: center;
        margin-bottom: 1rem;
    }
    .user-avatar { font-size: 2rem; margin-bottom: 0.3rem; }
    .user-name   { font-size: 0.9rem; font-weight: 700; color: #E2E8F0; }
    .user-role   { font-size: 0.7rem; font-weight: 600; text-transform: uppercase;
                   letter-spacing: 0.1em; margin-top: 0.2rem; }

    /* Table container */
    div[data-testid="stDataFrame"] > div {
        border-radius: 12px;
        border: 1px solid rgba(255,255,255,0.05) !important;
    }
    </style>
    """, unsafe_allow_html=True)



# ── Header EA ─────────────────────────────────────────────────────────────────

def render_page_header(title: str, subtitle: str = "") -> None:
    b64 = _logo_b64()
    logo_html = (
        f'<img src="data:image/png;base64,{b64}" style="height:56px;width:auto;object-fit:contain;">'
        if b64 else
        '<div class="ea-mark">EA</div><div class="ea-mark-sub">EdTech Agency</div>'
    )
    st.markdown(f"""
    <div class="page-header">
        <div style="display:flex;align-items:center;">{logo_html}</div>
        <div>
            <div class="page-title">{title}</div>
            {"<div class='page-subtitle'>" + subtitle + "</div>" if subtitle else ""}
        </div>
    </div>
    """, unsafe_allow_html=True)


# ── Section header ────────────────────────────────────────────────────────────

def section_header(title: str) -> None:
    st.markdown(f'<div class="sec-header">{title}</div>', unsafe_allow_html=True)


# ── Metric card ───────────────────────────────────────────────────────────────

def metric_card(label: str, value: Any, icon: str = "📊", sub: str = "") -> None:
    if isinstance(value, (int, float)) and value >= 1000:
        fmt = f"{value / 1000:,.3f}K"
    elif isinstance(value, int):
        fmt = f"{value:,}"
    else:
        fmt = str(value)
    st.markdown(f"""
    <div class="metric-card">
        <div class="mc-icon">{icon}</div>
        <div class="mc-label">{label}</div>
        <div class="mc-value">{fmt}</div>
        {"<div class='mc-sub'>" + sub + "</div>" if sub else ""}
    </div>
    """, unsafe_allow_html=True)


def metrics_row(items: List[Tuple[str, Any, str, str]]) -> None:
    """items: list of (label, value, icon, sub)"""
    cols = st.columns(len(items))
    for col, (label, value, icon, sub) in zip(cols, items):
        with col:
            metric_card(label, value, icon, sub)


# ── Biểu đồ ───────────────────────────────────────────────────────────────────

def chart_bar_h(df: pd.DataFrame, group_col: str, title: str, max_rows: int = 15) -> None:
    """Bar chart nằm ngang – đếm số lượng bản ghi theo group_col."""
    if group_col not in df.columns or df.empty:
        st.info(f"Không có dữ liệu cột '{group_col}'.")
        return

    data = (
        df[group_col]
        .value_counts()
        .head(max_rows)
        .reset_index()
    )
    data.columns = ["name", "count"]
    data = data.sort_values("count", ascending=True)

    n = len(data)
    colors = [f"rgba(0,179,126,{0.35 + 0.65 * i / max(n - 1, 1):.2f})" for i in range(n)]

    fig = go.Figure(go.Bar(
        x=data["count"],
        y=data["name"],
        orientation="h",
        marker=dict(color=colors, line=dict(width=0)),
        text=data["count"].apply(lambda v: f"{v:,}"),
        textposition="outside",
        textfont=dict(color="#64748B", size=10),
        hovertemplate="%{y}: <b>%{x:,}</b><extra></extra>",
    ))
    fig.update_layout(
        title=dict(text=title, font=dict(size=13, color="#CBD5E1"), x=0.5, xanchor="center"),
        xaxis=dict(gridcolor="rgba(255,255,255,0.04)", color="#475569", zeroline=False),
        yaxis=dict(color="#94A3B8", tickfont=dict(size=10)),
        height=max(280, n * 28 + 60),
        **CHART_LAYOUT,
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


def chart_donut(df: pd.DataFrame, group_col: str, title: str, max_slices: int = 6) -> None:
    """Donut chart – top N theo group_col. Tự động loại bỏ giá trị 'Khác' có trong data."""
    if group_col not in df.columns or df.empty:
        st.info(f"Không có dữ liệu cột '{group_col}'.")
        return

    # Loại bỏ giá trị 'Khác' và giá trị trống khỏi dữ liệu gốc trước khi vẽ
    exclude = {"khác", "", "nan", "none"}
    df_clean = df[~df[group_col].astype(str).str.strip().str.lower().isin(exclude)]

    if df_clean.empty:
        st.info(f"Không có dữ liệu hợp lệ để hiển thị.")
        return

    data   = df_clean[group_col].value_counts().head(max_slices)
    others = df_clean[group_col].value_counts().iloc[max_slices:].sum()
    labels = data.index.tolist()
    values = data.values.tolist()
    if others > 0:
        labels.append("Khác")
        values.append(int(others))

    fig = go.Figure(go.Pie(
        labels=labels,
        values=values,
        hole=0.52,
        marker=dict(colors=PALETTE[:len(labels)], line=dict(color="#0A0F1E", width=2)),
        textinfo="label+percent",
        textfont=dict(size=10, color="#CBD5E1"),
        insidetextorientation="radial",
        hovertemplate="%{label}: <b>%{value:,}</b> (%{percent})<extra></extra>",
    ))
    fig.update_layout(
        title=dict(text=title, font=dict(size=13, color="#CBD5E1"), x=0.5, xanchor="center"),
        legend=dict(font=dict(color="#94A3B8", size=9), bgcolor="rgba(0,0,0,0)", orientation="h", y=-0.15),
        height=360,
        **CHART_LAYOUT,
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


def chart_funnel(df: pd.DataFrame, group_col: str, title: str, max_cats: int = 8) -> None:
    """Funnel chart – hiển thị số lượng và tỷ lệ theo group_col (giảm dần)."""
    if group_col not in df.columns or df.empty:
        st.info(f"Không có dữ liệu cột '{group_col}'.")
        return

    # Loại bỏ giá trị rống/không hợp lệ
    exclude = {"", "nan", "none"}
    df_clean = df[~df[group_col].astype(str).str.strip().str.lower().isin(exclude)]
    counts = df_clean[group_col].value_counts().head(max_cats)

    if counts.empty:
        st.info("Không có dữ liệu để hiển thị.")
        return

    fig = go.Figure(go.Funnel(
        y=counts.index.tolist(),
        x=counts.values.tolist(),
        textposition="inside",
        textinfo="value+percent total",
        textfont=dict(color="white", size=10),
        marker=dict(
            color=PALETTE[:len(counts)],
            line=dict(width=1, color="#0A0F1E"),
        ),
        connector=dict(visible=False),
        hovertemplate="<b>%{y}</b>: %{x:,} (%{percentTotal})<extra></extra>",
    ))
    fig.update_layout(
        title=dict(text=title, font=dict(size=13, color="#CBD5E1"), x=0.5, xanchor="center"),
        height=360,
        **CHART_LAYOUT,
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


# ── Sidebar user info ─────────────────────────────────────────────────────────

def render_user_card(full_name: str, role: str, role_color: str = "#00B37E") -> None:
    b64 = _logo_b64()
    logo_html = (
        f'<img src="data:image/png;base64,{b64}" style="width:72px;height:auto;margin-bottom:0.5rem;">'
        if b64 else
        '<div style="font-size:1.8rem;font-weight:900;color:#00B37E;">EA</div>'
    )
    st.markdown(f"""
    <div class="user-card">
        {logo_html}
        <div class="user-name">{full_name}</div>
        <div class="user-role" style="color:{role_color};">{role.upper()}</div>
    </div>
    """, unsafe_allow_html=True)
