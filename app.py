"""
Quebec Pipeline Tracker
A professional VC deal flow platform with traction scoring.
Inspired by Legora and Brightspark design aesthetics.
"""

import streamlit as st
import pandas as pd
import sqlite3
import json
import sys
import os
from datetime import datetime, date
from pathlib import Path
import plotly.express as px
import plotly.graph_objects as go

# Add project root to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ============================================================================
# CONFIGURATION & THEME
# ============================================================================

st.set_page_config(
    page_title="QC Pipeline",
    page_icon="◆",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Professional Light Theme - Investissement Québec Inspired
st.markdown("""
<style>
    :root {
        --bg-primary: #ffffff;
        --bg-secondary: #f5f7fa;
        --bg-card: #ffffff;
        --border-color: #d0d5dd;
        --text-primary: #1a1f36;
        --text-secondary: #3c4257;
        --text-muted: #697386;
        --accent-primary: #00875a;
        --accent-hover: #006644;
        --accent-light: #e6f4ef;
        --blue-dark: #003366;
        --blue-medium: #0052cc;
    }
    
    /* Base */
    .stApp { background: var(--bg-secondary); }
    .main .block-container { padding: 2rem 3rem; max-width: 1400px; }
    #MainMenu, footer, header {visibility: hidden;}
    .stDeployButton {display: none;}
    
    /* Typography - High Contrast */
    h1 { 
        font-size: 1.75rem !important; 
        font-weight: 700 !important; 
        color: var(--blue-dark) !important; 
        letter-spacing: -0.01em;
        margin-bottom: 0.25rem !important;
    }
    h2 { 
        font-size: 1.25rem !important; 
        font-weight: 600 !important; 
        color: var(--blue-dark) !important;
        margin-top: 1.5rem !important;
    }
    h3 { 
        font-size: 1rem !important; 
        font-weight: 600 !important; 
        color: var(--text-primary) !important; 
    }
    p, .stMarkdown p { 
        color: var(--text-secondary) !important; 
        font-size: 0.95rem !important;
        line-height: 1.6 !important;
    }
    span, label { color: var(--text-primary) !important; }
    
    /* Sidebar */
    [data-testid="stSidebar"] { 
        background: var(--bg-primary) !important; 
        border-right: 1px solid var(--border-color);
    }
    [data-testid="stSidebar"] .stButton > button {
        background: transparent !important; 
        border: none !important; 
        color: var(--text-secondary) !important;
        text-align: left !important; 
        padding: 0.75rem 1rem !important; 
        border-radius: 6px !important;
        font-weight: 500 !important;
        font-size: 0.9rem !important;
        transition: all 0.15s ease !important;
    }
    [data-testid="stSidebar"] .stButton > button:hover { 
        background: var(--accent-light) !important; 
        color: var(--accent-primary) !important; 
    }
    
    /* Metric Cards */
    .metric-card {
        background: var(--bg-primary);
        border: 1px solid var(--border-color); 
        border-radius: 8px; 
        padding: 1.25rem 1.5rem;
        box-shadow: 0 1px 2px rgba(0,0,0,0.05);
    }
    .metric-card:hover { 
        border-color: var(--accent-primary);
    }
    .metric-value { 
        font-size: 2rem; 
        font-weight: 700; 
        color: var(--blue-dark); 
        line-height: 1.2; 
    }
    .metric-label { 
        font-size: 0.8rem; 
        font-weight: 500; 
        color: var(--text-muted); 
        text-transform: uppercase; 
        letter-spacing: 0.03em; 
        margin-top: 0.5rem; 
    }
    
    /* Company Cards */
    .company-card {
        background: var(--bg-primary);
        border: 1px solid var(--border-color); 
        border-radius: 8px; 
        padding: 1rem 1.25rem;
        margin-bottom: 0.5rem; 
        transition: all 0.15s ease;
    }
    .company-card:hover { 
        border-color: var(--accent-primary);
        box-shadow: 0 2px 8px rgba(0, 135, 90, 0.1);
    }
    .company-name { 
        font-size: 0.95rem; 
        font-weight: 600; 
        color: var(--text-primary); 
        margin-bottom: 0.5rem; 
    }
    .company-meta { 
        font-size: 0.8rem; 
        color: var(--text-muted); 
        display: flex; 
        gap: 1rem; 
        margin-top: 0.5rem; 
    }
    
    /* Tags */
    .tag { 
        display: inline-flex; 
        padding: 0.25rem 0.5rem; 
        border-radius: 4px; 
        font-size: 0.7rem; 
        font-weight: 600; 
        margin-right: 0.375rem;
        letter-spacing: 0.02em;
    }
    .tag-sector { 
        background: #e8f4fc; 
        color: var(--blue-medium); 
    }
    .tag-stage { 
        background: var(--accent-light); 
        color: var(--accent-primary); 
    }
    
    /* Pipeline Columns */
    .pipeline-column { 
        background: var(--bg-primary); 
        border: 1px solid var(--border-color); 
        border-radius: 8px; 
        padding: 1rem; 
        min-height: 450px; 
    }
    .pipeline-header { 
        font-size: 0.75rem; 
        font-weight: 700; 
        color: var(--text-muted); 
        text-transform: uppercase; 
        letter-spacing: 0.05em; 
        padding-bottom: 0.75rem; 
        margin-bottom: 0.75rem; 
        border-bottom: 2px solid var(--bg-secondary); 
        display: flex; 
        justify-content: space-between;
        align-items: center;
    }
    .pipeline-count { 
        background: var(--bg-secondary); 
        color: var(--text-primary);
        padding: 0.2rem 0.5rem; 
        border-radius: 4px; 
        font-size: 0.75rem;
        font-weight: 600;
    }
    
    /* Primary Buttons - Green IQ Style */
    .stButton > button { 
        background: var(--accent-primary) !important; 
        color: white !important; 
        border: none !important; 
        border-radius: 6px !important; 
        padding: 0.5rem 1.25rem !important; 
        font-weight: 600 !important;
        font-size: 0.875rem !important;
        transition: all 0.15s ease !important;
    }
    .stButton > button:hover { 
        background: var(--accent-hover) !important;
    }
    
    /* Inputs */
    .stTextInput > div > div > input, 
    .stSelectbox > div > div > div, 
    .stTextArea > div > div > textarea,
    .stMultiSelect > div > div > div {
        background: var(--bg-primary) !important; 
        border: 1px solid var(--border-color) !important; 
        border-radius: 6px !important; 
        color: var(--text-primary) !important;
        font-size: 0.9rem !important;
    }
    .stTextInput > div > div > input:focus,
    .stTextArea > div > div > textarea:focus {
        border-color: var(--accent-primary) !important;
        box-shadow: 0 0 0 2px var(--accent-light) !important;
    }
    
    /* Labels */
    .stTextInput label, .stSelectbox label, .stTextArea label, .stMultiSelect label {
        color: var(--text-primary) !important;
        font-weight: 500 !important;
        font-size: 0.875rem !important;
    }
    
    /* Tabs */
    .stTabs [data-baseweb="tab-list"] { 
        background: transparent; 
        border-bottom: 2px solid var(--border-color);
        gap: 0;
    }
    .stTabs [data-baseweb="tab"] { 
        color: var(--text-muted) !important; 
        padding: 0.75rem 1.25rem;
        font-weight: 500;
        font-size: 0.9rem;
    }
    .stTabs [aria-selected="true"] { 
        color: var(--accent-primary) !important; 
        border-bottom: 2px solid var(--accent-primary) !important;
        background: transparent !important;
        font-weight: 600;
    }
    
    /* Progress bars */
    .stProgress > div > div { background: var(--bg-secondary) !important; border-radius: 4px; }
    .stProgress > div > div > div { background: var(--accent-primary) !important; border-radius: 4px; }
    
    /* Dividers */
    hr { border-color: var(--border-color) !important; margin: 1.5rem 0 !important; }
    
    /* Logo area */
    .logo-container { padding: 1.25rem 1rem; margin-bottom: 0.5rem; border-bottom: 1px solid var(--border-color); }
    .logo-text { 
        font-size: 1.1rem; 
        font-weight: 700; 
        color: var(--blue-dark); 
        letter-spacing: -0.01em; 
    }
    .logo-subtext { 
        font-size: 0.65rem; 
        color: var(--text-muted); 
        text-transform: uppercase; 
        letter-spacing: 0.06em; 
        margin-top: 0.25rem; 
    }
    
    /* Data frames */
    .stDataFrame { border-radius: 8px !important; border: 1px solid var(--border-color) !important; }
    
    /* File uploader */
    .stFileUploader > div { 
        background: var(--bg-primary) !important;
        border: 2px dashed var(--border-color) !important;
        border-radius: 8px !important;
    }
    
    /* Metrics widget */
    [data-testid="metric-container"] {
        background: var(--bg-primary);
        border: 1px solid var(--border-color);
        border-radius: 8px;
        padding: 1rem;
    }
    [data-testid="metric-container"] label { color: var(--text-muted) !important; }
    [data-testid="metric-container"] div[data-testid="stMetricValue"] { color: var(--blue-dark) !important; }
    
    /* Slider */
    .stSlider > div > div { background: var(--bg-secondary) !important; }
    .stSlider > div > div > div > div { background: var(--accent-primary) !important; }
    
    /* Checkbox */
    .stCheckbox label span { color: var(--text-primary) !important; }
    
    /* Expander */
    .streamlit-expanderHeader { 
        background: var(--bg-primary) !important; 
        border: 1px solid var(--border-color) !important;
        border-radius: 6px !important;
        color: var(--text-primary) !important;
        font-weight: 500 !important;
    }
    
    /* Info/Warning boxes */
    .stAlert { border-radius: 6px !important; }
    
    /* Caption text */
    .stCaption, small { color: var(--text-muted) !important; }
</style>
""", unsafe_allow_html=True)

# ============================================================================
# DATABASE & HELPERS
# ============================================================================

DB_PATH = Path("pipeline_data.db")
PIPELINE_STAGES = ["Prospect", "Premier Contact", "Due Diligence", "Préparation CI", "Comité", "Closing", "Pass"]
STAGE_COLORS = {"Prospect": "#0052cc", "Premier Contact": "#0065ff", "Due Diligence": "#36b37e", "Préparation CI": "#00875a", "Comité": "#006644", "Closing": "#00875a", "Pass": "#97a0af"}

def init_database():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS companies (
        id INTEGER PRIMARY KEY, company_id TEXT UNIQUE, name TEXT, description TEXT, website TEXT, hq_location TEXT,
        year_founded TEXT, employees INTEGER, employee_history TEXT, first_financing_size REAL, first_financing_date TEXT,
        last_financing_size REAL, last_financing_date TEXT, total_raised REAL, last_valuation REAL, last_valuation_date TEXT,
        iq_sector TEXT, iq_team TEXT, stage_entreprise TEXT, verticals TEXT, primary_industry TEXT, ownership_status TEXT,
        financing_status TEXT, active_investors TEXT, former_investors TEXT, primary_contact TEXT, watchlist TEXT,
        secteurs_dpcriii TEXT, pipeline_stage TEXT DEFAULT 'Prospect', priority INTEGER DEFAULT 0, notes TEXT, tags TEXT,
        assigned_to TEXT, next_action TEXT, next_action_date TEXT, created_at TEXT, updated_at TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS activities (id INTEGER PRIMARY KEY, company_id TEXT, activity_type TEXT, description TEXT, created_at TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS traction_snapshots (id INTEGER PRIMARY KEY, company_id TEXT, snapshot_date TEXT, job_postings_count INTEGER, news_mentions_30d INTEGER, news_sentiment_avg REAL, website_status INTEGER, has_blog INTEGER, has_careers_page INTEGER, tech_stack TEXT, github_stars INTEGER, github_forks INTEGER, raw_data TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS growth_scores (id INTEGER PRIMARY KEY, company_id TEXT, score_date TEXT, hiring_velocity_score REAL, funding_momentum_score REAL, news_buzz_score REAL, web_presence_score REAL, tech_activity_score REAL, growth_score REAL, growth_trend TEXT, confidence REAL, factors_positive TEXT, factors_negative TEXT)""")
    conn.commit()
    conn.close()

def get_connection(): return sqlite3.connect(DB_PATH)

def safe_str(val):
    if val is None or pd.isna(val): return None
    if isinstance(val, bytes): return val.decode('utf-8', errors='ignore')
    return str(val)

def safe_float(val):
    if val is None or pd.isna(val): return None
    try: return float(val)
    except: return None

def safe_int(val):
    if val is None or pd.isna(val): return None
    try: return int(float(val))
    except: return None

def parse_date(val):
    if val is None or pd.isna(val): return None
    try:
        if isinstance(val, datetime): return val.strftime('%Y-%m-%d')
        if hasattr(val, 'strftime'): return val.strftime('%Y-%m-%d')
        s = str(val)
        if s and s != 'nan' and s != 'NaT': return s[:10]
    except: pass
    return None

def clean_dataframe(df):
    for col in df.columns:
        if df[col].dtype == object:
            df[col] = df[col].apply(lambda x: x.decode('utf-8', errors='ignore') if isinstance(x, bytes) else x)
    return df

def import_pitchbook_data(uploaded_file):
    try:
        df = pd.read_excel(uploaded_file, header=7)
        conn = get_connection()
        now = datetime.now().isoformat()
        imported, skipped = 0, 0
        for _, row in df.iterrows():
            cid = safe_str(row.get('Company ID'))
            if not cid or cid == 'nan': continue
            existing = pd.read_sql("SELECT id FROM companies WHERE company_id = ?", conn, params=(cid,))
            if len(existing) > 0: skipped += 1; continue
            cursor = conn.cursor()
            cursor.execute("""INSERT INTO companies (company_id, name, description, website, hq_location, year_founded, employees, employee_history, first_financing_size, first_financing_date, last_financing_size, last_financing_date, total_raised, last_valuation, last_valuation_date, iq_sector, iq_team, stage_entreprise, verticals, primary_industry, ownership_status, financing_status, active_investors, former_investors, primary_contact, watchlist, secteurs_dpcriii, pipeline_stage, priority, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (cid, safe_str(row.get('Companies')), safe_str(row.get('Description')), safe_str(row.get('Website')), safe_str(row.get('HQ Location')), safe_str(row.get('Year Founded')), safe_int(row.get('Employees')), safe_str(row.get('Employee History')), safe_float(row.get('First Financing Size')), parse_date(row.get('First Financing Date')), safe_float(row.get('Last Financing Size')), parse_date(row.get('Last Financing Date')), safe_float(row.get('Total Raised')), safe_float(row.get('Last Known Valuation')), parse_date(row.get('Last Known Valuation Date')), safe_str(row.get('IQ - Secteur')), safe_str(row.get('Équipe IQ')), safe_str(row.get("Stade de l'entreprise")), safe_str(row.get('Verticals')), safe_str(row.get('Primary Industry Sector')), safe_str(row.get('Ownership Status')), safe_str(row.get('Company Financing Status')), safe_str(row.get('Active Investors')), safe_str(row.get('Former Investors')), safe_str(row.get('Primary Contact')), safe_str(row.get('Watchlist - DPCRIII')), safe_str(row.get('Secteurs  - DPCRIII')), 'Prospect', 0, now, now))
            imported += 1
        conn.commit()
        conn.close()
        return imported, skipped
    except Exception as e:
        st.error(f"Import error: {e}")
        return 0, 0

def get_all_companies(filters=None):
    conn = get_connection()
    query = "SELECT * FROM companies WHERE 1=1"
    params = []
    if filters:
        if filters.get('search'):
            query += " AND (name LIKE ? OR description LIKE ? OR notes LIKE ?)"
            s = f"%{filters['search']}%"; params.extend([s,s,s])
        if filters.get('sectors'): query += f" AND iq_sector IN ({','.join(['?']*len(filters['sectors']))})" ; params.extend(filters['sectors'])
        if filters.get('stages'): query += f" AND stage_entreprise IN ({','.join(['?']*len(filters['stages']))})" ; params.extend(filters['stages'])
        if filters.get('pipeline_stages'): query += f" AND pipeline_stage IN ({','.join(['?']*len(filters['pipeline_stages']))})" ; params.extend(filters['pipeline_stages'])
        if filters.get('watchlist_only'): query += " AND watchlist IS NOT NULL AND watchlist != ''"
    query += " ORDER BY updated_at DESC"
    df = pd.read_sql(query, conn, params=params)
    conn.close()
    return clean_dataframe(df)

def get_company(company_id):
    conn = get_connection()
    df = pd.read_sql("SELECT * FROM companies WHERE company_id = ?", conn, params=(company_id,))
    conn.close()
    if len(df) > 0: return clean_dataframe(df).iloc[0]
    return None

def update_company(company_id, updates):
    conn = get_connection()
    updates['updated_at'] = datetime.now().isoformat()
    set_clause = ', '.join([f"{k} = ?" for k in updates.keys()])
    conn.cursor().execute(f"UPDATE companies SET {set_clause} WHERE company_id = ?", list(updates.values()) + [company_id])
    conn.commit()
    conn.close()

def add_activity(company_id, activity_type, description):
    conn = get_connection()
    conn.cursor().execute("INSERT INTO activities (company_id, activity_type, description, created_at) VALUES (?,?,?,?)", (company_id, activity_type, description, datetime.now().isoformat()))
    conn.commit()
    conn.close()

def get_activities(company_id):
    conn = get_connection()
    df = pd.read_sql("SELECT * FROM activities WHERE company_id = ? ORDER BY created_at DESC", conn, params=(company_id,))
    conn.close()
    return clean_dataframe(df)

def get_unique_values(column):
    conn = get_connection()
    df = pd.read_sql(f"SELECT DISTINCT {column} FROM companies WHERE {column} IS NOT NULL AND {column} != ''", conn)
    conn.close()
    return clean_dataframe(df)[column].tolist()

# ============================================================================
# UI COMPONENTS
# ============================================================================

def render_metric_card(value, label):
    st.markdown(f'<div class="metric-card"><div class="metric-value">{value}</div><div class="metric-label">{label}</div></div>', unsafe_allow_html=True)

def render_company_card(company):
    name = safe_str(company['name']) or '—'
    priority = "★" * (company.get('priority', 0) or 0)
    sector = safe_str(company.get('iq_sector')) or ''
    stage = safe_str(company.get('stage_entreprise')) or ''
    raised = company.get('total_raised')
    raised_str = f"${raised:.1f}M" if pd.notna(raised) and raised else "—"
    emp = company.get('employees')
    emp_str = f"{int(emp)} emp" if pd.notna(emp) else "—"
    st.markdown(f'<div class="company-card"><div class="company-name">{name} <span style="color:#d97706;font-weight:400">{priority}</span></div><div><span class="tag tag-sector">{sector}</span><span class="tag tag-stage">{stage}</span></div><div class="company-meta"><span>{raised_str}</span><span>{emp_str}</span></div></div>', unsafe_allow_html=True)

# ============================================================================
# PAGES
# ============================================================================

def page_dashboard():
    st.markdown("# Portfolio Overview")
    st.markdown('<p style="color:#5c6370;margin-top:-0.5rem">Real-time pipeline metrics</p>', unsafe_allow_html=True)
    df = get_all_companies()
    if len(df) == 0: st.info("◆ Import data in Settings"); return
    
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1: render_metric_card(len(df), "Companies")
    with col2: render_metric_card(len(df[~df['pipeline_stage'].isin(['Pass','Closing'])]), "Active Pipeline")
    with col3: render_metric_card(f"${df['total_raised'].sum():.0f}M", "Total Raised")
    with col4: render_metric_card(f"{df['employees'].mean():.0f}", "Avg Employees")
    with col5: render_metric_card(len(df[df['priority']>=3]), "High Priority")
    
    st.markdown("---")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("### Pipeline by Stage")
        stage_counts = df['pipeline_stage'].fillna('Prospect').value_counts()
        ordered = [(s, stage_counts.get(s,0)) for s in PIPELINE_STAGES]
        fig = go.Figure(go.Bar(x=[x[0] for x in ordered], y=[x[1] for x in ordered], marker_color=[STAGE_COLORS.get(x[0],'#00875a') for x in ordered], text=[x[1] for x in ordered], textposition='outside', textfont=dict(color='#1a1f36', size=12)))
        fig.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font_color='#3c4257', height=350, margin=dict(l=20,r=20,t=20,b=80), xaxis=dict(showgrid=False,tickangle=45,tickfont=dict(size=11)), yaxis=dict(showgrid=True,gridcolor='#e5e7eb',tickfont=dict(size=11)))
        st.plotly_chart(fig, use_container_width=True)
    with col2:
        st.markdown("### By Sector")
        sector_counts = df['iq_sector'].value_counts().head(8)
        fig = go.Figure(go.Pie(labels=sector_counts.index, values=sector_counts.values, hole=0.55, marker=dict(colors=['#003366','#0052cc','#0065ff','#36b37e','#00875a','#006644','#5243aa','#97a0af']), textfont=dict(size=11)))
        fig.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font_color='#3c4257', height=350, margin=dict(l=20,r=20,t=20,b=20), legend=dict(font=dict(size=11)))
        st.plotly_chart(fig, use_container_width=True)

def page_pipeline():
    st.markdown("# Deal Pipeline")
    df = get_all_companies()
    if len(df) == 0: st.info("◆ Import data first"); return
    cols = st.columns(len(PIPELINE_STAGES))
    for idx, stage in enumerate(PIPELINE_STAGES):
        with cols[idx]:
            sc = df[df['pipeline_stage']==stage]
            st.markdown(f'<div class="pipeline-header"><span>{stage}</span><span class="pipeline-count">{len(sc)}</span></div>', unsafe_allow_html=True)
            for _, c in sc.head(8).iterrows():
                render_company_card(c)
                if st.button("Open", key=f"o_{c['company_id']}", use_container_width=True):
                    st.session_state['selected_company'] = c['company_id']
                    st.session_state['page'] = 'detail'
                    st.rerun()

def page_companies():
    st.markdown("# Companies")
    with st.sidebar:
        st.markdown("### Filters")
        search = st.text_input("🔍 Search")
        sectors = get_unique_values('iq_sector')
        sel_sectors = st.multiselect("Sector", sectors)
        sel_pipeline = st.multiselect("Pipeline", PIPELINE_STAGES)
    filters = {'search': search or None, 'sectors': sel_sectors or None, 'pipeline_stages': sel_pipeline or None}
    df = get_all_companies(filters)
    st.markdown(f"**{len(df)} companies**")
    for _, c in df.iterrows():
        cols = st.columns([3,2,1.5,1.5,1])
        with cols[0]: st.markdown(f"**{safe_str(c['name'])}**")
        with cols[1]: st.write(safe_str(c['pipeline_stage']) or 'Prospect')
        with cols[2]: r = c.get('total_raised'); st.write(f"${r:.1f}M" if pd.notna(r) else "—")
        with cols[3]: e = c.get('employees'); st.write(f"{int(e)}" if pd.notna(e) else "—")
        with cols[4]:
            if st.button("→", key=f"v_{c['company_id']}"):
                st.session_state['selected_company'] = c['company_id']
                st.session_state['page'] = 'detail'
                st.rerun()

def page_detail():
    cid = st.session_state.get('selected_company')
    if not cid: st.warning("No company selected"); return
    c = get_company(cid)
    if c is None: st.error("Not found"); return
    col1, col2 = st.columns([5,1])
    with col1: st.markdown(f"# {safe_str(c['name'])}")
    with col2:
        if st.button("← Back"): st.session_state['page'] = 'companies'; st.rerun()
    
    tab1, tab2, tab3 = st.tabs(["Profile", "Tracking", "Activity"])
    with tab1:
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("### Info")
            st.write(f"**Sector:** {safe_str(c.get('iq_sector')) or '—'}")
            st.write(f"**Location:** {safe_str(c.get('hq_location')) or '—'}")
            st.write(f"**Employees:** {c.get('employees') or '—'}")
        with col2:
            st.markdown("### Financing")
            r = c.get('total_raised'); st.write(f"**Raised:** ${r:.2f}M" if pd.notna(r) else "**Raised:** —")
            v = c.get('last_valuation'); st.write(f"**Valuation:** ${v:.2f}M" if pd.notna(v) else "**Valuation:** —")
        st.markdown("### Description")
        st.write(safe_str(c.get('description')) or '—')
    
    with tab2:
        col1, col2 = st.columns(2)
        curr = safe_str(c.get('pipeline_stage')) or 'Prospect'
        if curr not in PIPELINE_STAGES: curr = 'Prospect'
        with col1:
            new_stage = st.selectbox("Pipeline Stage", PIPELINE_STAGES, index=PIPELINE_STAGES.index(curr))
            new_priority = st.slider("Priority", 0, 5, c.get('priority',0) or 0)
        with col2:
            new_action = st.text_input("Next Action", safe_str(c.get('next_action')) or '')
            new_assigned = st.text_input("Assigned To", safe_str(c.get('assigned_to')) or '')
        new_notes = st.text_area("Notes", safe_str(c.get('notes')) or '', height=150)
        if st.button("💾 Save", type="primary"):
            update_company(cid, {'pipeline_stage': new_stage, 'priority': new_priority, 'next_action': new_action, 'assigned_to': new_assigned, 'notes': new_notes})
            if new_stage != curr: add_activity(cid, 'Stage Change', f"Moved to {new_stage}")
            st.success("Saved!"); st.rerun()
    
    with tab3:
        col1, col2 = st.columns([3,1])
        with col1: desc = st.text_input("Log activity")
        with col2: atype = st.selectbox("Type", ["Note","Call","Email","Meeting"])
        if st.button("Add") and desc: add_activity(cid, atype, desc); st.rerun()
        st.markdown("---")
        for _, a in get_activities(cid).iterrows():
            st.markdown(f"**{safe_str(a['activity_type'])}:** {safe_str(a['description'])} — {safe_str(a['created_at'])[:10] if a['created_at'] else ''}")

def page_traction():
    st.markdown("# Traction Tracker")
    st.markdown('<p style="color:#5c6370">Growth signals and scoring</p>', unsafe_allow_html=True)
    try:
        from traction.scraper import TractionScraper, GrowthScorer
        traction_ok = True
    except ImportError as e:
        st.error(f"Missing module: {e}")
        st.info("Run: `pip install beautifulsoup4 feedparser requests`")
        return
    
    tab1, tab2 = st.tabs(["🏆 Scores", "🔍 Analyze"])
    with tab1:
        conn = get_connection()
        try:
            df = pd.read_sql("""SELECT gs.company_id, c.name, c.iq_sector, gs.growth_score, gs.confidence FROM growth_scores gs JOIN companies c ON gs.company_id = c.company_id WHERE gs.id IN (SELECT MAX(id) FROM growth_scores GROUP BY company_id) ORDER BY gs.growth_score DESC""", conn)
            df = clean_dataframe(df)
        except: df = pd.DataFrame()
        conn.close()
        if len(df) == 0: st.info("No scores yet. Use Analyze tab."); return
        fig = go.Figure(go.Bar(y=df['name'].head(10), x=df['growth_score'].head(10), orientation='h', marker_color='#00875a', textfont=dict(color='#1a1f36')))
        fig.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font_color='#3c4257', height=400, yaxis=dict(autorange='reversed',tickfont=dict(size=11)), xaxis=dict(range=[0,100], gridcolor='#e5e7eb',tickfont=dict(size=11)))
        st.plotly_chart(fig, use_container_width=True)
    
    with tab2:
        conn = get_connection()
        companies = clean_dataframe(pd.read_sql("SELECT company_id, name, website FROM companies ORDER BY name", conn))
        conn.close()
        if len(companies) == 0: st.info("Import companies first"); return
        opts = {r['name']: r['company_id'] for _, r in companies.iterrows()}
        sel = st.selectbox("Select Company", list(opts.keys()))
        cid = opts[sel]
        c = get_company(cid)
        st.write(f"**Website:** {safe_str(c.get('website')) if c else '—'}")
        if st.button("🔍 Scan", type="primary"):
            with st.spinner("Scanning..."):
                scraper = TractionScraper()
                scraper.collect_traction_snapshot(cid, sel, safe_str(c.get('website')) if c else None)
                scorer = GrowthScorer()
                score = scorer.calculate_growth_score(cid)
            st.success("Done!")
            st.metric("Growth Score", f"{score.get('growth_score',0):.1f}/100")

def page_settings():
    st.markdown("# Settings")
    st.markdown("### Import Data")
    f = st.file_uploader("PitchBook Excel", type=['xlsx'])
    if f and st.button("Import", type="primary"):
        with st.spinner("Importing..."): i, s = import_pitchbook_data(f)
        st.success(f"✓ {i} imported, {s} skipped")
    st.markdown("---")
    df = get_all_companies()
    col1, col2 = st.columns(2)
    with col1: st.metric("Companies", len(df))
    with col2: st.metric("Sectors", df['iq_sector'].nunique() if len(df)>0 else 0)
    if len(df) > 0:
        st.download_button("📥 Export CSV", df.to_csv(index=False), "export.csv", "text/csv")

# ============================================================================
# MAIN
# ============================================================================

def main():
    init_database()
    if 'page' not in st.session_state: st.session_state['page'] = 'dashboard'
    
    with st.sidebar:
        st.markdown('<div class="logo-container"><div class="logo-text">◆ QC Pipeline</div><div class="logo-subtext">Deal Flow Tracker</div></div>', unsafe_allow_html=True)
        st.markdown("---")
        if st.button("📊 Overview", use_container_width=True): st.session_state['page'] = 'dashboard'; st.rerun()
        if st.button("🎯 Pipeline", use_container_width=True): st.session_state['page'] = 'pipeline'; st.rerun()
        if st.button("🏢 Companies", use_container_width=True): st.session_state['page'] = 'companies'; st.rerun()
        if st.button("📈 Traction", use_container_width=True): st.session_state['page'] = 'traction'; st.rerun()
        if st.button("⚙️ Settings", use_container_width=True): st.session_state['page'] = 'settings'; st.rerun()
        st.markdown("---")
        st.caption("v2.2 • IQ Edition")
    
    p = st.session_state.get('page', 'dashboard')
    if p == 'dashboard': page_dashboard()
    elif p == 'pipeline': page_pipeline()
    elif p == 'companies': page_companies()
    elif p == 'detail': page_detail()
    elif p == 'traction': page_traction()
    elif p == 'settings': page_settings()

if __name__ == "__main__":
    main()
