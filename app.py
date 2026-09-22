"""
Ykone Task Dispatch — Internal job & debrief manager.
Monochrome typewriter theme (black / white / grey shadows).
"""

from __future__ import annotations

import calendar
import io
import json
import uuid
from datetime import date, datetime
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from st_aggrid import AgGrid, DataReturnMode, GridOptionsBuilder, GridUpdateMode, JsCode

# ─────────────────────────────────────────────────────────────────────────────
# Page config  (must be first Streamlit call)
# ─────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Ykone Task Dispatch",
    page_icon="ykone_logo.jpg",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────────────────────────────────────
# Paths & constants
# ─────────────────────────────────────────────────────────────────────────────
APP_DIR   = Path(__file__).parent
DATA_DIR  = APP_DIR / "data"
DATA_FILE = DATA_DIR / "planning.json"
LOGO_FILE = APP_DIR / "ykone_logo.jpg"


def _fs_writable() -> bool:
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        test = DATA_DIR / ".write_test"
        test.write_text("x")
        test.unlink()
        return True
    except OSError:
        return False


FS_WRITABLE = _fs_writable()

# Editable columns (order matters for grid and Excel export).
EDITABLE_COLS = [
    "TEAM CREA 1", "TEAM CREA 2", "CM", "ACCOUNTS",
    "BRIEFING CRA", "DEBRIEF", "PIT STOP",
    "% D'AVANCEMENT", "DEADLINE", "PREZ CLIENT",
    "ETAT CREA", "OBSERVATIONS",
]
DATE_COLS = ["BRIEFING CRA", "DEADLINE", "PREZ CLIENT"]
ALL_COLS  = ["id", "CLIENT", "JOB"] + EDITABLE_COLS + ["COMPLETED"]

ETAT_OPTIONS = ["EN COURS", "ATT BAT", "BAT OK", "COMPLETED", "ANNULÉ"]

# Editable defaults — populate via the sidebar or the JSON backup file over time.
CREA_NAMES: list[str] = []
CM_NAMES: list[str] = []
ACCOUNTING_NAMES: list[str] = []

# ─────────────────────────────────────────────────────────────────────────────
# Monochrome typewriter palette
# ─────────────────────────────────────────────────────────────────────────────
BG        = "#0a0a0a"
SURFACE   = "#131313"
CARD      = "#181818"
CARD_ALT  = "#1e1e1e"
LINE      = "#2a2a2a"
LINE_SOFT = "#1f1f1f"
TEXT      = "#f2f2f2"
DIM       = "#8a8a8a"
DIM_SOFT  = "#5c5c5c"
INK       = "#ffffff"
INK_SOFT  = "#d6d6d6"
SHADOW    = "0 12px 30px rgba(0,0,0,0.55), 0 2px 0 rgba(255,255,255,0.03) inset"
SHADOW_SM = "0 6px 18px rgba(0,0,0,0.55)"

# Traffic-light hues kept minimal for KPIs / progress cells only.
OK   = "#e8e8e8"
WARN = "#9c9c9c"
BAD  = "#5a5a5a"

# ─────────────────────────────────────────────────────────────────────────────
# CSS — typewriter / monochrome theme
# ─────────────────────────────────────────────────────────────────────────────
STYLE = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Courier+Prime:wght@400;700&family=DM+Mono:wght@400;500&display=swap');

html, body, [data-testid="stApp"] {{
    background: {BG};
    color: {TEXT};
    font-family: 'Courier Prime', 'Courier New', monospace;
    letter-spacing: 0.2px;
}}

/* keep Material Symbols icons rendered (Streamlit uses them for expander arrows) */
[data-testid="stIconMaterial"],
[data-testid*="Icon"],
.material-icons, .material-icons-outlined,
.material-icons-round, .material-icons-sharp,
.material-symbols, .material-symbols-outlined,
.material-symbols-rounded, .material-symbols-sharp {{
    font-family: 'Material Symbols Rounded','Material Symbols Outlined','Material Icons Outlined','Material Icons Round','Material Icons' !important;
    letter-spacing: normal !important;
    text-transform: none !important;
    font-feature-settings: 'liga' !important;
    -webkit-font-feature-settings: 'liga' !important;
}}

[data-testid="stSidebar"] {{
    background: linear-gradient(180deg, #050505 0%, {BG} 100%) !important;
    border-right: 1px solid {LINE};
    box-shadow: 8px 0 24px rgba(0,0,0,0.55);
}}
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] p,
[data-testid="stSidebar"] span {{
    color: {TEXT} !important;
    font-family: 'Courier Prime', monospace !important;
}}

/* ── header ─────────────────────────────────────────────────────── */
.dash-header {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 1.2rem 0 0.5rem 0;
    border-bottom: 1px solid {LINE};
    margin-bottom: 1.4rem;
}}
.dash-title {{
    font-family: 'Courier Prime', monospace;
    font-size: 2.2rem;
    font-weight: 700;
    letter-spacing: 6px;
    text-transform: uppercase;
    color: {INK};
    text-shadow: 3px 3px 0 rgba(255,255,255,0.04);
}}
.dash-subtitle {{
    color: {DIM};
    font-size: 0.72rem;
    letter-spacing: 5px;
    text-transform: uppercase;
    margin-top: 0.35rem;
}}

/* ── KPI cards ──────────────────────────────────────────────────── */
.kpi-grid {{
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 1rem;
    margin-bottom: 1.4rem;
}}
.kpi-card {{
    background: {CARD};
    border: 1px solid {LINE};
    border-top: 2px solid {INK_SOFT};
    padding: 1.1rem 1rem;
    text-align: left;
    box-shadow: {SHADOW};
    position: relative;
    overflow: hidden;
}}
.kpi-card::after {{
    content: "";
    position: absolute; right: 12px; top: 12px;
    width: 8px; height: 8px; border: 1px solid {DIM_SOFT};
}}
.kpi-card .kpi-value {{
    font-family: 'DM Mono', monospace;
    font-size: 2.4rem;
    font-weight: 500;
    line-height: 1;
    color: {INK};
}}
.kpi-card .kpi-label {{
    font-family: 'DM Mono', monospace;
    font-size: 0.68rem;
    color: {DIM};
    text-transform: uppercase;
    letter-spacing: 3px;
    margin-top: 0.7rem;
}}

/* ── section titles ─────────────────────────────────────────────── */
.section-title {{
    font-family: 'DM Mono', monospace;
    font-size: 0.72rem;
    font-weight: 700;
    color: {INK};
    text-transform: uppercase;
    letter-spacing: 4px;
    border-bottom: 1px solid {LINE};
    padding-bottom: 0.5rem;
    margin: 1.6rem 0 1rem 0;
}}

/* ── tabs ───────────────────────────────────────────────────────── */
[data-testid="stTabs"] [role="tablist"] {{
    background: {SURFACE};
    padding: 0.35rem;
    gap: 0.4rem;
    border: 1px solid {LINE};
    box-shadow: {SHADOW_SM};
}}
[data-testid="stTabs"] [role="tab"] {{
    font-family: 'Courier Prime', monospace !important;
    font-weight: 700;
    font-size: 0.85rem;
    color: {DIM};
    border: none !important;
    padding: 0.55rem 1.6rem;
    text-transform: uppercase;
    letter-spacing: 2px;
}}
[data-testid="stTabs"] [role="tab"][aria-selected="true"] {{
    background: {INK} !important;
    color: {BG} !important;
    box-shadow: 3px 3px 0 rgba(255,255,255,0.08);
}}
[data-testid="stTabs"] [role="tab"]:hover {{ color: {TEXT} !important; }}

/* ── buttons ───────────────────────────────────────────────────── */
div[data-testid="stButton"] > button,
div[data-testid="stDownloadButton"] > button,
div[data-testid="stFormSubmitButton"] > button {{
    font-family: 'Courier Prime', monospace !important;
    font-weight: 700;
    font-size: 0.85rem;
    letter-spacing: 2px;
    text-transform: uppercase;
    border-radius: 0 !important;
    transition: transform 0.15s ease, box-shadow 0.15s ease;
}}
div[data-testid="stButton"] > button[kind="primary"],
div[data-testid="stDownloadButton"] > button[kind="primary"],
div[data-testid="stFormSubmitButton"] > button[kind="primary"] {{
    background: {INK} !important;
    color: {BG} !important;
    border: 1px solid {INK} !important;
    box-shadow: 4px 4px 0 rgba(255,255,255,0.08) !important;
}}
div[data-testid="stButton"] > button[kind="primary"]:hover,
div[data-testid="stDownloadButton"] > button[kind="primary"]:hover,
div[data-testid="stFormSubmitButton"] > button[kind="primary"]:hover {{
    transform: translate(-1px, -1px);
    box-shadow: 5px 5px 0 rgba(255,255,255,0.12) !important;
}}
div[data-testid="stButton"] > button[kind="secondary"] {{
    background: {CARD} !important;
    color: {TEXT} !important;
    border: 1px solid {LINE} !important;
    box-shadow: 3px 3px 0 rgba(255,255,255,0.04) !important;
}}
div[data-testid="stButton"] > button[kind="secondary"]:hover {{
    background: {CARD_ALT} !important;
    transform: translate(-1px, -1px);
}}

/* ── form / inputs ──────────────────────────────────────────────── */
[data-testid="stTextInput"] input,
[data-testid="stNumberInput"] input,
[data-testid="stTextArea"] textarea,
[data-testid="stDateInput"] input,
[data-testid="stTimeInput"] input {{
    background: {SURFACE} !important;
    color: {TEXT} !important;
    border: 1px solid {LINE} !important;
    border-radius: 0 !important;
    font-family: 'DM Mono', monospace !important;
    box-shadow: inset 2px 2px 0 rgba(0,0,0,0.35);
}}
[data-testid="stSelectbox"] > div > div,
[data-testid="stMultiSelect"] > div > div {{
    background: {SURFACE} !important;
    color: {TEXT} !important;
    border: 1px solid {LINE} !important;
    border-radius: 0 !important;
}}

/* labels */
[data-testid="stWidgetLabel"] p,
[data-baseweb="form-control-label"] p,
label p {{
    font-family: 'DM Mono', monospace !important;
    font-size: 0.72rem !important;
    letter-spacing: 2px;
    text-transform: uppercase;
    color: {DIM} !important;
}}

/* ── expander ───────────────────────────────────────────────────── */
[data-testid="stExpander"] details {{
    background: {CARD};
    border: 1px solid {LINE} !important;
    border-radius: 0;
    box-shadow: {SHADOW_SM};
}}
[data-testid="stExpander"] summary {{
    color: {INK};
    font-family: 'Courier Prime', monospace;
    font-weight: 700;
    letter-spacing: 2px;
    text-transform: uppercase;
}}

/* ── alerts ─────────────────────────────────────────────────────── */
[data-testid="stAlert"] {{
    background: {CARD} !important;
    border-radius: 0;
    border: 1px solid {LINE};
    box-shadow: {SHADOW_SM};
    font-family: 'DM Mono', monospace;
}}

/* ── selected job callout ───────────────────────────────────────── */
.selected-job {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0.9rem 1.2rem;
    background: {CARD};
    border: 1px solid {LINE};
    border-left: 3px solid {INK};
    box-shadow: {SHADOW_SM};
    margin: 0.4rem 0 1rem 0;
}}
.selected-job small {{
    display: block;
    color: {DIM};
    font-family: 'DM Mono', monospace;
    font-size: 0.7rem;
    letter-spacing: 3px;
    text-transform: uppercase;
    margin-bottom: 0.3rem;
}}
.selected-job strong {{
    color: {INK};
    font-family: 'Courier Prime', monospace;
    font-size: 1rem;
    letter-spacing: 1px;
    text-transform: uppercase;
}}
.selected-job .count {{
    color: {INK};
    font-family: 'DM Mono', monospace;
    font-weight: 500;
    font-size: 1rem;
    letter-spacing: 2px;
}}

/* ── brand block in header ─────────────────────────────────────── */
.brand-inline {{
    display: flex;
    align-items: center;
    gap: 1rem;
}}
.brand-inline img {{
    height: 42px;
    filter: invert(1) grayscale(1);
}}

/* ── calendar ───────────────────────────────────────────────────── */
.cal-wrap {{
    border: 1px solid {LINE};
    background: {CARD};
    box-shadow: {SHADOW};
    padding: 1rem 1.1rem 1.2rem;
    margin: 0.4rem 0 1.4rem;
}}
.cal-head {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 0.9rem;
}}
.cal-head .cal-title {{
    font-family: 'Courier Prime', monospace;
    font-size: 1.1rem;
    letter-spacing: 4px;
    text-transform: uppercase;
    color: {INK};
}}
.cal-grid {{
    display: grid;
    grid-template-columns: repeat(7, 1fr);
    gap: 4px;
}}
.cal-dow {{
    font-family: 'DM Mono', monospace;
    font-size: 0.62rem;
    color: {DIM};
    letter-spacing: 3px;
    text-transform: uppercase;
    padding: 0.35rem 0.5rem;
    border-bottom: 1px solid {LINE};
    text-align: left;
}}
.cal-cell {{
    min-height: 88px;
    padding: 0.4rem 0.5rem 0.5rem;
    background: {SURFACE};
    border: 1px solid {LINE_SOFT};
    box-shadow: 2px 2px 0 rgba(255,255,255,0.02);
    display: flex;
    flex-direction: column;
    gap: 0.35rem;
}}
.cal-cell.empty {{ background: transparent; border-color: transparent; box-shadow: none; }}
.cal-cell.today {{ border: 1px solid {INK}; box-shadow: 3px 3px 0 rgba(255,255,255,0.08); }}
.cal-cell .cal-day {{
    font-family: 'DM Mono', monospace;
    font-size: 0.72rem;
    color: {DIM};
    letter-spacing: 1px;
}}
.cal-cell.today .cal-day {{ color: {INK}; font-weight: 700; }}
.cal-events {{ display: flex; flex-direction: column; gap: 3px; }}
.cal-chip {{
    display: flex;
    align-items: center;
    gap: 6px;
    font-family: 'DM Mono', monospace;
    font-size: 0.62rem;
    color: {INK_SOFT};
    letter-spacing: 0.5px;
    line-height: 1.1;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}}
.cal-chip .cal-dot {{
    display: inline-block;
    width: 8px; height: 8px;
    flex: 0 0 8px;
}}
.cal-dot.brief    {{ background: transparent; border: 1px solid {INK}; }}
.cal-dot.debrief  {{ background: {DIM}; }}
.cal-dot.pit      {{ background: {INK}; transform: rotate(45deg); }}
.cal-dot.deadline {{ background: {INK}; height: 2px; width: 12px; flex-basis: 12px; }}
.cal-dot.prez     {{ background: transparent; border: 1px dashed {INK_SOFT}; }}
.cal-more {{
    font-family: 'DM Mono', monospace;
    font-size: 0.6rem;
    color: {DIM};
    letter-spacing: 0.5px;
}}
.cal-legend {{
    display: flex; flex-wrap: wrap; gap: 1.1rem;
    padding: 0.7rem 0 0.2rem;
    font-family: 'DM Mono', monospace;
    font-size: 0.66rem;
    color: {DIM};
    letter-spacing: 1.5px;
    text-transform: uppercase;
}}
.cal-legend .cal-chip {{ font-size: 0.66rem; color: {DIM}; }}

/* ── hide Streamlit chrome ───────────────────────────────────────── */
#MainMenu, footer, header {{ visibility: hidden; }}
</style>
"""

# ─────────────────────────────────────────────────────────────────────────────
# Data helpers
# ─────────────────────────────────────────────────────────────────────────────

def _parse_excel_date(v) -> str | None:
    if v is None:
        return None
    try:
        if pd.isna(v):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(v, (datetime, pd.Timestamp)):
        ts = pd.Timestamp(v)
        if ts.year < 1950:
            return None
        return ts.strftime("%Y-%m-%d")
    if isinstance(v, date):
        return v.strftime("%Y-%m-%d")
    s = str(v).strip()
    return None if s in ("", "nan", "NaT", "None") else s[:10]


def _parse_pct(v) -> int:
    if v is None:
        return 0
    try:
        if pd.isna(v):
            return 0
    except (TypeError, ValueError):
        pass
    if isinstance(v, (datetime, pd.Timestamp)):
        return 0
    if isinstance(v, (int, float)):
        if 0 < v <= 1:
            return int(round(v * 100))
        return max(0, min(100, int(v)))
    return 0


def import_from_excel(file_obj=None) -> pd.DataFrame:
    """Parse a PLANNING TEAM Excel file (Ykone or Balti layout) into a clean DataFrame."""
    raw = pd.read_excel(file_obj, sheet_name="PLANNING TEAM", header=None)
    hdr_row = None
    for i, row in raw.iterrows():
        vals = [str(x).strip() for x in row.values]
        if "CLIENT" in vals and "JOB" in vals:
            hdr_row = i
            break
    if hdr_row is None:
        return pd.DataFrame(columns=ALL_COLS)

    df = pd.read_excel(file_obj, sheet_name="PLANNING TEAM", header=hdr_row)
    df.columns.name = None
    df = df.loc[:, ~df.columns.str.startswith("Unnamed")]
    df = df.dropna(how="all").reset_index(drop=True)

    if "CLIENT" in df.columns:
        df["CLIENT"] = df["CLIENT"].ffill()

    rows: list[dict] = []
    for _, row in df.iterrows():
        client = str(row.get("CLIENT", "") or "").strip()
        job    = str(row.get("JOB",    "") or "").strip()
        if not client and not job:
            continue
        rec = {
            "id":              str(uuid.uuid4())[:8],
            "CLIENT":          client,
            "JOB":             job,
            "TEAM CREA 1":     str(row.get("TEAM CREA 1",  "") or "").strip(),
            "TEAM CREA 2":     str(row.get("TEAM CREA 2",  "") or "").strip(),
            "CM":              str(row.get("CM",           "") or "").strip(),
            "ACCOUNTS":        str(row.get("ACCOUNTS",     "") or "").strip(),
            "BRIEFING CRA":    _parse_excel_date(row.get("BRIEFING CRA")),
            "DEBRIEF":         _parse_excel_date(row.get("DEBRIEF")),
            "PIT STOP":        str(row.get("PIT STOP",     "") or "").strip(),
            "% D'AVANCEMENT":  _parse_pct(row.get("% D'AVANCEMENT")),
            "DEADLINE":        _parse_excel_date(row.get("DEADLINE")),
            "PREZ CLIENT":     _parse_excel_date(row.get("PREZ CLIENT")),
            "ETAT CREA":       str(row.get("ETAT CREA",   "") or "EN COURS").strip() or "EN COURS",
            "OBSERVATIONS":    str(row.get("OBSERVATIONS", "") or "").strip(),
            "COMPLETED":       False,
        }
        rows.append(rec)

    return pd.DataFrame(rows, columns=ALL_COLS)


def load_data() -> pd.DataFrame:
    if not DATA_FILE.exists():
        return pd.DataFrame(columns=ALL_COLS)
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        records = json.load(f)
    if not records:
        return pd.DataFrame(columns=ALL_COLS)
    df = pd.DataFrame(records)
    for col in ALL_COLS:
        if col not in df.columns:
            df[col] = None
    return df[ALL_COLS]


def save_data(df: pd.DataFrame) -> None:
    if not FS_WRITABLE:
        return
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    df.to_json(DATA_FILE, orient="records", indent=2, force_ascii=False)


def df_to_json_bytes(df: pd.DataFrame) -> bytes:
    return df.to_json(orient="records", indent=2, force_ascii=False).encode("utf-8")


def df_to_excel_bytes(df: pd.DataFrame) -> bytes:
    export_cols = ["CLIENT", "JOB"] + EDITABLE_COLS + ["COMPLETED"]
    out = df.copy()
    for c in export_cols:
        if c not in out.columns:
            out[c] = ""
    out = out[export_cols].copy()
    if "DEBRIEF" in out.columns:
        out["DEBRIEF"] = out["DEBRIEF"].apply(_debrief_display)
    if "% D'AVANCEMENT" in out.columns:
        out["% D'AVANCEMENT"] = pd.to_numeric(out["% D'AVANCEMENT"], errors="coerce").fillna(0).astype(int)
    out = out.fillna("")

    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        out.to_excel(writer, sheet_name="PLANNING TEAM", index=False)
        ws = writer.sheets["PLANNING TEAM"]
        from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

        hdr_fill = PatternFill(start_color="0A0A0A", end_color="0A0A0A", fill_type="solid")
        hdr_font = Font(name="Courier New", size=10, bold=True, color="FFFFFF")
        thin_border = Border(
            left=Side(style="thin", color="333333"),
            right=Side(style="thin", color="333333"),
            top=Side(style="thin", color="333333"),
            bottom=Side(style="thin", color="AAAAAA"),
        )
        for cell in ws[1]:
            cell.fill = hdr_fill
            cell.font = hdr_font
            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
            cell.border = thin_border

        data_font = Font(name="Courier New", size=10)
        alt_fill = PatternFill(start_color="F5F5F5", end_color="F5F5F5", fill_type="solid")
        wrap_align = Alignment(vertical="center", wrap_text=True)
        for row_idx in range(2, ws.max_row + 1):
            for cell in ws[row_idx]:
                cell.font = data_font
                cell.alignment = wrap_align
            if row_idx % 2 == 0:
                for cell in ws[row_idx]:
                    cell.fill = alt_fill

        for col_letter, width in {
            "A": 16, "B": 30, "C": 18, "D": 18, "E": 14, "F": 14, "G": 14,
            "H": 22, "I": 14, "J": 14, "K": 14, "L": 14, "M": 14, "N": 30, "O": 12,
        }.items():
            ws.column_dimensions[col_letter].width = width

        ws.row_dimensions[1].height = 32
        ws.freeze_panes = "C2"

    buf.seek(0)
    return buf.getvalue()


def _parse_debriefs(v) -> list[str]:
    if not v or str(v).strip() in ("", "None", "nan", "NaT"):
        return []
    return [x.strip() for x in str(v).split(";") if x.strip()]


def _debrief_display(v) -> str:
    items = _parse_debriefs(v)
    if not items:
        return ""
    return "\n".join(f"#{i + 1} — {d}" for i, d in enumerate(items))


def get_df() -> pd.DataFrame:
    if "df" not in st.session_state:
        st.session_state.df = load_data()
    return st.session_state.df


# ─────────────────────────────────────────────────────────────────────────────
# Chart helpers
# ─────────────────────────────────────────────────────────────────────────────

def _plotly_layout(**kwargs) -> dict:
    defaults = dict(
        paper_bgcolor=BG,
        plot_bgcolor=SURFACE,
        font=dict(color=TEXT, family="Courier Prime, monospace", size=12),
        margin=dict(l=20, r=20, t=30, b=20),
        showlegend=True,
        legend=dict(font=dict(color=TEXT), bgcolor="rgba(0,0,0,0)"),
    )
    defaults.update(kwargs)
    return defaults


ETAT_COLOR = {
    "COMPLETED": "#f2f2f2",
    "BAT OK":    "#c8c8c8",
    "EN COURS":  "#8f8f8f",
    "ATT BAT":   "#5c5c5c",
    "ANNULÉ":    "#3a3a3a",
}


# ─────────────────────────────────────────────────────────────────────────────
# ── RENDER ──────────────────────────────────────────────────────────────────
# ─────────────────────────────────────────────────────────────────────────────
st.markdown(STYLE, unsafe_allow_html=True)

col_logo, col_title = st.columns([1, 6])
with col_logo:
    if LOGO_FILE.exists():
        st.image(str(LOGO_FILE), width=140)
with col_title:
    st.markdown(
        '<div class="dash-header">'
        '  <div>'
        '    <div class="dash-title">Task Dispatch</div>'
        '    <div class="dash-subtitle">Internal Job & Debrief Ledger</div>'
        '  </div>'
        '</div>',
        unsafe_allow_html=True,
    )

df = get_df()

# ─────────────────────────────────────────────────────────────────────────────
# Sidebar
# ─────────────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(
        f'<div style="font-family:\'Courier Prime\',monospace;'
        f'font-size:1.3rem;font-weight:700;letter-spacing:5px;'
        f'text-transform:uppercase;color:{INK};'
        f'border-bottom:1px solid {LINE};padding-bottom:0.5rem;">YKONE · DESK</div>',
        unsafe_allow_html=True,
    )

    clients = ["All"] + sorted({r for r in df["CLIENT"].dropna() if r})
    sel_client = st.selectbox("Filter by Client", clients, key="sb_client")

    etats = ["All"] + ETAT_OPTIONS
    sel_etat = st.selectbox("Filter by État", etats, key="sb_etat")

    show_completed = st.checkbox("Show Completed", value=True, key="cb_completed")

    st.markdown("---")

    with st.expander("Import Excel", expanded=False):
        uploaded = st.file_uploader(
            "Upload PLANNING.xlsx", type=["xlsx", "xls"], label_visibility="collapsed"
        )
        if uploaded and st.button("Import", key="btn_import"):
            st.session_state.df = import_from_excel(uploaded)
            save_data(st.session_state.df)
            st.success("Imported.")
            st.rerun()

    with st.expander("Backup / Restore", expanded=False):
        cur_df = st.session_state.get("df", pd.DataFrame(columns=ALL_COLS))
        st.download_button(
            "Download JSON backup",
            data=df_to_json_bytes(cur_df),
            file_name="planning_backup.json",
            mime="application/json",
            key="btn_dl",
        )
        restore_file = st.file_uploader(
            "Upload JSON backup", type=["json"], key="restore_upload", label_visibility="collapsed"
        )
        if restore_file and st.button("Restore", key="btn_restore"):
            records = json.load(restore_file)
            st.session_state.df = pd.DataFrame(records)
            save_data(st.session_state.df)
            st.success("Restored.")
            st.rerun()

    if not FS_WRITABLE:
        st.caption("Read-only filesystem — use backups to persist changes.")

    st.markdown("---")
    total    = len(df)
    done     = int(df["COMPLETED"].astype(bool).sum()) if "COMPLETED" in df.columns else 0
    pct_done = round(done / total * 100) if total else 0
    st.markdown(f"**{done}/{total}** jobs completed")
    st.progress(pct_done / 100)

# ─────────────────────────────────────────────────────────────────────────────
# KPI cards
# ─────────────────────────────────────────────────────────────────────────────
today = date.today()


def _count_overdue(frame: pd.DataFrame) -> int:
    n = 0
    for _, row in frame.iterrows():
        dl = row.get("DEADLINE")
        if dl and str(dl) not in ("None", "NaT", "nan", ""):
            try:
                d = datetime.strptime(str(dl)[:10], "%Y-%m-%d").date()
                if d < today and not bool(row.get("COMPLETED", False)):
                    n += 1
            except ValueError:
                pass
    return n


total_jobs  = len(df)
completed   = int(df["COMPLETED"].astype(bool).sum()) if "COMPLETED" in df.columns else 0
in_progress = int(df["ETAT CREA"].isin(["EN COURS", "ATT BAT"]).sum()) if "ETAT CREA" in df.columns else 0
overdue     = _count_overdue(df)

st.markdown(
    f"""<div class="kpi-grid">
  <div class="kpi-card"><div class="kpi-value">{total_jobs}</div>
    <div class="kpi-label">Total Jobs</div></div>
  <div class="kpi-card"><div class="kpi-value" style="color:{OK}">{completed}</div>
    <div class="kpi-label">Completed</div></div>
  <div class="kpi-card"><div class="kpi-value" style="color:{WARN}">{in_progress}</div>
    <div class="kpi-label">In Progress</div></div>
  <div class="kpi-card"><div class="kpi-value" style="color:{BAD}">{overdue}</div>
    <div class="kpi-label">Overdue</div></div>
</div>""",
    unsafe_allow_html=True,
)

# ─────────────────────────────────────────────────────────────────────────────
# Filter view
# ─────────────────────────────────────────────────────────────────────────────
view = df.copy()
if sel_client != "All":
    view = view[view["CLIENT"] == sel_client]
if sel_etat != "All":
    view = view[view["ETAT CREA"] == sel_etat]
if not show_completed:
    view = view[~view["COMPLETED"].astype(bool)]

# ─────────────────────────────────────────────────────────────────────────────
# Tabs
# ─────────────────────────────────────────────────────────────────────────────
tab_plan, tab_viz = st.tabs(["  PLANNING BOARD  ", "  PROGRESS & ANALYTICS  "])

# ═════════════════════════════════════════════════════════════════════════════
# TAB 1 — PLANNING BOARD
# ═════════════════════════════════════════════════════════════════════════════
with tab_plan:

    with st.expander("+  Add New Job", expanded=False):
        with st.form("add_form", clear_on_submit=True):
            c1, c2 = st.columns(2)
            new_client = c1.text_input("CLIENT *")
            new_job    = c2.text_input("JOB *")

            c3, c4, c5, c6 = st.columns(4)
            new_tc1 = c3.text_input("TEAM CREA 1", placeholder="Choose members")
            new_tc2 = c4.text_input("TEAM CREA 2", placeholder="Choose members")
            new_cm  = c5.text_input("CM",          placeholder="Choose members")
            new_acc = c6.text_input("ACCOUNTS",    placeholder="Choose members")

            c7, c8, c9 = st.columns(3)
            with c7:
                new_brief_d = st.date_input("BRIEFING CRA", value=None, key="d_brief")
                new_brief_t = st.time_input("Heure", value=None, key="t_brief", label_visibility="collapsed")
            with c8:
                new_debrief_d = st.date_input("DEBRIEF #1", value=None, key="d_debrief")
                new_debrief_t = st.time_input("Heure", value=None, key="t_debrief", label_visibility="collapsed")
            with c9:
                new_pit_d = st.date_input("PIT STOP", value=None, key="d_pit")
                new_pit_t = st.time_input("Heure", value=None, key="t_pit", label_visibility="collapsed")

            c10, c11, c_pct = st.columns(3)
            with c10:
                new_dl_d = st.date_input("DEADLINE", value=None, key="d_dl")
                new_dl_t = st.time_input("Heure", value=None, key="t_dl", label_visibility="collapsed")
            with c11:
                new_prez_d = st.date_input("PREZ CLIENT", value=None, key="d_prez")
                new_prez_t = st.time_input("Heure", value=None, key="t_prez", label_visibility="collapsed")
            with c_pct:
                new_pct = st.number_input("% D'AVANCEMENT", 0, 100, 0)

            c12, c13 = st.columns(2)
            new_etat = c12.selectbox("ETAT CREA", ETAT_OPTIONS)
            new_obs  = c13.text_area("OBSERVATIONS")

            submitted = st.form_submit_button("+  Add Job", type="primary", use_container_width=True)

        if submitted:
            if not new_client.strip() or not new_job.strip():
                st.error("CLIENT and JOB are required.")
            else:
                new_row = {
                    "id":              str(uuid.uuid4())[:8],
                    "CLIENT":          new_client.strip(),
                    "JOB":             new_job.strip(),
                    "TEAM CREA 1":     new_tc1.strip(),
                    "TEAM CREA 2":     new_tc2.strip(),
                    "CM":              new_cm.strip(),
                    "ACCOUNTS":        new_acc.strip(),
                    "BRIEFING CRA":    f"{new_brief_d} {new_brief_t}"     if new_brief_d   else None,
                    "DEBRIEF":         f"{new_debrief_d} {new_debrief_t}" if new_debrief_d else "",
                    "PIT STOP":        f"{new_pit_d} {new_pit_t}"         if new_pit_d     else None,
                    "% D'AVANCEMENT":  int(new_pct),
                    "DEADLINE":        f"{new_dl_d} {new_dl_t}"           if new_dl_d      else None,
                    "PREZ CLIENT":     f"{new_prez_d} {new_prez_t}"       if new_prez_d    else None,
                    "ETAT CREA":       new_etat,
                    "OBSERVATIONS":    new_obs.strip(),
                    "COMPLETED":       False,
                }
                st.session_state.df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
                save_data(st.session_state.df)
                st.success(f"'{new_job.strip()}' added.")
                st.rerun()

    with st.expander("+  Manage Debriefs", expanded=False):
        active = df[(df["CLIENT"].fillna("") != "") | (df["JOB"].fillna("") != "")].copy()
        if len(active) == 0:
            st.info("No jobs yet.")
        else:
            active["_label"] = active["CLIENT"].fillna("") + "  —  " + active["JOB"].fillna("")
            job_labels = active["_label"].tolist()
            sel_label  = st.selectbox("Select a job to manage its debriefs", job_labels, key="debrief_job_sel")
            sel_row    = active[active["_label"] == sel_label].iloc[0]
            orig_idx   = sel_row.name
            existing   = _parse_debriefs(sel_row["DEBRIEF"])
            count      = len(existing)

            st.markdown(
                f'<div class="selected-job">'
                f'  <div><small>Selected job</small>'
                f'    <strong>{sel_row["CLIENT"]} — {sel_row["JOB"]}</strong></div>'
                f'  <span class="count">{count} debrief{"s" if count != 1 else ""}</span>'
                f'</div>',
                unsafe_allow_html=True,
            )
            if count >= 3:
                st.warning(f"{count} debriefs logged — consider stopping further requests from this client.")

            tab_modify, tab_add = st.tabs(["  MODIFY A DEBRIEF  ", "  ADD A NEW DEBRIEF  "])

            with tab_modify:
                if not existing:
                    st.info("No debriefs recorded yet for this job.")
                else:
                    options = [f"#{i + 1}  —  {d}" for i, d in enumerate(existing)]
                    sel_opt = st.selectbox("Which debrief?", options, key="mod_sel")
                    sel_i   = options.index(sel_opt)
                    current = existing[sel_i]
                    try:
                        dt_obj = datetime.strptime(current[:16], "%Y-%m-%d %H:%M")
                        init_d = dt_obj.date()
                        init_t = dt_obj.time()
                    except ValueError:
                        init_d, init_t = None, None

                    mc1, mc2 = st.columns(2)
                    mod_date = mc1.date_input("New date", value=init_d, key="mod_d")
                    mod_time = mc2.time_input("New time", value=init_t, key="mod_t")

                    if st.button("Save changes", type="primary", key="btn_mod"):
                        existing[sel_i] = f"{mod_date} {mod_time}"
                        df.at[orig_idx, "DEBRIEF"] = ";".join(existing)
                        st.session_state.df = df
                        save_data(df)
                        st.success(f"Debrief #{sel_i + 1} updated.")
                        st.rerun()

            with tab_add:
                ac1, ac2 = st.columns(2)
                new_db_date = ac1.date_input("Date", key="add_db_d")
                new_db_time = ac2.time_input("Heure", key="add_db_t")

                if st.button(f"+  Log Debrief #{count + 1}", type="primary", key="btn_add_db"):
                    existing.append(f"{new_db_date} {new_db_time}")
                    df.at[orig_idx, "DEBRIEF"] = ";".join(existing)
                    st.session_state.df = df
                    save_data(df)
                    st.success(f"Debrief #{len(existing)} logged.")
                    st.rerun()

    with st.expander("+  Add Timeline", expanded=False):
        st.caption("Coming soon.")

    st.markdown('<div class="section-title">Job Board</div>', unsafe_allow_html=True)

    DISPLAY_COLS = ["CLIENT", "JOB"] + EDITABLE_COLS + ["COMPLETED"]

    grid_df = view[DISPLAY_COLS].copy().reset_index(drop=True)
    if "DEBRIEF" in grid_df.columns:
        grid_df["DEBRIEF"] = grid_df["DEBRIEF"].apply(_debrief_display)
    if "% D'AVANCEMENT" in grid_df.columns:
        grid_df["% D'AVANCEMENT"] = pd.to_numeric(grid_df["% D'AVANCEMENT"], errors="coerce").fillna(0).astype(int)
    if "COMPLETED" in grid_df.columns:
        grid_df["COMPLETED"] = grid_df["COMPLETED"].astype(bool)
    # AgGrid can't decode PyArrow LargeUtf8 — cast text columns to plain object.
    for _c in grid_df.columns:
        if _c in ("% D'AVANCEMENT", "COMPLETED"):
            continue
        grid_df[_c] = grid_df[_c].astype(object).where(grid_df[_c].notna(), "")

    gob = GridOptionsBuilder.from_dataframe(grid_df)
    gob.configure_default_column(
        editable=True, sortable=True, resizable=True,
        filter="agTextColumnFilter", floatingFilter=True,
        filterParams={"buttons": ["reset", "apply"], "closeOnApply": True, "debounceMs": 200},
        menuTabs=["filterMenuTab", "generalMenuTab", "columnsMenuTab"],
    )

    gob.configure_column("CLIENT", editable=False, pinned="left", width=140)
    gob.configure_column("JOB", width=220)
    gob.configure_column("TEAM CREA 1", width=140)
    gob.configure_column("TEAM CREA 2", width=140)
    gob.configure_column("CM", width=110)
    gob.configure_column("ACCOUNTS", width=110)
    gob.configure_column("BRIEFING CRA", width=125)
    gob.configure_column(
        "DEBRIEF", editable=False, width=210, wrapText=True, autoHeight=True,
        cellStyle=JsCode("""
            function(params) {
                return {
                    'white-space': 'pre-line',
                    'line-height': '1.4',
                    'padding-top': '4px',
                    'padding-bottom': '4px',
                    'font-size': '12px',
                    'font-family': 'DM Mono, monospace'
                };
            }
        """),
    )
    gob.configure_column("PIT STOP", width=140)
    gob.configure_column(
        "% D'AVANCEMENT", width=120, type=["numericColumn"], filter="agNumberColumnFilter",
        cellStyle=JsCode("""
            function(params) {
                const v = params.value;
                let bg, color;
                if (v >= 100) { bg = '#f2f2f2'; color = '#0a0a0a'; }
                else if (v >= 60) { bg = '#8f8f8f'; color = '#0a0a0a'; }
                else { bg = '#3a3a3a'; color = '#f2f2f2'; }
                return {
                    'background': bg, 'color': color,
                    'textAlign': 'center', 'fontWeight': '700',
                    'fontFamily': 'DM Mono, monospace'
                };
            }
        """),
    )
    gob.configure_column("DEADLINE", width=125)
    gob.configure_column("PREZ CLIENT", width=125)
    gob.configure_column(
        "ETAT CREA", width=130,
        cellEditor="agSelectCellEditor",
        cellEditorParams={"values": ETAT_OPTIONS},
    )
    gob.configure_column("OBSERVATIONS", width=200)
    gob.configure_column("COMPLETED", header_name="DONE", width=90, cellRenderer="agCheckboxCellRenderer")

    gob.configure_grid_options(
        domLayout="normal",
        rowHeight=36, headerHeight=42, floatingFiltersHeight=34,
        suppressMovableColumns=False, animateRows=True,
        getRowStyle=JsCode("""
            function(params) {
                if (!params.data) return null;
                if (params.data.COMPLETED === true || params.data.COMPLETED === 'true') return null;
                const dl = params.data['DEADLINE'];
                if (!dl) return null;
                const dlStr = String(dl).slice(0, 10);
                const dlDate = new Date(dlStr + 'T00:00:00');
                if (isNaN(dlDate.getTime())) return null;
                const today = new Date();
                today.setHours(0, 0, 0, 0);
                const diffDays = Math.floor((dlDate - today) / (1000 * 60 * 60 * 24));
                if (diffDays >= 0 && diffDays <= 3) {
                    return {
                        'background-color': '#2a2a2a',
                        'color': '#ffffff',
                        'font-weight': '600'
                    };
                }
                return null;
            }
        """),
    )

    grid_options = gob.build()

    custom_css = {
        ".ag-theme-alpine-dark": {
            "--ag-background-color": "#131313",
            "--ag-foreground-color": "#f2f2f2",
            "--ag-header-background-color": "#0a0a0a",
            "--ag-header-foreground-color": "#f2f2f2",
            "--ag-odd-row-background-color": "#181818",
            "--ag-row-hover-color": "rgba(255,255,255,0.06)",
            "--ag-border-color": "#2a2a2a",
            "--ag-header-column-separator-color": "#2a2a2a",
            "--ag-selected-row-background-color": "rgba(255,255,255,0.10)",
            "--ag-font-family": "'Courier Prime', 'DM Mono', monospace",
            "--ag-font-size": "13px",
        },
        ".ag-header-cell": {
            "font-weight": "700 !important",
            "letter-spacing": "2px",
            "text-transform": "uppercase",
            "font-size": "0.7rem !important",
        },
        ".ag-header": {"border-bottom": "2px solid #f2f2f2 !important"},
        ".ag-menu": {"background-color": "#131313 !important", "border": "1px solid #2e2e2e !important", "color": "#f2f2f2 !important"},
        ".ag-filter, .ag-set-filter": {"background-color": "#131313 !important", "color": "#f2f2f2 !important"},
        ".ag-set-filter-list, .ag-virtual-list-viewport": {"background-color": "#131313 !important"},
        ".ag-set-filter-item": {"color": "#f2f2f2 !important", "padding": "4px 8px !important"},
        ".ag-set-filter-item:hover": {"background-color": "rgba(255,255,255,0.08) !important"},
        ".ag-checkbox-input-wrapper.ag-checked::after": {"color": "#f2f2f2 !important"},
        ".ag-filter-apply-panel button": {
            "background": "#f2f2f2 !important",
            "color": "#0a0a0a !important",
            "border": "none !important",
            "padding": "5px 12px !important",
            "border-radius": "0 !important",
            "font-weight": "700 !important",
            "letter-spacing": "1px",
            "text-transform": "uppercase",
        },
        ".ag-icon-menu, .ag-icon-filter": {"color": "#f2f2f2 !important"},
        ".ag-floating-filter": {"background-color": "#0f0f0f !important", "border-top": "1px solid #2a2a2a !important"},
        ".ag-floating-filter-input input, .ag-input-field-input": {
            "background-color": "#161616 !important",
            "color": "#f2f2f2 !important",
            "border": "1px solid #333 !important",
            "border-radius": "0 !important",
            "padding": "3px 6px !important",
            "font-family": "'DM Mono', monospace !important",
            "font-size": "12px !important",
        },
        ".ag-floating-filter-input input::placeholder": {"color": "#666 !important"},
    }

    grid_response = AgGrid(
        grid_df,
        gridOptions=grid_options,
        update_mode=GridUpdateMode.VALUE_CHANGED,
        data_return_mode=DataReturnMode.AS_INPUT,
        fit_columns_on_grid_load=False,
        allow_unsafe_jscode=True,
        theme="alpine-dark",
        custom_css=custom_css,
        height=520,
        key="aggrid_board",
        reload_data=False,
    )

    edited_df = pd.DataFrame(grid_response["data"])

    _orig_indices = view.index.tolist()
    for _i, _orig_idx in enumerate(_orig_indices):
        if _i >= len(edited_df):
            break
        for _col in DISPLAY_COLS:
            _val = edited_df.iloc[_i][_col]
            if isinstance(_val, date):
                _val = _val.isoformat()
            df.at[_orig_idx, _col] = _val
    st.session_state.df = df

    btn_cols = st.columns([1.4, 1.6, 1.6, 2.4])
    with btn_cols[0]:
        st.download_button(
            "Save as Excel",
            data=df_to_excel_bytes(df),
            file_name=f"planning_ykone_{date.today().isoformat()}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary",
            use_container_width=True,
            on_click=lambda: save_data(st.session_state.df),
            key="btn_save_xlsx",
        )
    with btn_cols[1]:
        if st.button("Mark All as Completed", use_container_width=True):
            for orig_idx in view.index.tolist():
                df.at[orig_idx, "COMPLETED"]      = True
                df.at[orig_idx, "ETAT CREA"]      = "COMPLETED"
                df.at[orig_idx, "% D'AVANCEMENT"] = 100
            st.session_state.df = df
            save_data(df)
            st.success("Marked as completed.")
            st.rerun()
    with btn_cols[2]:
        if st.button("Unmark Selected", use_container_width=True):
            for i, orig_idx in enumerate(view.index.tolist()):
                if i < len(edited_df) and edited_df.iloc[i]["COMPLETED"]:
                    df.at[orig_idx, "COMPLETED"] = False
                    if df.at[orig_idx, "ETAT CREA"] == "COMPLETED":
                        df.at[orig_idx, "ETAT CREA"] = "EN COURS"
            st.session_state.df = df
            save_data(df)
            st.rerun()

    with st.expander("Danger Zone", expanded=False):
        if st.button("Delete ALL completed jobs", type="secondary"):
            st.session_state.df = df[~df["COMPLETED"].astype(bool)].reset_index(drop=True)
            save_data(st.session_state.df)
            st.success("Deleted.")
            st.rerun()

# ═════════════════════════════════════════════════════════════════════════════
# TAB 2 — PROGRESS & ANALYTICS
# ═════════════════════════════════════════════════════════════════════════════
with tab_viz:

    if len(df) == 0:
        st.info("No data yet. Add jobs in the Planning Board tab.")
        st.stop()

    # ── Calendar view ───────────────────────────────────────────────────────
    def _collect_events(frame: pd.DataFrame) -> dict[date, list[dict]]:
        buckets: dict[date, list[dict]] = {}
        field_map = [
            ("BRIEFING CRA", "brief",    "BRIEF"),
            ("PIT STOP",     "pit",      "PIT"),
            ("DEADLINE",     "deadline", "DEADLINE"),
            ("PREZ CLIENT",  "prez",     "PREZ"),
        ]
        for _, row in frame.iterrows():
            label = f"{row.get('CLIENT', '?')} · {row.get('JOB', '?')}"
            for col, kind, tag in field_map:
                v = row.get(col)
                if v and str(v) not in ("", "nan", "None", "NaT"):
                    try:
                        d = datetime.strptime(str(v)[:10], "%Y-%m-%d").date()
                        buckets.setdefault(d, []).append({"kind": kind, "tag": tag, "label": label})
                    except ValueError:
                        pass
            for db in _parse_debriefs(row.get("DEBRIEF")):
                try:
                    d = datetime.strptime(db[:10], "%Y-%m-%d").date()
                    buckets.setdefault(d, []).append({"kind": "debrief", "tag": "DEBRIEF", "label": label})
                except ValueError:
                    pass
        return buckets

    events = _collect_events(df)

    st.markdown('<div class="section-title">Calendar</div>', unsafe_allow_html=True)

    cal_key = "cal_anchor"
    if cal_key not in st.session_state:
        st.session_state[cal_key] = date.today().replace(day=1)
    anchor: date = st.session_state[cal_key]

    nav_prev, nav_lbl, nav_next, nav_today = st.columns([1, 5, 1, 1])
    if nav_prev.button("‹", key="cal_prev", use_container_width=True):
        prev_month = anchor.month - 1 or 12
        prev_year  = anchor.year - 1 if anchor.month == 1 else anchor.year
        st.session_state[cal_key] = date(prev_year, prev_month, 1)
        st.rerun()
    nav_lbl.markdown(
        f'<div style="text-align:center;font-family:\'Courier Prime\',monospace;'
        f'font-size:1.1rem;letter-spacing:5px;text-transform:uppercase;'
        f'color:{INK};padding-top:0.35rem;">'
        f'{anchor.strftime("%B %Y").upper()}</div>',
        unsafe_allow_html=True,
    )
    if nav_next.button("›", key="cal_next", use_container_width=True):
        next_month = anchor.month + 1 if anchor.month < 12 else 1
        next_year  = anchor.year + 1 if anchor.month == 12 else anchor.year
        st.session_state[cal_key] = date(next_year, next_month, 1)
        st.rerun()
    if nav_today.button("Today", key="cal_today", use_container_width=True):
        st.session_state[cal_key] = date.today().replace(day=1)
        st.rerun()

    today_d = date.today()
    dow_labels = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]
    weeks = calendar.Calendar(firstweekday=0).monthdatescalendar(anchor.year, anchor.month)

    cells_html = []
    cells_html.append('<div class="cal-grid">')
    for lbl in dow_labels:
        cells_html.append(f'<div class="cal-dow">{lbl}</div>')
    for week in weeks:
        for day in week:
            if day.month != anchor.month:
                cells_html.append('<div class="cal-cell empty"></div>')
                continue
            classes = "cal-cell" + (" today" if day == today_d else "")
            evs = events.get(day, [])
            visible = evs[:3]
            hidden = len(evs) - len(visible)
            chips = "".join(
                f'<div class="cal-chip" title="{ev["tag"]} — {ev["label"]}">'
                f'<span class="cal-dot {ev["kind"]}"></span>{ev["label"][:16]}</div>'
                for ev in visible
            )
            more = f'<div class="cal-more">+{hidden} more</div>' if hidden > 0 else ""
            cells_html.append(
                f'<div class="{classes}">'
                f'<div class="cal-day">{day.day:02d}</div>'
                f'<div class="cal-events">{chips}{more}</div>'
                f'</div>'
            )
    cells_html.append('</div>')

    legend_html = (
        '<div class="cal-legend">'
        '<span class="cal-chip"><span class="cal-dot brief"></span>Briefing CRA</span>'
        '<span class="cal-chip"><span class="cal-dot debrief"></span>Debrief</span>'
        '<span class="cal-chip"><span class="cal-dot pit"></span>Pit stop</span>'
        '<span class="cal-chip"><span class="cal-dot deadline"></span>Deadline</span>'
        '<span class="cal-chip"><span class="cal-dot prez"></span>Prez client</span>'
        '</div>'
    )

    st.markdown(f'<div class="cal-wrap">{"".join(cells_html)}{legend_html}</div>', unsafe_allow_html=True)

    r1a, r1b = st.columns(2)

    with r1a:
        st.markdown('<div class="section-title">Status Distribution</div>', unsafe_allow_html=True)
        ec = df["ETAT CREA"].value_counts().reset_index()
        ec.columns = ["ETAT", "COUNT"]
        fig_donut = go.Figure(go.Pie(
            labels=ec["ETAT"],
            values=ec["COUNT"],
            hole=0.58,
            marker=dict(
                colors=[ETAT_COLOR.get(e, "#7a7a7a") for e in ec["ETAT"]],
                line=dict(color=BG, width=3),
            ),
            textinfo="percent+label",
            textfont=dict(color=TEXT, size=12, family="Courier Prime, monospace"),
            hovertemplate="<b>%{label}</b><br>%{value} jobs (%{percent})<extra></extra>",
        ))
        fig_donut.update_layout(**_plotly_layout(height=330, showlegend=False))
        st.plotly_chart(fig_donut, use_container_width=True)

    with r1b:
        st.markdown('<div class="section-title">Jobs per Client</div>', unsafe_allow_html=True)
        cc = df.groupby("CLIENT").size().reset_index(name="COUNT").sort_values("COUNT")
        fig_bar = go.Figure(go.Bar(
            x=cc["COUNT"],
            y=cc["CLIENT"],
            orientation="h",
            marker=dict(
                color=cc["COUNT"],
                colorscale=[[0, "#3a3a3a"], [0.5, "#8f8f8f"], [1, "#f2f2f2"]],
                showscale=False,
            ),
            text=cc["COUNT"],
            textposition="outside",
            textfont=dict(color=TEXT, family="DM Mono, monospace"),
            hovertemplate="<b>%{y}</b><br>%{x} jobs<extra></extra>",
        ))
        fig_bar.update_layout(**_plotly_layout(
            height=330,
            showlegend=False,
            xaxis=dict(showgrid=False, color=DIM),
            yaxis=dict(showgrid=False, color=TEXT),
        ))
        st.plotly_chart(fig_bar, use_container_width=True)

    st.markdown('<div class="section-title">% Avancement per Job (top 20)</div>', unsafe_allow_html=True)

    prog = df.copy()
    prog["% D'AVANCEMENT"] = pd.to_numeric(prog["% D'AVANCEMENT"], errors="coerce").fillna(0)
    prog = prog[prog["% D'AVANCEMENT"] > 0].copy()
    prog["label"] = prog["CLIENT"].fillna("?") + "  ·  " + prog["JOB"].fillna("?")
    prog = prog.sort_values("% D'AVANCEMENT").tail(20)

    if len(prog):
        bar_colors = []
        for _, row in prog.iterrows():
            p = row["% D'AVANCEMENT"]
            if bool(row.get("COMPLETED", False)) or p == 100:
                bar_colors.append("#f2f2f2")
            elif p >= 60:
                bar_colors.append("#8f8f8f")
            else:
                bar_colors.append("#4a4a4a")

        fig_prog = go.Figure(go.Bar(
            x=prog["% D'AVANCEMENT"],
            y=prog["label"],
            orientation="h",
            marker=dict(color=bar_colors, line=dict(color=BG, width=0.5)),
            text=[f"{p:.0f}%" for p in prog["% D'AVANCEMENT"]],
            textposition="outside",
            textfont=dict(color=TEXT, family="DM Mono, monospace"),
            hovertemplate="<b>%{y}</b><br>%{x}%<extra></extra>",
        ))
        fig_prog.add_vline(x=50, line_color=DIM, line_dash="dot", line_width=1)
        fig_prog.update_layout(**_plotly_layout(
            height=max(280, len(prog) * 32),
            showlegend=False,
            xaxis=dict(range=[0, 115], showgrid=False, title="% Avancement", color=DIM),
            yaxis=dict(showgrid=False, color=TEXT),
        ))
        st.plotly_chart(fig_prog, use_container_width=True)
    else:
        st.info("Set % D'Avancement values in the Planning Board to see this chart.")

    st.markdown('<div class="section-title">Debriefs Ledger</div>', unsafe_allow_html=True)

    deb_rows: list[dict] = []
    for _, row in df.iterrows():
        cnt = len(_parse_debriefs(row.get("DEBRIEF")))
        if cnt > 0:
            deb_rows.append({
                "label": f"{row.get('CLIENT', '?')}  ·  {row.get('JOB', '?')}",
                "debrief_count": cnt,
            })

    if not deb_rows:
        st.info("Log debriefs in the Planning Board to see this chart.")
    else:
        deb_df = pd.DataFrame(deb_rows).sort_values("debrief_count")
        deb_colors = ["#f2f2f2" if c >= 3 else "#8f8f8f" for c in deb_df["debrief_count"]]
        fig_deb = go.Figure(go.Bar(
            x=deb_df["debrief_count"],
            y=deb_df["label"],
            orientation="h",
            marker=dict(color=deb_colors, line=dict(color=BG, width=0.5)),
            text=deb_df["debrief_count"],
            textposition="outside",
            textfont=dict(color=TEXT, family="DM Mono, monospace"),
            hovertemplate="<b>%{y}</b><br>%{x} debriefs<extra></extra>",
        ))
        max_val = int(deb_df["debrief_count"].max())
        if max_val >= 3:
            fig_deb.add_vline(
                x=3, line_color=INK, line_dash="dash", line_width=1.5,
                annotation_text="Warning threshold (3)",
                annotation_font_color=INK, annotation_position="top right",
            )
        fig_deb.update_layout(**_plotly_layout(
            height=max(280, len(deb_df) * 32),
            showlegend=False,
            xaxis=dict(title="Number of debriefs", showgrid=False, color=DIM,
                       dtick=1, range=[0, max_val + 1.5]),
            yaxis=dict(showgrid=False, color=TEXT),
        ))
        st.plotly_chart(fig_deb, use_container_width=True)

        total_debriefs = int(deb_df["debrief_count"].sum())
        over_threshold = int((deb_df["debrief_count"] >= 3).sum())
        avg_debriefs   = deb_df["debrief_count"].mean()

        m1, m2, m3 = st.columns(3)
        m1.markdown(
            f'<div class="kpi-card"><div class="kpi-value">{total_debriefs}</div>'
            f'<div class="kpi-label">Total Debriefs</div></div>',
            unsafe_allow_html=True,
        )
        m2.markdown(
            f'<div class="kpi-card"><div class="kpi-value" style="color:{WARN}">{avg_debriefs:.1f}</div>'
            f'<div class="kpi-label">Avg / Job</div></div>',
            unsafe_allow_html=True,
        )
        m3.markdown(
            f'<div class="kpi-card"><div class="kpi-value" style="color:{BAD}">{over_threshold}</div>'
            f'<div class="kpi-label">≥ 3 Debriefs</div></div>',
            unsafe_allow_html=True,
        )
