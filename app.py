"""
Quebec Pipeline Tracker v3.0
Unified VC deal flow platform with traction scoring.
Design: Investissement Québec style
"""

import streamlit as st
import pandas as pd
import sqlite3
import json
import sys
import os
from datetime import datetime, date, timedelta
from pathlib import Path
import plotly.express as px
import plotly.graph_objects as go

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ============================================================================
# CONFIGURATION
# ============================================================================

st.set_page_config(page_title="QC Pipeline", page_icon="◆", layout="wide", initial_sidebar_state="expanded")

# Investissement Québec Inspired Theme
st.markdown("""
<style>
    :root {
        --bg-primary: #ffffff;
        --bg-secondary: #f5f7fa;
        --border-color: #d0d5dd;
        --text-primary: #1a1f36;
        --text-secondary: #3c4257;
        --text-muted: #697386;
        --navy: #003366;
        --navy-light: #004080;
        --blue: #0052cc;
        --green: #00875a;
        --green-hover: #006644;
        --green-light: #e6f4ef;
    }
    
    .stApp { background: var(--bg-secondary); }
    .main .block-container { padding: 2rem 3rem; max-width: 1400px; }
    #MainMenu, footer, header {visibility: hidden;}
    .stDeployButton {display: none;}
    
    h1 { font-size: 1.75rem !important; font-weight: 700 !important; color: var(--navy) !important; }
    h2 { font-size: 1.25rem !important; font-weight: 600 !important; color: var(--navy) !important; margin-top: 1.5rem !important; }
    h3 { font-size: 1rem !important; font-weight: 600 !important; color: var(--text-primary) !important; }
    p, .stMarkdown p { color: var(--text-secondary) !important; font-size: 0.95rem !important; line-height: 1.6 !important; }
    span, label { color: var(--text-primary) !important; }
    
    [data-testid="stSidebar"] { background: var(--bg-primary) !important; border-right: 1px solid var(--border-color); }
    [data-testid="stSidebar"] .stButton > button {
        background: transparent !important; border: none !important; color: var(--text-secondary) !important;
        text-align: left !important; padding: 0.75rem 1rem !important; border-radius: 6px !important;
        font-weight: 500 !important; font-size: 0.9rem !important;
    }
    [data-testid="stSidebar"] .stButton > button:hover { background: var(--green-light) !important; color: var(--green) !important; }
    
    .metric-card { background: var(--bg-primary); border: 1px solid var(--border-color); border-radius: 8px; padding: 1.25rem 1.5rem; }
    .metric-card:hover { border-color: var(--green); }
    .metric-value { font-size: 2rem; font-weight: 700; color: var(--navy); line-height: 1.2; }
    .metric-label { font-size: 0.8rem; font-weight: 500; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.03em; margin-top: 0.5rem; }
    
    .company-card { background: var(--bg-primary); border: 1px solid var(--border-color); border-radius: 8px; padding: 1rem 1.25rem; margin-bottom: 0.5rem; }
    .company-card:hover { border-color: var(--green); box-shadow: 0 2px 8px rgba(0,135,90,0.1); }
    .company-name { font-size: 0.95rem; font-weight: 600; color: var(--text-primary); margin-bottom: 0.5rem; }
    .company-meta { font-size: 0.8rem; color: var(--text-muted); display: flex; gap: 1rem; margin-top: 0.5rem; }
    
    .tag { display: inline-flex; padding: 0.25rem 0.5rem; border-radius: 4px; font-size: 0.7rem; font-weight: 600; margin-right: 0.375rem; }
    .tag-sector { background: #e8f4fc; color: var(--blue); }
    .tag-stage { background: var(--green-light); color: var(--green); }
    
    .pipeline-header { font-size: 0.75rem; font-weight: 700; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.05em; padding-bottom: 0.75rem; margin-bottom: 0.75rem; border-bottom: 2px solid var(--bg-secondary); display: flex; justify-content: space-between; }
    .pipeline-count { background: var(--bg-secondary); color: var(--text-primary); padding: 0.2rem 0.5rem; border-radius: 4px; font-size: 0.75rem; font-weight: 600; }
    
    .stButton > button { background: var(--green) !important; color: white !important; border: none !important; border-radius: 6px !important; padding: 0.5rem 1.25rem !important; font-weight: 600 !important; font-size: 0.875rem !important; }
    .stButton > button:hover { background: var(--green-hover) !important; }
    
    .stTextInput > div > div > input, .stSelectbox > div > div > div, .stTextArea > div > div > textarea, .stMultiSelect > div > div > div {
        background: var(--bg-primary) !important; border: 1px solid var(--border-color) !important; border-radius: 6px !important; color: var(--text-primary) !important; font-size: 0.9rem !important;
    }
    .stTextInput label, .stSelectbox label, .stTextArea label, .stMultiSelect label, .stSlider label, .stCheckbox label span {
        color: var(--text-primary) !important; font-weight: 500 !important; font-size: 0.875rem !important;
    }
    
    .stTabs [data-baseweb="tab-list"] { background: transparent; border-bottom: 2px solid var(--border-color); }
    .stTabs [data-baseweb="tab"] { color: var(--text-muted) !important; padding: 0.75rem 1.25rem; font-weight: 500; font-size: 0.9rem; }
    .stTabs [aria-selected="true"] { color: var(--green) !important; border-bottom: 2px solid var(--green) !important; font-weight: 600; }
    
    .stProgress > div > div { background: var(--bg-secondary) !important; }
    .stProgress > div > div > div { background: var(--green) !important; }
    
    hr { border-color: var(--border-color) !important; margin: 1.5rem 0 !important; }
    
    .logo-container { padding: 1.25rem 1rem; margin-bottom: 0.5rem; border-bottom: 1px solid var(--border-color); }
    .logo-text { font-size: 1.1rem; font-weight: 700; color: var(--navy); }
    .logo-subtext { font-size: 0.65rem; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.06em; margin-top: 0.25rem; }
    
    [data-testid="metric-container"] { background: var(--bg-primary); border: 1px solid var(--border-color); border-radius: 8px; padding: 1rem; }
    [data-testid="metric-container"] label { color: var(--text-muted) !important; }
    [data-testid="metric-container"] div[data-testid="stMetricValue"] { color: var(--navy) !important; }
    
    .stDataFrame { border-radius: 8px !important; border: 1px solid var(--border-color) !important; }
    .stAlert { border-radius: 6px !important; }
    .stCaption, small { color: var(--text-muted) !important; }
</style>
""", unsafe_allow_html=True)

# ============================================================================
# DATABASE
# ============================================================================

DB_PATH = Path("pipeline_data.db")
PIPELINE_STAGES = ["Prospect", "Premier Contact", "Due Diligence", "Préparation CI", "Comité", "Closing", "Pass"]
STAGE_COLORS = {"Prospect": "#0052cc", "Premier Contact": "#0065ff", "Due Diligence": "#36b37e", "Préparation CI": "#00875a", "Comité": "#006644", "Closing": "#00875a", "Pass": "#97a0af"}
NAVY = "#003366"

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
    c.execute("""CREATE TABLE IF NOT EXISTS funding_predictions (
        id INTEGER PRIMARY KEY, company_id TEXT, prediction_date TEXT, estimated_months_to_raise INTEGER,
        confidence TEXT, predicted_window TEXT, recommended_action TEXT, runway_score REAL, hiring_score REAL,
        growth_score REAL, market_score REAL, benchmark_score REAL, urgency_score REAL, primary_signals TEXT,
        all_signals TEXT, next_review_date TEXT)""")
    conn.commit()
    conn.close()

def get_connection(): return sqlite3.connect(DB_PATH)

# ============================================================================
# HELPERS
# ============================================================================

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

def clean_df(df):
    for col in df.columns:
        if df[col].dtype == object:
            df[col] = df[col].apply(lambda x: x.decode('utf-8', errors='ignore') if isinstance(x, bytes) else x)
    return df

# ============================================================================
# DATA IMPORT WITH PRE-SCREENING
# ============================================================================

def preview_pitchbook_data(uploaded_file):
    """Preview and filter data before import."""
    try:
        df = pd.read_excel(uploaded_file, header=7)
        
        # Clean column names
        df_preview = pd.DataFrame()
        df_preview['name'] = df.get('Companies', df.get('Company Name', ''))
        df_preview['website'] = df.get('Website', '')
        df_preview['employees'] = pd.to_numeric(df.get('Employees', 0), errors='coerce').fillna(0)
        df_preview['total_raised'] = pd.to_numeric(df.get('Total Raised', 0), errors='coerce').fillna(0)
        df_preview['last_financing_date'] = df.get('Last Financing Date', '')
        df_preview['iq_sector'] = df.get('IQ - Secteur', '')
        df_preview['financing_status'] = df.get('Company Financing Status', '')
        df_preview['ownership_status'] = df.get('Ownership Status', '')
        df_preview['company_id'] = df.get('Company ID', '')
        
        # Calculate flags
        df_preview['has_website'] = df_preview['website'].apply(lambda x: bool(x) and str(x).lower() not in ['nan', 'none', ''])
        df_preview['has_employees'] = df_preview['employees'] > 0
        df_preview['has_funding'] = df_preview['total_raised'] > 0
        
        # Check for recent activity (last financing within 3 years)
        def is_recent(date_val):
            if pd.isna(date_val) or not date_val: return False
            try:
                d = pd.to_datetime(date_val)
                return d > datetime.now() - timedelta(days=3*365)
            except: return False
        df_preview['recent_activity'] = df_preview['last_financing_date'].apply(is_recent)
        
        # Check for inactive status
        df_preview['potentially_inactive'] = df_preview['financing_status'].apply(
            lambda x: 'Defunct' in str(x) or 'Bankrupt' in str(x) or 'Out of Business' in str(x) if x else False
        )
        
        return df_preview, df
        
    except Exception as e:
        st.error(f"Preview error: {e}")
        return None, None

def import_filtered_data(full_df, company_ids_to_import):
    """Import only selected companies."""
    conn = get_connection()
    now = datetime.now().isoformat()
    imported, skipped = 0, 0
    
    for _, row in full_df.iterrows():
        cid = safe_str(row.get('Company ID'))
        if not cid or cid == 'nan' or cid not in company_ids_to_import:
            continue
        
        existing = pd.read_sql("SELECT id FROM companies WHERE company_id = ?", conn, params=(cid,))
        if len(existing) > 0:
            skipped += 1
            continue
        
        cursor = conn.cursor()
        cursor.execute("""INSERT INTO companies (company_id, name, description, website, hq_location, year_founded, employees, employee_history, first_financing_size, first_financing_date, last_financing_size, last_financing_date, total_raised, last_valuation, last_valuation_date, iq_sector, iq_team, stage_entreprise, verticals, primary_industry, ownership_status, financing_status, active_investors, former_investors, primary_contact, watchlist, secteurs_dpcriii, pipeline_stage, priority, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (cid, safe_str(row.get('Companies')), safe_str(row.get('Description')), safe_str(row.get('Website')), safe_str(row.get('HQ Location')), safe_str(row.get('Year Founded')), safe_int(row.get('Employees')), safe_str(row.get('Employee History')), safe_float(row.get('First Financing Size')), parse_date(row.get('First Financing Date')), safe_float(row.get('Last Financing Size')), parse_date(row.get('Last Financing Date')), safe_float(row.get('Total Raised')), safe_float(row.get('Last Known Valuation')), parse_date(row.get('Last Known Valuation Date')), safe_str(row.get('IQ - Secteur')), safe_str(row.get('Équipe IQ')), safe_str(row.get("Stade de l'entreprise")), safe_str(row.get('Verticals')), safe_str(row.get('Primary Industry Sector')), safe_str(row.get('Ownership Status')), safe_str(row.get('Company Financing Status')), safe_str(row.get('Active Investors')), safe_str(row.get('Former Investors')), safe_str(row.get('Primary Contact')), safe_str(row.get('Watchlist - DPCRIII')), safe_str(row.get('Secteurs  - DPCRIII')), 'Prospect', 0, now, now))
        imported += 1
    
    conn.commit()
    conn.close()
    return imported, skipped

# ============================================================================
# DATA ACCESS
# ============================================================================

def get_all_companies(filters=None):
    conn = get_connection()
    query = "SELECT * FROM companies WHERE 1=1"
    params = []
    if filters:
        if filters.get('search'):
            query += " AND (name LIKE ? OR description LIKE ? OR notes LIKE ?)"
            s = f"%{filters['search']}%"; params.extend([s,s,s])
        if filters.get('sectors'): query += f" AND iq_sector IN ({','.join(['?']*len(filters['sectors']))})" ; params.extend(filters['sectors'])
        if filters.get('pipeline_stages'): query += f" AND pipeline_stage IN ({','.join(['?']*len(filters['pipeline_stages']))})" ; params.extend(filters['pipeline_stages'])
        if filters.get('watchlist_only'): query += " AND watchlist IS NOT NULL AND watchlist != ''"
    query += " ORDER BY updated_at DESC"
    df = pd.read_sql(query, conn, params=params)
    conn.close()
    return clean_df(df)

def get_company(company_id):
    conn = get_connection()
    df = pd.read_sql("SELECT * FROM companies WHERE company_id = ?", conn, params=(company_id,))
    conn.close()
    if len(df) > 0: return clean_df(df).iloc[0]
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
    return clean_df(df)

def get_unique_values(column):
    conn = get_connection()
    df = pd.read_sql(f"SELECT DISTINCT {column} FROM companies WHERE {column} IS NOT NULL AND {column} != ''", conn)
    conn.close()
    return clean_df(df)[column].tolist()

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

def create_bar_chart(x_data, y_data, colors, title=""):
    fig = go.Figure(go.Bar(x=x_data, y=y_data, marker_color=colors, text=y_data, textposition='outside', textfont=dict(color=NAVY, size=12)))
    fig.update_layout(
        title=dict(text=title, font=dict(color=NAVY, size=14)),
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        font_color=NAVY, height=350, margin=dict(l=20,r=20,t=40,b=80),
        xaxis=dict(showgrid=False, tickangle=45, tickfont=dict(size=11, color=NAVY)),
        yaxis=dict(showgrid=True, gridcolor='#e5e7eb', tickfont=dict(size=11, color=NAVY))
    )
    return fig

def create_horizontal_bar(names, values, title=""):
    fig = go.Figure(go.Bar(y=names, x=values, orientation='h', marker_color='#00875a', text=[f"{v:.1f}" for v in values], textposition='inside', textfont=dict(color='white', size=12)))
    fig.update_layout(
        title=dict(text=title, font=dict(color=NAVY, size=14)),
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        font_color=NAVY, height=400, margin=dict(l=10,r=20,t=40,b=20),
        yaxis=dict(autorange='reversed', tickfont=dict(size=11, color=NAVY)),
        xaxis=dict(range=[0,100], gridcolor='#e5e7eb', tickfont=dict(size=11, color=NAVY), title='Score')
    )
    return fig

def create_pie_chart(labels, values, title=""):
    colors = ['#003366','#0052cc','#0065ff','#36b37e','#00875a','#006644','#5243aa','#97a0af']
    fig = go.Figure(go.Pie(labels=labels, values=values, hole=0.55, marker=dict(colors=colors[:len(labels)]), textfont=dict(size=11, color=NAVY)))
    fig.update_layout(
        title=dict(text=title, font=dict(color=NAVY, size=14)),
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        font_color=NAVY, height=350, margin=dict(l=20,r=20,t=40,b=20),
        legend=dict(font=dict(size=11, color=NAVY))
    )
    return fig

# ============================================================================
# PAGE: OVERVIEW
# ============================================================================

def page_overview():
    st.markdown("# Portfolio Overview")
    st.markdown("Real-time pipeline metrics and insights")
    
    df = get_all_companies()
    if len(df) == 0:
        st.info("◆ Import your PitchBook data in Settings to get started")
        return
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1: render_metric_card(len(df), "Companies")
    with col2: render_metric_card(len(df[~df['pipeline_stage'].isin(['Pass','Closing'])]), "Active Pipeline")
    with col3: render_metric_card(f"${df['total_raised'].sum():.0f}M", "Total Raised")
    with col4: render_metric_card(f"{df['employees'].mean():.0f}", "Avg Employees")
    with col5: render_metric_card(len(df[df['priority']>=3]), "High Priority")
    
    st.markdown("---")
    
    col1, col2 = st.columns(2)
    with col1:
        stage_counts = df['pipeline_stage'].fillna('Prospect').value_counts()
        ordered = [(s, stage_counts.get(s,0)) for s in PIPELINE_STAGES]
        fig = create_bar_chart([x[0] for x in ordered], [x[1] for x in ordered], [STAGE_COLORS.get(x[0],'#00875a') for x in ordered], "Pipeline by Stage")
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        sector_counts = df['iq_sector'].value_counts().head(8)
        fig = create_pie_chart(sector_counts.index.tolist(), sector_counts.values.tolist(), "By Sector")
        st.plotly_chart(fig, use_container_width=True)

# ============================================================================
# PAGE: PIPELINE
# ============================================================================

def page_pipeline():
    st.markdown("# Deal Pipeline")
    st.markdown("Track companies through your investment process")
    
    df = get_all_companies()
    if len(df) == 0: st.info("◆ Import data first"); return
    
    cols = st.columns(len(PIPELINE_STAGES))
    for idx, stage in enumerate(PIPELINE_STAGES):
        with cols[idx]:
            sc = df[df['pipeline_stage']==stage]
            st.markdown(f'<div class="pipeline-header"><span>{stage}</span><span class="pipeline-count">{len(sc)}</span></div>', unsafe_allow_html=True)
            for _, c in sc.head(8).iterrows():
                render_company_card(c)
                if st.button("Open", key=f"p_{c['company_id']}", use_container_width=True):
                    st.session_state['selected_company'] = c['company_id']
                    st.session_state['page'] = 'detail'
                    st.rerun()

# ============================================================================
# PAGE: COMPANIES
# ============================================================================

def page_companies():
    st.markdown("# Companies")
    st.markdown("Browse and filter your deal flow")
    
    with st.sidebar:
        st.markdown("### Filters")
        search = st.text_input("🔍 Search")
        sectors = get_unique_values('iq_sector')
        sel_sectors = st.multiselect("Sector", sectors)
        sel_pipeline = st.multiselect("Pipeline", PIPELINE_STAGES)
    
    filters = {'search': search or None, 'sectors': sel_sectors or None, 'pipeline_stages': sel_pipeline or None}
    df = get_all_companies(filters)
    
    st.markdown(f"**{len(df)} companies**")
    
    if len(df) == 0:
        st.info("No companies match filters")
        return
    
    for _, c in df.iterrows():
        cols = st.columns([3,2,1.5,1.5,1])
        with cols[0]: st.markdown(f"**{safe_str(c['name'])}**")
        with cols[1]: st.write(safe_str(c['pipeline_stage']) or 'Prospect')
        with cols[2]: r = c.get('total_raised'); st.write(f"${r:.1f}M" if pd.notna(r) else "—")
        with cols[3]: e = c.get('employees'); st.write(f"{int(e)}" if pd.notna(e) else "—")
        with cols[4]:
            if st.button("→", key=f"c_{c['company_id']}"):
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
            st.write(f"**Website:** {safe_str(c.get('website')) or '—'}")
        with col2:
            st.markdown("### Financing")
            r = c.get('total_raised'); st.write(f"**Raised:** ${r:.2f}M" if pd.notna(r) else "**Raised:** —")
            v = c.get('last_valuation'); st.write(f"**Valuation:** ${v:.2f}M" if pd.notna(v) else "**Valuation:** —")
            st.write(f"**Last Financing:** {safe_str(c.get('last_financing_date')) or '—'}")
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
        with col2: atype = st.selectbox("Type", ["Note","Call","Email","Meeting","Due Diligence"])
        if st.button("Add Activity") and desc: add_activity(cid, atype, desc); st.rerun()
        st.markdown("---")
        for _, a in get_activities(cid).iterrows():
            st.markdown(f"**{safe_str(a['activity_type'])}:** {safe_str(a['description'])} — _{safe_str(a['created_at'])[:10] if a['created_at'] else ''}_")

# ============================================================================
# PAGE: TRACTION (FULL FEATURES)
# ============================================================================

def page_traction():
    st.markdown("# Traction Tracker")
    st.markdown("Growth signals and investment scoring")
    
    try:
        from traction.scraper import TractionScraper, GrowthScorer
        traction_ok = True
    except Exception as e:
        traction_ok = False
        st.error(f"⚠️ Module load error: {str(e)}")
    
    tab1, tab2, tab3 = st.tabs(["🏆 Top Scores", "🔍 Analyze Company", "⚡ Batch Scan"])
    
    # TAB 1: TOP SCORES
    with tab1:
        conn = get_connection()
        try:
            df = pd.read_sql("""
                SELECT gs.company_id, c.name, c.iq_sector, c.pipeline_stage, c.total_raised,
                       gs.growth_score, gs.hiring_velocity_score, gs.funding_momentum_score, 
                       gs.news_buzz_score, gs.confidence, gs.factors_positive, gs.score_date
                FROM growth_scores gs
                JOIN companies c ON gs.company_id = c.company_id
                WHERE gs.id IN (SELECT MAX(id) FROM growth_scores GROUP BY company_id)
                ORDER BY gs.growth_score DESC
            """, conn)
            df = clean_df(df)
        except: df = pd.DataFrame()
        conn.close()
        
        if len(df) == 0:
            st.info("No scores calculated yet. Use 'Analyze Company' or 'Batch Scan' to get started.")
        else:
            col1, col2, col3, col4 = st.columns(4)
            with col1: st.metric("Companies Scored", len(df))
            with col2: st.metric("Avg Score", f"{df['growth_score'].mean():.1f}")
            with col3: st.metric("High Potential (60+)", len(df[df['growth_score']>=60]))
            with col4: st.metric("Actively Hiring", len(df[df['hiring_velocity_score']>=40]))
            
            st.markdown("---")
            
            top_10 = df.head(10)
            fig = create_horizontal_bar(top_10['name'].tolist(), top_10['growth_score'].tolist(), "Top 10 by Growth Score")
            st.plotly_chart(fig, use_container_width=True)
            
            st.markdown("### All Scored Companies")
            display_df = df[['name', 'iq_sector', 'pipeline_stage', 'growth_score', 'confidence']].copy()
            display_df.columns = ['Company', 'Sector', 'Pipeline', 'Score', 'Confidence %']
            st.dataframe(display_df, use_container_width=True, hide_index=True)
    
    # TAB 2: ANALYZE COMPANY
    with tab2:
        if not traction_ok:
            st.warning("Traction module not available")
            return
        
        conn = get_connection()
        companies = clean_df(pd.read_sql("SELECT company_id, name, website FROM companies ORDER BY name", conn))
        conn.close()
        
        if len(companies) == 0:
            st.info("Import companies first")
            return
        
        opts = {r['name']: r['company_id'] for _, r in companies.iterrows()}
        sel = st.selectbox("Select Company", list(opts.keys()))
        cid = opts[sel]
        c = get_company(cid)
        
        website = safe_str(c.get('website')) if c is not None else '—'
        
        col1, col2 = st.columns(2)
        with col1: st.write(f"**Website:** {website}")
        with col2: github_url = st.text_input("GitHub URL (optional)")
        
        if st.button("🔍 Scan Traction Signals", type="primary"):
            with st.spinner("Scanning web sources..."):
                from traction.scraper import TractionScraper, GrowthScorer
                scraper = TractionScraper()
                snapshot = scraper.collect_traction_snapshot(cid, sel, website if website != '—' else None, github_url or None)
                scorer = GrowthScorer()
                score = scorer.calculate_growth_score(cid)
            
            st.success("✓ Scan complete!")
            
            col1, col2, col3 = st.columns(3)
            with col1: st.metric("Growth Score", f"{score.get('growth_score',0):.1f}/100")
            with col2: st.metric("Confidence", f"{score.get('confidence',0):.0f}%")
            with col3: st.metric("News Mentions", snapshot.get('news',{}).get('mentions_count',0))
            
            st.markdown("### Score Breakdown")
            components = score.get('components', {})
            for name, value in components.items():
                st.progress(min(value/100, 1.0), text=f"{name.replace('_', ' ').title()}: {value:.1f}")
            
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("**✓ Positive Signals**")
                for f in score.get('factors_positive', []): st.write(f"• {f}")
            with col2:
                st.markdown("**⚠ Concerns**")
                for f in score.get('factors_negative', []): st.write(f"• {f}")
    
    # TAB 3: BATCH SCAN
    with tab3:
        if not traction_ok:
            st.warning("Traction module not available")
            return
        
        st.markdown("Scan multiple companies at once (respects rate limits)")
        
        conn = get_connection()
        companies = clean_df(pd.read_sql("""
            SELECT c.company_id, c.name, c.website, c.iq_sector, c.pipeline_stage,
                   (SELECT MAX(score_date) FROM growth_scores gs WHERE gs.company_id = c.company_id) as last_scan
            FROM companies c ORDER BY c.name
        """, conn))
        conn.close()
        
        if len(companies) == 0:
            st.info("Import companies first")
            return
        
        col1, col2, col3 = st.columns(3)
        with col1:
            sectors = ["All"] + companies['iq_sector'].dropna().unique().tolist()
            sel_sector = st.selectbox("Filter by Sector", sectors, key="batch_sector")
        with col2:
            pipelines = ["All"] + companies['pipeline_stage'].dropna().unique().tolist()
            sel_pipeline = st.selectbox("Filter by Pipeline", pipelines, key="batch_pipeline")
        with col3:
            only_unscanned = st.checkbox("Only unscanned", value=True)
        
        filtered = companies.copy()
        if sel_sector != "All": filtered = filtered[filtered['iq_sector']==sel_sector]
        if sel_pipeline != "All": filtered = filtered[filtered['pipeline_stage']==sel_pipeline]
        if only_unscanned: filtered = filtered[filtered['last_scan'].isna()]
        
        st.write(f"**{len(filtered)} companies** match criteria")
        
        if len(filtered) > 0:
            max_scan = st.slider("Companies to scan", 1, min(30, len(filtered)), min(10, len(filtered)))
            
            st.dataframe(filtered.head(max_scan)[['name','iq_sector','website','last_scan']], hide_index=True)
            
            if st.button("🚀 Start Batch Scan", type="primary"):
                from traction.scraper import TractionScraper, GrowthScorer
                scraper = TractionScraper()
                scorer = GrowthScorer()
                
                progress = st.progress(0)
                status = st.empty()
                results = []
                
                for idx, (_, company) in enumerate(filtered.head(max_scan).iterrows()):
                    progress.progress((idx + 1) / max_scan)
                    status.text(f"Scanning {idx + 1}/{max_scan}: {company['name']}")
                    
                    try:
                        scraper.collect_traction_snapshot(company['company_id'], company['name'], company.get('website'))
                        score = scorer.calculate_growth_score(company['company_id'])
                        results.append({'name': company['name'], 'score': score.get('growth_score',0), 'status': '✓'})
                    except Exception as e:
                        results.append({'name': company['name'], 'score': 0, 'status': f'✗ {str(e)[:20]}'})
                
                progress.progress(1.0)
                status.text("Complete!")
                
                st.success(f"Scanned {len(results)} companies")
                results_df = pd.DataFrame(results).sort_values('score', ascending=False)
                st.dataframe(results_df, hide_index=True)

# ============================================================================
# PAGE: FUNDING RADAR
# ============================================================================

def page_funding_radar():
    st.markdown("# Funding Radar")
    st.markdown("Predict funding windows and prioritize BD outreach")
    
    try:
        from traction.scraper import FundingPredictor, TractionScraper
        predictor_ok = True
    except Exception as e:
        predictor_ok = False
        st.error(f"⚠️ Module load error: {str(e)}")
    
    tab1, tab2, tab3, tab4 = st.tabs(["🎯 Priority Queue", "🔮 Analyze Company", "⚡ Batch Predict", "📊 Insights"])
    
    # TAB 1: PRIORITY QUEUE
    with tab1:
        st.markdown("### Companies Most Likely to Raise Soon")
        st.markdown("Ranked by urgency score — focus your BD efforts on the top companies")
        
        conn = get_connection()
        try:
            df = pd.read_sql("""
                SELECT 
                    fp.company_id,
                    c.name,
                    c.iq_sector,
                    c.pipeline_stage,
                    c.total_raised,
                    c.employees,
                    c.last_financing_date,
                    fp.estimated_months_to_raise,
                    fp.confidence,
                    fp.predicted_window,
                    fp.recommended_action,
                    fp.urgency_score,
                    fp.runway_score,
                    fp.hiring_score,
                    fp.growth_score,
                    fp.primary_signals,
                    fp.prediction_date
                FROM funding_predictions fp
                JOIN companies c ON fp.company_id = c.company_id
                WHERE fp.id IN (
                    SELECT MAX(id) FROM funding_predictions GROUP BY company_id
                )
                ORDER BY fp.urgency_score DESC
            """, conn)
            df = clean_df(df)
        except Exception as e:
            df = pd.DataFrame()
        conn.close()
        
        if len(df) == 0:
            st.info("No predictions yet. Use 'Analyze Company' or 'Batch Predict' to generate funding predictions.")
        else:
            # Summary metrics
            col1, col2, col3, col4, col5 = st.columns(5)
            with col1: 
                priority_count = len(df[df['recommended_action'] == 'priority_bd'])
                render_metric_card(priority_count, "Priority BD")
            with col2: 
                warm_count = len(df[df['recommended_action'] == 'warm_outreach'])
                render_metric_card(warm_count, "Warm Outreach")
            with col3:
                avg_months = df['estimated_months_to_raise'].mean()
                render_metric_card(f"{avg_months:.1f}", "Avg Months to Raise")
            with col4:
                high_conf = len(df[df['confidence'] == 'high'])
                render_metric_card(high_conf, "High Confidence")
            with col5:
                render_metric_card(len(df), "Total Predicted")
            
            st.markdown("---")
            
            # Action filter
            col1, col2, col3 = st.columns([2, 2, 2])
            with col1:
                action_filter = st.selectbox("Filter by Action", ["All", "priority_bd", "warm_outreach", "monitor", "watch", "low_priority"])
            with col2:
                confidence_filter = st.selectbox("Filter by Confidence", ["All", "high", "medium", "low"])
            with col3:
                months_filter = st.slider("Max Months to Raise", 1, 24, 12)
            
            filtered_df = df.copy()
            if action_filter != "All":
                filtered_df = filtered_df[filtered_df['recommended_action'] == action_filter]
            if confidence_filter != "All":
                filtered_df = filtered_df[filtered_df['confidence'] == confidence_filter]
            filtered_df = filtered_df[filtered_df['estimated_months_to_raise'] <= months_filter]
            
            st.markdown(f"**{len(filtered_df)} companies** match your criteria")
            
            # Priority Queue Cards
            for idx, row in filtered_df.head(20).iterrows():
                with st.container():
                    col1, col2, col3, col4, col5 = st.columns([3, 1.5, 1.5, 2, 1])
                    
                    # Company info
                    with col1:
                        name = safe_str(row.get('name')) or '—'
                        sector = safe_str(row.get('iq_sector')) or ''
                        pipeline = safe_str(row.get('pipeline_stage')) or 'Prospect'
                        
                        action = row.get('recommended_action', '')
                        action_colors = {
                            'priority_bd': '#dc2626',
                            'warm_outreach': '#d97706',
                            'monitor': '#0052cc',
                            'watch': '#697386',
                            'low_priority': '#97a0af'
                        }
                        action_color = action_colors.get(action, '#697386')
                        
                        st.markdown(f"""
                        <div style="padding: 0.5rem 0;">
                            <span style="font-weight: 600; color: #1a1f36; font-size: 1rem;">{name}</span>
                            <span style="background: {action_color}; color: white; padding: 0.2rem 0.5rem; border-radius: 4px; font-size: 0.7rem; font-weight: 600; margin-left: 0.5rem;">{action.upper().replace('_', ' ')}</span>
                            <br><span class="tag tag-sector">{sector}</span><span class="tag tag-stage">{pipeline}</span>
                        </div>
                        """, unsafe_allow_html=True)
                    
                    # Timing
                    with col2:
                        months = row.get('estimated_months_to_raise', 0)
                        window = safe_str(row.get('predicted_window')) or '—'
                        st.markdown(f"**{months} mo**<br><span style='color: #697386; font-size: 0.8rem;'>{window}</span>", unsafe_allow_html=True)
                    
                    # Scores
                    with col3:
                        urgency = row.get('urgency_score', 0)
                        confidence = safe_str(row.get('confidence')) or 'low'
                        conf_colors = {'high': '#00875a', 'medium': '#d97706', 'low': '#697386'}
                        st.markdown(f"**{urgency:.0f}**/100<br><span style='color: {conf_colors.get(confidence, '#697386')}; font-size: 0.8rem;'>{confidence.upper()} conf.</span>", unsafe_allow_html=True)
                    
                    # Top signal
                    with col4:
                        try:
                            signals_raw = row.get('primary_signals', '[]')
                            if isinstance(signals_raw, bytes):
                                signals_raw = signals_raw.decode('utf-8')
                            signals = json.loads(signals_raw) if signals_raw else []
                            if signals:
                                top_signal = signals[0].get('detail', '')[:50]
                                st.markdown(f"<span style='font-size: 0.85rem; color: #3c4257;'>📍 {top_signal}...</span>", unsafe_allow_html=True)
                            else:
                                st.markdown("<span style='color: #697386;'>No signals</span>", unsafe_allow_html=True)
                        except:
                            st.markdown("<span style='color: #697386;'>—</span>", unsafe_allow_html=True)
                    
                    # Action button
                    with col5:
                        if st.button("View", key=f"fr_{row['company_id']}"):
                            st.session_state['selected_company'] = row['company_id']
                            st.session_state['page'] = 'detail'
                            st.rerun()
                    
                    st.markdown("<hr style='margin: 0.5rem 0; border-color: #e5e7eb;'>", unsafe_allow_html=True)
    
    # TAB 2: ANALYZE COMPANY
    with tab2:
        if not predictor_ok:
            st.warning("Predictor module not available")
            return
        
        st.markdown("### Predict Funding Window for a Company")
        
        conn = get_connection()
        companies = clean_df(pd.read_sql("SELECT company_id, name, iq_sector, last_financing_date, total_raised FROM companies ORDER BY name", conn))
        conn.close()
        
        if len(companies) == 0:
            st.info("Import companies first")
            return
        
        opts = {f"{r['name']} ({safe_str(r['iq_sector']) or 'No sector'})": r['company_id'] for _, r in companies.iterrows()}
        sel = st.selectbox("Select Company", list(opts.keys()))
        cid = opts[sel]
        c = get_company(cid)
        
        if c is not None:
            col1, col2, col3, col4 = st.columns(4)
            with col1: 
                raised = c.get('total_raised')
                st.write(f"**Total Raised:** ${raised:.1f}M" if pd.notna(raised) else "**Total Raised:** —")
            with col2: 
                st.write(f"**Last Financing:** {safe_str(c.get('last_financing_date')) or '—'}")
            with col3:
                st.write(f"**Employees:** {c.get('employees') or '—'}")
            with col4:
                st.write(f"**Stage:** {safe_str(c.get('stage_entreprise')) or '—'}")
        
        if st.button("🔮 Predict Funding Window", type="primary"):
            with st.spinner("Analyzing funding signals..."):
                from traction.scraper import FundingPredictor
                predictor = FundingPredictor()
                prediction = predictor.predict_funding_window(cid)
            
            if "error" in prediction:
                st.error(prediction["error"])
            else:
                st.success("✓ Prediction complete!")
                
                # Main prediction display
                st.markdown("---")
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    months = prediction.get('estimated_months_to_raise', 0)
                    st.metric("Estimated Time to Raise", f"{months} months")
                
                with col2:
                    window = prediction.get('predicted_window', '—')
                    st.metric("Predicted Window", window)
                
                with col3:
                    confidence = prediction.get('confidence', 'low').upper()
                    st.metric("Confidence", confidence)
                
                with col4:
                    action = prediction.get('recommended_action', '').replace('_', ' ').title()
                    st.metric("Recommended Action", action)
                
                # Score breakdown
                st.markdown("### Score Breakdown")
                scores = prediction.get('scores', {})
                
                col1, col2 = st.columns(2)
                
                with col1:
                    # Radar chart for scores
                    categories = ['Runway', 'Hiring', 'Growth', 'Market', 'Benchmark']
                    values = [
                        scores.get('runway', 0),
                        scores.get('hiring', 0),
                        scores.get('growth', 0),
                        scores.get('market', 0),
                        scores.get('benchmark', 0)
                    ]
                    
                    fig = go.Figure()
                    fig.add_trace(go.Scatterpolar(
                        r=values + [values[0]],
                        theta=categories + [categories[0]],
                        fill='toself',
                        fillcolor='rgba(0, 135, 90, 0.2)',
                        line=dict(color='#00875a', width=2),
                        name='Score'
                    ))
                    fig.update_layout(
                        polar=dict(
                            radialaxis=dict(visible=True, range=[0, 100], tickfont=dict(color=NAVY, size=10)),
                            angularaxis=dict(tickfont=dict(color=NAVY, size=11))
                        ),
                        showlegend=False,
                        height=350,
                        margin=dict(l=60, r=60, t=30, b=30),
                        paper_bgcolor='rgba(0,0,0,0)',
                        font_color=NAVY
                    )
                    st.plotly_chart(fig, use_container_width=True)
                
                with col2:
                    st.markdown("**Component Scores**")
                    for name, value in scores.items():
                        if name != 'urgency':
                            st.progress(min(value/100, 1.0), text=f"{name.replace('_', ' ').title()}: {value:.0f}/100")
                    
                    st.markdown(f"**Overall Urgency Score: {scores.get('urgency', 0):.0f}/100**")
                
                # Signals
                st.markdown("### Key Signals")
                col1, col2 = st.columns(2)
                
                all_signals = prediction.get('all_signals', [])
                high_signals = [s for s in all_signals if s.get('weight') == 'high']
                other_signals = [s for s in all_signals if s.get('weight') != 'high']
                
                with col1:
                    st.markdown("**🔴 High-Weight Signals**")
                    if high_signals:
                        for sig in high_signals:
                            st.markdown(f"• **{sig.get('type', '').replace('_', ' ').title()}**: {sig.get('detail', '')}")
                    else:
                        st.write("No high-weight signals detected")
                
                with col2:
                    st.markdown("**🟡 Other Signals**")
                    if other_signals:
                        for sig in other_signals[:5]:
                            st.markdown(f"• {sig.get('type', '').replace('_', ' ').title()}: {sig.get('detail', '')}")
                    else:
                        st.write("No additional signals")
    
    # TAB 3: BATCH PREDICT
    with tab3:
        if not predictor_ok:
            st.warning("Predictor module not available")
            return
        
        st.markdown("### Batch Funding Predictions")
        st.markdown("Run predictions for multiple companies to build your priority queue")
        
        conn = get_connection()
        companies = clean_df(pd.read_sql("""
            SELECT c.company_id, c.name, c.iq_sector, c.pipeline_stage, c.last_financing_date,
                   (SELECT MAX(prediction_date) FROM funding_predictions fp WHERE fp.company_id = c.company_id) as last_prediction
            FROM companies c 
            ORDER BY c.name
        """, conn))
        conn.close()
        
        if len(companies) == 0:
            st.info("Import companies first")
            return
        
        # Filters
        col1, col2, col3 = st.columns(3)
        with col1:
            sectors = ["All"] + companies['iq_sector'].dropna().unique().tolist()
            sel_sector = st.selectbox("Filter by Sector", sectors, key="batch_pred_sector")
        with col2:
            pipelines = ["All"] + companies['pipeline_stage'].dropna().unique().tolist()
            sel_pipeline = st.selectbox("Filter by Pipeline", pipelines, key="batch_pred_pipeline")
        with col3:
            only_unpredicted = st.checkbox("Only companies without predictions", value=True)
        
        filtered = companies.copy()
        if sel_sector != "All":
            filtered = filtered[filtered['iq_sector'] == sel_sector]
        if sel_pipeline != "All":
            filtered = filtered[filtered['pipeline_stage'] == sel_pipeline]
        if only_unpredicted:
            filtered = filtered[filtered['last_prediction'].isna()]
        
        st.write(f"**{len(filtered)} companies** match criteria")
        
        if len(filtered) > 0:
            max_predict = st.slider("Companies to predict", 1, min(50, len(filtered)), min(20, len(filtered)))
            
            # Preview
            preview_df = filtered.head(max_predict)[['name', 'iq_sector', 'pipeline_stage', 'last_financing_date', 'last_prediction']]
            preview_df.columns = ['Company', 'Sector', 'Pipeline', 'Last Financing', 'Last Prediction']
            st.dataframe(preview_df, hide_index=True)
            
            if st.button("🚀 Run Batch Predictions", type="primary"):
                from traction.scraper import FundingPredictor, TractionScraper
                predictor = FundingPredictor()
                scraper = TractionScraper()
                
                progress = st.progress(0)
                status = st.empty()
                results = []
                
                for idx, (_, company) in enumerate(filtered.head(max_predict).iterrows()):
                    progress.progress((idx + 1) / max_predict)
                    status.text(f"Predicting {idx + 1}/{max_predict}: {company['name']}")
                    
                    try:
                        # First ensure we have traction data
                        c = get_company(company['company_id'])
                        if c is not None:
                            website = safe_str(c.get('website'))
                            scraper.collect_traction_snapshot(company['company_id'], company['name'], website)
                        
                        # Then predict
                        prediction = predictor.predict_funding_window(company['company_id'])
                        
                        if "error" not in prediction:
                            results.append({
                                'name': company['name'],
                                'months': prediction.get('estimated_months_to_raise', 0),
                                'action': prediction.get('recommended_action', ''),
                                'confidence': prediction.get('confidence', ''),
                                'urgency': prediction.get('scores', {}).get('urgency', 0),
                                'status': '✓'
                            })
                        else:
                            results.append({'name': company['name'], 'months': 0, 'action': '', 'confidence': '', 'urgency': 0, 'status': '✗ No data'})
                    except Exception as e:
                        results.append({'name': company['name'], 'months': 0, 'action': '', 'confidence': '', 'urgency': 0, 'status': f'✗ {str(e)[:20]}'})
                
                progress.progress(1.0)
                status.text("Complete!")
                
                st.success(f"Predicted {len(results)} companies")
                
                # Results summary
                results_df = pd.DataFrame(results).sort_values('urgency', ascending=False)
                st.dataframe(results_df, hide_index=True)
                
                # Quick stats
                priority_count = len([r for r in results if r['action'] == 'priority_bd'])
                warm_count = len([r for r in results if r['action'] == 'warm_outreach'])
                st.markdown(f"**Quick Summary:** {priority_count} Priority BD, {warm_count} Warm Outreach, {len(results) - priority_count - warm_count} Others")
    
    # TAB 4: INSIGHTS
    with tab4:
        st.markdown("### Funding Radar Insights")
        
        conn = get_connection()
        try:
            df = pd.read_sql("""
                SELECT 
                    fp.*,
                    c.name,
                    c.iq_sector,
                    c.pipeline_stage
                FROM funding_predictions fp
                JOIN companies c ON fp.company_id = c.company_id
                WHERE fp.id IN (
                    SELECT MAX(id) FROM funding_predictions GROUP BY company_id
                )
            """, conn)
            df = clean_df(df)
        except:
            df = pd.DataFrame()
        conn.close()
        
        if len(df) == 0:
            st.info("Run some predictions first to see insights")
            return
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Distribution by recommended action
            action_counts = df['recommended_action'].value_counts()
            action_colors = {
                'priority_bd': '#dc2626',
                'warm_outreach': '#d97706',
                'monitor': '#0052cc',
                'watch': '#697386',
                'low_priority': '#97a0af'
            }
            colors = [action_colors.get(a, '#697386') for a in action_counts.index]
            
            fig = go.Figure(go.Pie(
                labels=[a.replace('_', ' ').title() for a in action_counts.index],
                values=action_counts.values,
                hole=0.55,
                marker=dict(colors=colors),
                textfont=dict(size=11, color=NAVY)
            ))
            fig.update_layout(
                title=dict(text="By Recommended Action", font=dict(color=NAVY, size=14)),
                paper_bgcolor='rgba(0,0,0,0)',
                height=350,
                margin=dict(l=20, r=20, t=40, b=20),
                legend=dict(font=dict(size=11, color=NAVY))
            )
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            # Distribution by estimated months
            fig = go.Figure(go.Histogram(
                x=df['estimated_months_to_raise'],
                nbinsx=12,
                marker_color='#00875a'
            ))
            fig.update_layout(
                title=dict(text="Distribution: Months to Raise", font=dict(color=NAVY, size=14)),
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                height=350,
                margin=dict(l=20, r=20, t=40, b=40),
                xaxis=dict(title="Months", tickfont=dict(color=NAVY, size=11), gridcolor='#e5e7eb'),
                yaxis=dict(title="# Companies", tickfont=dict(color=NAVY, size=11), gridcolor='#e5e7eb'),
                font_color=NAVY
            )
            st.plotly_chart(fig, use_container_width=True)
        
        st.markdown("---")
        
        # Top signals analysis
        st.markdown("### Most Common Signals")
        
        all_signals = []
        for _, row in df.iterrows():
            try:
                signals_raw = row.get('primary_signals', '[]')
                if isinstance(signals_raw, bytes):
                    signals_raw = signals_raw.decode('utf-8')
                signals = json.loads(signals_raw) if signals_raw else []
                for sig in signals:
                    all_signals.append(sig.get('type', 'unknown'))
            except:
                continue
        
        if all_signals:
            signal_counts = pd.Series(all_signals).value_counts().head(10)
            
            fig = go.Figure(go.Bar(
                y=[s.replace('_', ' ').title() for s in signal_counts.index],
                x=signal_counts.values,
                orientation='h',
                marker_color='#0052cc',
                text=signal_counts.values,
                textposition='inside',
                textfont=dict(color='white', size=12)
            ))
            fig.update_layout(
                title=dict(text="Top Signals Driving Predictions", font=dict(color=NAVY, size=14)),
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                height=400,
                margin=dict(l=20, r=20, t=40, b=20),
                xaxis=dict(title="Occurrences", tickfont=dict(color=NAVY, size=11), gridcolor='#e5e7eb'),
                yaxis=dict(autorange='reversed', tickfont=dict(color=NAVY, size=11)),
                font_color=NAVY
            )
            st.plotly_chart(fig, use_container_width=True)
        
        # Sector breakdown
        st.markdown("### By Sector")
        sector_urgency = df.groupby('iq_sector')['urgency_score'].mean().sort_values(ascending=False).head(10)
        
        fig = go.Figure(go.Bar(
            x=sector_urgency.index,
            y=sector_urgency.values,
            marker_color='#00875a',
            text=[f"{v:.0f}" for v in sector_urgency.values],
            textposition='outside',
            textfont=dict(color=NAVY, size=12)
        ))
        fig.update_layout(
            title=dict(text="Average Urgency Score by Sector", font=dict(color=NAVY, size=14)),
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            height=350,
            margin=dict(l=20, r=20, t=40, b=80),
            xaxis=dict(tickangle=45, tickfont=dict(color=NAVY, size=10)),
            yaxis=dict(range=[0, 100], tickfont=dict(color=NAVY, size=11), gridcolor='#e5e7eb'),
            font_color=NAVY
        )
        st.plotly_chart(fig, use_container_width=True)

# ============================================================================
# PAGE: SETTINGS (WITH PRE-SCREENING)
# ============================================================================

def page_settings():
    st.markdown("# Settings")
    st.markdown("Data import and configuration")
    
    st.markdown("### Import Data with Pre-Screening")
    st.markdown("Upload your PitchBook export and filter before importing.")
    
    uploaded_file = st.file_uploader("PitchBook Export (.xlsx)", type=['xlsx', 'xls'])
    
    if uploaded_file:
        preview_df, full_df = preview_pitchbook_data(uploaded_file)
        
        if preview_df is not None:
            st.markdown("---")
            st.markdown("### Pre-Import Screening")
            st.markdown("Filter out companies before importing:")
            
            col1, col2 = st.columns(2)
            with col1:
                remove_no_website = st.checkbox("Remove companies without website", value=True)
                remove_no_employees = st.checkbox("Remove companies with 0 employees", value=False)
                remove_inactive = st.checkbox("Remove defunct/bankrupt companies", value=True)
            with col2:
                remove_no_funding = st.checkbox("Remove companies with no funding", value=False)
                remove_stale = st.checkbox("Remove companies with no activity in 3+ years", value=False)
                min_employees = st.number_input("Minimum employees", value=0, min_value=0)
            
            # Apply filters
            filtered = preview_df.copy()
            original_count = len(filtered)
            
            if remove_no_website: filtered = filtered[filtered['has_website']]
            if remove_no_employees: filtered = filtered[filtered['has_employees']]
            if remove_inactive: filtered = filtered[~filtered['potentially_inactive']]
            if remove_no_funding: filtered = filtered[filtered['has_funding']]
            if remove_stale: filtered = filtered[filtered['recent_activity'] | filtered['has_funding']]
            if min_employees > 0: filtered = filtered[filtered['employees'] >= min_employees]
            
            removed = original_count - len(filtered)
            
            st.markdown("---")
            col1, col2, col3 = st.columns(3)
            with col1: st.metric("Total in File", original_count)
            with col2: st.metric("Filtered Out", removed, delta=f"-{removed}", delta_color="inverse")
            with col3: st.metric("Ready to Import", len(filtered))
            
            st.markdown("### Preview (first 20)")
            display_cols = ['name', 'iq_sector', 'employees', 'total_raised', 'has_website']
            st.dataframe(filtered[display_cols].head(20), hide_index=True)
            
            if len(filtered) > 0:
                if st.button(f"Import {len(filtered)} Companies", type="primary"):
                    with st.spinner("Importing..."):
                        ids_to_import = filtered['company_id'].tolist()
                        imported, skipped = import_filtered_data(full_df, ids_to_import)
                    st.success(f"✓ {imported} companies imported, {skipped} already existed")
                    st.rerun()
    
    st.markdown("---")
    
    st.markdown("### Database Stats")
    df = get_all_companies()
    col1, col2, col3, col4 = st.columns(4)
    with col1: st.metric("Companies", len(df))
    with col2: st.metric("Sectors", df['iq_sector'].nunique() if len(df)>0 else 0)
    with col3:
        conn = get_connection()
        try:
            scores = pd.read_sql("SELECT COUNT(DISTINCT company_id) as c FROM growth_scores", conn)
            st.metric("Scored", scores['c'].iloc[0])
        except: st.metric("Scored", 0)
        conn.close()
    with col4:
        conn = get_connection()
        try:
            acts = pd.read_sql("SELECT COUNT(*) as c FROM activities", conn)
            st.metric("Activities", acts['c'].iloc[0])
        except: st.metric("Activities", 0)
        conn.close()
    
    if len(df) > 0:
        st.download_button("📥 Export CSV", df.to_csv(index=False), "pipeline_export.csv", "text/csv")

# ============================================================================
# MAIN
# ============================================================================

def main():
    init_database()
    if 'page' not in st.session_state: st.session_state['page'] = 'overview'
    
    with st.sidebar:
        st.markdown('<div class="logo-container"><div class="logo-text">◆ QC Pipeline</div><div class="logo-subtext">Deal Flow Tracker</div></div>', unsafe_allow_html=True)
        
        if st.button("📊 Overview", use_container_width=True): st.session_state['page'] = 'overview'; st.rerun()
        if st.button("🎯 Pipeline", use_container_width=True): st.session_state['page'] = 'pipeline'; st.rerun()
        if st.button("🏢 Companies", use_container_width=True): st.session_state['page'] = 'companies'; st.rerun()
        if st.button("📈 Traction", use_container_width=True): st.session_state['page'] = 'traction'; st.rerun()
        if st.button("🔮 Funding Radar", use_container_width=True): st.session_state['page'] = 'funding_radar'; st.rerun()
        if st.button("⚙️ Settings", use_container_width=True): st.session_state['page'] = 'settings'; st.rerun()
        
        st.markdown("---")
        st.caption("v3.1 • IQ Edition + Funding Radar")
    
    p = st.session_state.get('page', 'overview')
    if p == 'overview': page_overview()
    elif p == 'pipeline': page_pipeline()
    elif p == 'companies': page_companies()
    elif p == 'detail': page_detail()
    elif p == 'traction': page_traction()
    elif p == 'funding_radar': page_funding_radar()
    elif p == 'settings': page_settings()

if __name__ == "__main__":
    main()
