"""
Quebec Startup Pipeline Tracker
A local Streamlit application for tracking VC deal flow in Quebec.
"""

import streamlit as st
import pandas as pd
import sqlite3
import json
from datetime import datetime, date
from pathlib import Path
import plotly.express as px
import plotly.graph_objects as go

# ============================================================================
# CONFIGURATION
# ============================================================================

st.set_page_config(
    page_title="Quebec Pipeline Tracker",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Dark theme CSS
st.markdown("""
<style>
    /* Dark premium theme */
    .stApp {
        background-color: #0f1419;
    }
    
    .main .block-container {
        padding-top: 2rem;
        max-width: 100%;
    }
    
    /* Cards */
    .company-card {
        background: linear-gradient(145deg, #1a1f2e 0%, #151922 100%);
        border: 1px solid #2d3748;
        border-radius: 12px;
        padding: 1rem;
        margin-bottom: 0.75rem;
        transition: all 0.2s ease;
    }
    
    .company-card:hover {
        border-color: #4a5568;
        transform: translateY(-2px);
    }
    
    .company-name {
        font-size: 1rem;
        font-weight: 600;
        color: #e2e8f0;
        margin-bottom: 0.5rem;
    }
    
    .company-meta {
        font-size: 0.75rem;
        color: #718096;
    }
    
    .tag {
        display: inline-block;
        padding: 0.2rem 0.5rem;
        border-radius: 4px;
        font-size: 0.7rem;
        font-weight: 500;
        margin-right: 0.25rem;
    }
    
    .tag-sector { background: #2d3748; color: #90cdf4; }
    .tag-stage { background: #2d4a3e; color: #9ae6b4; }
    .tag-priority { background: #4a3728; color: #fbd38d; }
    
    /* Pipeline columns */
    .pipeline-column {
        background: #1a1f2e;
        border-radius: 12px;
        padding: 1rem;
        min-height: 400px;
    }
    
    .pipeline-header {
        font-size: 0.85rem;
        font-weight: 600;
        color: #a0aec0;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-bottom: 1rem;
        padding-bottom: 0.5rem;
        border-bottom: 2px solid #2d3748;
    }
    
    /* Metrics */
    .metric-card {
        background: linear-gradient(145deg, #1e2433 0%, #1a1f2e 100%);
        border: 1px solid #2d3748;
        border-radius: 12px;
        padding: 1.25rem;
        text-align: center;
    }
    
    .metric-value {
        font-size: 2rem;
        font-weight: 700;
        color: #63b3ed;
    }
    
    .metric-label {
        font-size: 0.75rem;
        color: #718096;
        text-transform: uppercase;
    }
    
    /* Hide Streamlit branding */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    
    /* Sidebar */
    [data-testid="stSidebar"] {
        background-color: #151922;
    }
    
    /* Fix text colors */
    .stMarkdown, .stText, p, span, label {
        color: #e2e8f0 !important;
    }
    
    h1, h2, h3 {
        color: #f7fafc !important;
    }
    
    /* Dataframe styling */
    .dataframe {
        background: #1a1f2e !important;
    }
</style>
""", unsafe_allow_html=True)

# ============================================================================
# DATABASE SETUP
# ============================================================================

DB_PATH = Path("pipeline_data.db")

PIPELINE_STAGES = [
    "Prospect",
    "Premier Contact",
    "Due Diligence",
    "Préparation CI",
    "Comité d'Investissement",
    "Closing",
    "Pass"
]

def init_database():
    """Initialize SQLite database with required tables."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Companies table (imported data + tracking fields)
    c.execute("""
        CREATE TABLE IF NOT EXISTS companies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id TEXT UNIQUE,
            name TEXT,
            description TEXT,
            website TEXT,
            hq_location TEXT,
            year_founded TEXT,
            employees INTEGER,
            employee_history TEXT,
            
            -- Financing
            first_financing_size REAL,
            first_financing_date TEXT,
            last_financing_size REAL,
            last_financing_date TEXT,
            total_raised REAL,
            last_valuation REAL,
            last_valuation_date TEXT,
            
            -- Classification
            iq_sector TEXT,
            iq_team TEXT,
            stage_entreprise TEXT,
            verticals TEXT,
            primary_industry TEXT,
            ownership_status TEXT,
            financing_status TEXT,
            
            -- Investors
            active_investors TEXT,
            former_investors TEXT,
            primary_contact TEXT,
            
            -- Watchlist
            watchlist TEXT,
            secteurs_dpcriii TEXT,
            
            -- Tracking (user-added)
            pipeline_stage TEXT DEFAULT 'Prospect',
            priority INTEGER DEFAULT 0,
            notes TEXT,
            tags TEXT,
            assigned_to TEXT,
            next_action TEXT,
            next_action_date TEXT,
            
            -- Metadata
            created_at TEXT,
            updated_at TEXT
        )
    """)
    
    # Activity log
    c.execute("""
        CREATE TABLE IF NOT EXISTS activities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id TEXT,
            activity_type TEXT,
            description TEXT,
            created_at TEXT,
            FOREIGN KEY (company_id) REFERENCES companies(company_id)
        )
    """)
    
    conn.commit()
    conn.close()

def get_connection():
    return sqlite3.connect(DB_PATH)

# ============================================================================
# DATA IMPORT
# ============================================================================

def import_pitchbook_data(uploaded_file):
    """Import PitchBook Excel export into database."""
    try:
        df = pd.read_excel(uploaded_file, header=7)
        
        conn = get_connection()
        now = datetime.now().isoformat()
        
        imported = 0
        skipped = 0
        
        def safe_str(val):
            """Convert value to string, handling NaN/NaT."""
            if val is None or pd.isna(val):
                return None
            return str(val)
        
        def safe_float(val):
            """Convert value to float, handling NaN/NaT."""
            if val is None or pd.isna(val):
                return None
            try:
                return float(val)
            except (ValueError, TypeError):
                return None
        
        def safe_int(val):
            """Convert value to int, handling NaN/NaT."""
            if val is None or pd.isna(val):
                return None
            try:
                return int(float(val))
            except (ValueError, TypeError):
                return None
        
        def parse_date(val):
            """Parse date safely, handling NaN/NaT."""
            if val is None or pd.isna(val):
                return None
            try:
                if isinstance(val, datetime):
                    return val.strftime('%Y-%m-%d')
                if hasattr(val, 'strftime'):
                    return val.strftime('%Y-%m-%d')
                val_str = str(val)
                if val_str and val_str != 'nan' and val_str != 'NaT':
                    return val_str[:10]
            except:
                pass
            return None
        
        for _, row in df.iterrows():
            company_id = safe_str(row.get('Company ID'))
            if not company_id or company_id == 'nan':
                continue
            
            # Check if exists
            existing = pd.read_sql(
                "SELECT id FROM companies WHERE company_id = ?", 
                conn, params=(company_id,)
            )
            
            if len(existing) > 0:
                skipped += 1
                continue
            
            # Insert new company
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO companies (
                    company_id, name, description, website, hq_location, year_founded,
                    employees, employee_history, first_financing_size, first_financing_date,
                    last_financing_size, last_financing_date, total_raised, last_valuation,
                    last_valuation_date, iq_sector, iq_team, stage_entreprise, verticals,
                    primary_industry, ownership_status, financing_status, active_investors,
                    former_investors, primary_contact, watchlist, secteurs_dpcriii,
                    pipeline_stage, priority, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                company_id,
                safe_str(row.get('Companies')),
                safe_str(row.get('Description')),
                safe_str(row.get('Website')),
                safe_str(row.get('HQ Location')),
                safe_str(row.get('Year Founded')),
                safe_int(row.get('Employees')),
                safe_str(row.get('Employee History')),
                safe_float(row.get('First Financing Size')),
                parse_date(row.get('First Financing Date')),
                safe_float(row.get('Last Financing Size')),
                parse_date(row.get('Last Financing Date')),
                safe_float(row.get('Total Raised')),
                safe_float(row.get('Last Known Valuation')),
                parse_date(row.get('Last Known Valuation Date')),
                safe_str(row.get('IQ - Secteur')),
                safe_str(row.get('Équipe IQ')),
                safe_str(row.get("Stade de l'entreprise")),
                safe_str(row.get('Verticals')),
                safe_str(row.get('Primary Industry Sector')),
                safe_str(row.get('Ownership Status')),
                safe_str(row.get('Company Financing Status')),
                safe_str(row.get('Active Investors')),
                safe_str(row.get('Former Investors')),
                safe_str(row.get('Primary Contact')),
                safe_str(row.get('Watchlist - DPCRIII')),
                safe_str(row.get('Secteurs  - DPCRIII')),
                'Prospect',
                0,
                now,
                now
            ))
            imported += 1
        
        conn.commit()
        conn.close()
        return imported, skipped
        
    except Exception as e:
        st.error(f"Import error: {str(e)}")
        import traceback
        st.error(traceback.format_exc())
        return 0, 0

# ============================================================================
# DATA ACCESS
# ============================================================================

def get_all_companies(filters=None):
    """Fetch companies with optional filters."""
    conn = get_connection()
    
    query = "SELECT * FROM companies WHERE 1=1"
    params = []
    
    if filters:
        if filters.get('search'):
            query += " AND (name LIKE ? OR description LIKE ? OR notes LIKE ?)"
            search_term = f"%{filters['search']}%"
            params.extend([search_term, search_term, search_term])
        
        if filters.get('sectors'):
            placeholders = ','.join(['?' for _ in filters['sectors']])
            query += f" AND iq_sector IN ({placeholders})"
            params.extend(filters['sectors'])
        
        if filters.get('stages'):
            placeholders = ','.join(['?' for _ in filters['stages']])
            query += f" AND stage_entreprise IN ({placeholders})"
            params.extend(filters['stages'])
        
        if filters.get('pipeline_stages'):
            placeholders = ','.join(['?' for _ in filters['pipeline_stages']])
            query += f" AND pipeline_stage IN ({placeholders})"
            params.extend(filters['pipeline_stages'])
        
        if filters.get('min_raised'):
            query += " AND total_raised >= ?"
            params.append(filters['min_raised'])
        
        if filters.get('max_raised'):
            query += " AND total_raised <= ?"
            params.append(filters['max_raised'])
        
        if filters.get('watchlist_only'):
            query += " AND watchlist IS NOT NULL AND watchlist != ''"
    
    query += " ORDER BY updated_at DESC"
    
    df = pd.read_sql(query, conn, params=params)
    conn.close()
    return df

def get_company(company_id):
    """Fetch single company by ID."""
    conn = get_connection()
    df = pd.read_sql(
        "SELECT * FROM companies WHERE company_id = ?", 
        conn, params=(company_id,)
    )
    conn.close()
    return df.iloc[0] if len(df) > 0 else None

def update_company(company_id, updates):
    """Update company fields."""
    conn = get_connection()
    cursor = conn.cursor()
    
    updates['updated_at'] = datetime.now().isoformat()
    
    set_clause = ', '.join([f"{k} = ?" for k in updates.keys()])
    values = list(updates.values()) + [company_id]
    
    cursor.execute(f"UPDATE companies SET {set_clause} WHERE company_id = ?", values)
    conn.commit()
    conn.close()

def add_activity(company_id, activity_type, description):
    """Log an activity for a company."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO activities (company_id, activity_type, description, created_at) VALUES (?, ?, ?, ?)",
        (company_id, activity_type, description, datetime.now().isoformat())
    )
    conn.commit()
    conn.close()

def get_activities(company_id):
    """Get activity log for a company."""
    conn = get_connection()
    df = pd.read_sql(
        "SELECT * FROM activities WHERE company_id = ? ORDER BY created_at DESC",
        conn, params=(company_id,)
    )
    conn.close()
    return df

def get_unique_values(column):
    """Get unique values for a column."""
    conn = get_connection()
    df = pd.read_sql(f"SELECT DISTINCT {column} FROM companies WHERE {column} IS NOT NULL AND {column} != ''", conn)
    conn.close()
    return df[column].tolist()

# ============================================================================
# UI COMPONENTS
# ============================================================================

def render_company_card(company, show_actions=True):
    """Render a company card."""
    priority_stars = "⭐" * (company.get('priority', 0) or 0)
    
    sector = company.get('iq_sector', '') or ''
    stage = company.get('stage_entreprise', '') or ''
    employees = company.get('employees', '')
    total_raised = company.get('total_raised', '')
    
    raised_str = f"${total_raised:.1f}M" if pd.notna(total_raised) and total_raised else "—"
    emp_str = f"{int(employees)} emp." if pd.notna(employees) and employees else ""
    
    html = f"""
    <div class="company-card">
        <div class="company-name">{company['name']} {priority_stars}</div>
        <div style="margin-bottom: 0.5rem;">
            <span class="tag tag-sector">{sector}</span>
            <span class="tag tag-stage">{stage}</span>
        </div>
        <div class="company-meta">
            {raised_str} raised • {emp_str}
        </div>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)

def render_metric_card(value, label, prefix="", suffix=""):
    """Render a metric card."""
    display_val = f"{prefix}{value}{suffix}"
    html = f"""
    <div class="metric-card">
        <div class="metric-value">{display_val}</div>
        <div class="metric-label">{label}</div>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)

# ============================================================================
# PAGES
# ============================================================================

def page_dashboard():
    """Dashboard with key metrics and charts."""
    st.title("📊 Tableau de Bord")
    
    df = get_all_companies()
    
    if len(df) == 0:
        st.info("Aucune entreprise dans la base de données. Importez vos données PitchBook dans l'onglet ⚙️ Paramètres.")
        return
    
    # Key metrics
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        render_metric_card(len(df), "Entreprises")
    
    with col2:
        active_pipeline = len(df[~df['pipeline_stage'].isin(['Pass', 'Closing'])])
        render_metric_card(active_pipeline, "Pipeline Actif")
    
    with col3:
        total_raised = df['total_raised'].sum()
        render_metric_card(f"{total_raised:.0f}", "Total Levé", suffix="M$")
    
    with col4:
        avg_employees = df['employees'].mean()
        render_metric_card(f"{avg_employees:.0f}", "Employés Moy.")
    
    with col5:
        priority = len(df[df['priority'] >= 3])
        render_metric_card(priority, "Haute Priorité")
    
    st.markdown("---")
    
    # Charts row
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Par Secteur")
        sector_counts = df['iq_sector'].value_counts().head(10)
        fig = px.bar(
            x=sector_counts.values, 
            y=sector_counts.index,
            orientation='h',
            color_discrete_sequence=['#63b3ed']
        )
        fig.update_layout(
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            font_color='#a0aec0',
            showlegend=False,
            xaxis_title="",
            yaxis_title="",
            margin=dict(l=0, r=0, t=10, b=0)
        )
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        st.subheader("Par Stade")
        stage_counts = df['pipeline_stage'].value_counts()
        fig = px.pie(
            values=stage_counts.values,
            names=stage_counts.index,
            hole=0.5,
            color_discrete_sequence=px.colors.sequential.Blues_r
        )
        fig.update_layout(
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            font_color='#a0aec0',
            margin=dict(l=0, r=0, t=10, b=0)
        )
        st.plotly_chart(fig, use_container_width=True)
    
    # Recent activity
    st.subheader("Activité Récente")
    recent = df.sort_values('updated_at', ascending=False).head(5)
    for _, company in recent.iterrows():
        col1, col2, col3 = st.columns([3, 2, 1])
        with col1:
            st.write(f"**{company['name']}**")
        with col2:
            st.write(company['pipeline_stage'])
        with col3:
            if company['updated_at']:
                st.write(company['updated_at'][:10])

def page_pipeline():
    """Kanban-style pipeline view."""
    st.title("🎯 Pipeline")
    
    df = get_all_companies()
    
    if len(df) == 0:
        st.info("Aucune entreprise. Importez vos données dans ⚙️ Paramètres.")
        return
    
    # Create columns for each pipeline stage
    cols = st.columns(len(PIPELINE_STAGES))
    
    for idx, stage in enumerate(PIPELINE_STAGES):
        with cols[idx]:
            stage_companies = df[df['pipeline_stage'] == stage]
            
            st.markdown(f"""
            <div class="pipeline-header">{stage} ({len(stage_companies)})</div>
            """, unsafe_allow_html=True)
            
            for _, company in stage_companies.iterrows():
                with st.container():
                    render_company_card(company, show_actions=False)
                    if st.button("Voir", key=f"view_{company['company_id']}"):
                        st.session_state['selected_company'] = company['company_id']
                        st.session_state['page'] = 'company_detail'
                        st.rerun()

def page_companies():
    """List view with filters and search."""
    st.title("🏢 Entreprises")
    
    # Sidebar filters
    with st.sidebar:
        st.subheader("🔍 Filtres")
        
        search = st.text_input("Recherche", placeholder="Nom, description...")
        
        sectors = get_unique_values('iq_sector')
        selected_sectors = st.multiselect("Secteur", sectors)
        
        stages = get_unique_values('stage_entreprise')
        selected_stages = st.multiselect("Stade Entreprise", stages)
        
        selected_pipeline = st.multiselect("Stade Pipeline", PIPELINE_STAGES)
        
        col1, col2 = st.columns(2)
        with col1:
            min_raised = st.number_input("Min Levé ($M)", value=0.0, step=0.5)
        with col2:
            max_raised = st.number_input("Max Levé ($M)", value=500.0, step=0.5)
        
        watchlist_only = st.checkbox("Watchlist seulement")
    
    # Build filters
    filters = {
        'search': search if search else None,
        'sectors': selected_sectors if selected_sectors else None,
        'stages': selected_stages if selected_stages else None,
        'pipeline_stages': selected_pipeline if selected_pipeline else None,
        'min_raised': min_raised if min_raised > 0 else None,
        'max_raised': max_raised if max_raised < 500 else None,
        'watchlist_only': watchlist_only
    }
    
    df = get_all_companies(filters)
    
    st.write(f"**{len(df)} entreprises**")
    
    if len(df) == 0:
        st.info("Aucun résultat avec ces filtres.")
        return
    
    # Display as interactive table
    for _, company in df.iterrows():
        col1, col2, col3, col4, col5 = st.columns([3, 2, 1.5, 1.5, 1])
        
        with col1:
            st.write(f"**{company['name']}**")
            st.caption(company.get('iq_sector', '') or '—')
        
        with col2:
            st.write(company.get('pipeline_stage', 'Prospect'))
        
        with col3:
            raised = company.get('total_raised')
            st.write(f"${raised:.1f}M" if pd.notna(raised) and raised else "—")
        
        with col4:
            emp = company.get('employees')
            st.write(f"{int(emp)}" if pd.notna(emp) else "—")
        
        with col5:
            if st.button("📝", key=f"edit_{company['company_id']}"):
                st.session_state['selected_company'] = company['company_id']
                st.session_state['page'] = 'company_detail'
                st.rerun()
        
        st.markdown("---")

def page_company_detail():
    """Detailed company view with editing."""
    company_id = st.session_state.get('selected_company')
    
    if not company_id:
        st.warning("Aucune entreprise sélectionnée.")
        return
    
    company = get_company(company_id)
    
    if company is None:
        st.error("Entreprise non trouvée.")
        return
    
    # Header
    col1, col2 = st.columns([4, 1])
    with col1:
        st.title(company['name'])
    with col2:
        if st.button("← Retour"):
            st.session_state['page'] = 'companies'
            st.rerun()
    
    # Main content
    tab1, tab2, tab3 = st.tabs(["📋 Informations", "📊 Tracking", "📝 Activités"])
    
    with tab1:
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("Profil")
            st.write(f"**Secteur:** {company.get('iq_sector', '—')}")
            st.write(f"**Stade:** {company.get('stage_entreprise', '—')}")
            st.write(f"**Location:** {company.get('hq_location', '—')}")
            st.write(f"**Fondée:** {company.get('year_founded', '—')}")
            st.write(f"**Employés:** {company.get('employees', '—')}")
            st.write(f"**Site web:** {company.get('website', '—')}")
        
        with col2:
            st.subheader("Financement")
            raised = company.get('total_raised')
            st.write(f"**Total Levé:** ${raised:.2f}M" if pd.notna(raised) else "**Total Levé:** —")
            
            last_size = company.get('last_financing_size')
            st.write(f"**Dernier Round:** ${last_size:.2f}M" if pd.notna(last_size) else "**Dernier Round:** —")
            st.write(f"**Date:** {company.get('last_financing_date', '—')}")
            
            valuation = company.get('last_valuation')
            st.write(f"**Valuation:** ${valuation:.2f}M" if pd.notna(valuation) else "**Valuation:** —")
        
        st.subheader("Description")
        st.write(company.get('description', 'Aucune description disponible.'))
        
        st.subheader("Investisseurs")
        st.write(f"**Actifs:** {company.get('active_investors', '—')}")
        st.write(f"**Anciens:** {company.get('former_investors', '—')}")
    
    with tab2:
        st.subheader("Suivi Pipeline")
        
        col1, col2 = st.columns(2)
        
        with col1:
            new_stage = st.selectbox(
                "Stade Pipeline",
                PIPELINE_STAGES,
                index=PIPELINE_STAGES.index(company.get('pipeline_stage', 'Prospect')) 
                    if company.get('pipeline_stage') in PIPELINE_STAGES else 0
            )
            
            new_priority = st.slider("Priorité", 0, 5, company.get('priority', 0) or 0)
            
            new_assigned = st.text_input("Assigné à", company.get('assigned_to', '') or '')
        
        with col2:
            new_next_action = st.text_input("Prochaine Action", company.get('next_action', '') or '')
            
            current_date = None
            if company.get('next_action_date'):
                try:
                    current_date = datetime.strptime(company['next_action_date'][:10], '%Y-%m-%d').date()
                except:
                    pass
            
            new_next_date = st.date_input("Date Échéance", current_date)
            
            new_tags = st.text_input("Tags (séparés par virgule)", company.get('tags', '') or '')
        
        new_notes = st.text_area("Notes", company.get('notes', '') or '', height=150)
        
        if st.button("💾 Sauvegarder", type="primary"):
            updates = {
                'pipeline_stage': new_stage,
                'priority': new_priority,
                'assigned_to': new_assigned,
                'next_action': new_next_action,
                'next_action_date': new_next_date.isoformat() if new_next_date else None,
                'tags': new_tags,
                'notes': new_notes
            }
            update_company(company_id, updates)
            
            # Log stage change
            if new_stage != company.get('pipeline_stage'):
                add_activity(company_id, 'stage_change', 
                    f"Pipeline stage changed from {company.get('pipeline_stage')} to {new_stage}")
            
            st.success("Sauvegardé!")
            st.rerun()
    
    with tab3:
        st.subheader("Journal d'Activités")
        
        # Add new activity
        col1, col2 = st.columns([2, 1])
        with col1:
            activity_desc = st.text_input("Nouvelle activité")
        with col2:
            activity_type = st.selectbox("Type", ["Note", "Appel", "Email", "Réunion", "Due Diligence"])
        
        if st.button("Ajouter") and activity_desc:
            add_activity(company_id, activity_type, activity_desc)
            st.success("Activité ajoutée!")
            st.rerun()
        
        st.markdown("---")
        
        # Show activity log
        activities = get_activities(company_id)
        
        if len(activities) == 0:
            st.info("Aucune activité enregistrée.")
        else:
            for _, activity in activities.iterrows():
                col1, col2 = st.columns([4, 1])
                with col1:
                    st.write(f"**{activity['activity_type']}:** {activity['description']}")
                with col2:
                    st.caption(activity['created_at'][:10])

def page_settings():
    """Settings and data import."""
    st.title("⚙️ Paramètres")
    
    st.subheader("📥 Import de Données")
    st.write("Importez votre export PitchBook (fichier Excel).")
    
    uploaded_file = st.file_uploader("Fichier Excel PitchBook", type=['xlsx', 'xls'])
    
    if uploaded_file:
        if st.button("Importer", type="primary"):
            with st.spinner("Import en cours..."):
                imported, skipped = import_pitchbook_data(uploaded_file)
                st.success(f"✅ {imported} entreprises importées, {skipped} déjà existantes.")
    
    st.markdown("---")
    
    st.subheader("📊 Statistiques Base de Données")
    
    df = get_all_companies()
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Entreprises", len(df))
    with col2:
        sectors = df['iq_sector'].nunique()
        st.metric("Secteurs", sectors)
    with col3:
        conn = get_connection()
        activities = pd.read_sql("SELECT COUNT(*) as count FROM activities", conn)
        conn.close()
        st.metric("Activités Loggées", activities['count'].iloc[0])
    
    st.markdown("---")
    
    st.subheader("📤 Export")
    
    if len(df) > 0:
        csv = df.to_csv(index=False)
        st.download_button(
            "Télécharger CSV",
            csv,
            "quebec_pipeline_export.csv",
            "text/csv"
        )

# ============================================================================
# MAIN APP
# ============================================================================

def main():
    # Initialize database
    init_database()
    
    # Initialize traction tables
    try:
        from traction.scraper import TractionScraper
        TractionScraper()._init_traction_tables()
    except:
        pass
    
    # Initialize session state
    if 'page' not in st.session_state:
        st.session_state['page'] = 'dashboard'
    
    # Sidebar navigation
    with st.sidebar:
        st.image("https://via.placeholder.com/200x50/1a1f2e/63b3ed?text=QC+Pipeline", width=200)
        st.markdown("---")
        
        if st.button("📊 Tableau de Bord", use_container_width=True):
            st.session_state['page'] = 'dashboard'
            st.rerun()
        
        if st.button("🎯 Pipeline", use_container_width=True):
            st.session_state['page'] = 'pipeline'
            st.rerun()
        
        if st.button("🏢 Entreprises", use_container_width=True):
            st.session_state['page'] = 'companies'
            st.rerun()
        
        if st.button("📈 Traction", use_container_width=True):
            st.session_state['page'] = 'traction'
            st.rerun()
        
        if st.button("⚙️ Paramètres", use_container_width=True):
            st.session_state['page'] = 'settings'
            st.rerun()
        
        st.markdown("---")
        st.caption("Quebec Startup Pipeline Tracker v1.1")
    
    # Route to page
    page = st.session_state.get('page', 'dashboard')
    
    if page == 'dashboard':
        page_dashboard()
    elif page == 'pipeline':
        page_pipeline()
    elif page == 'companies':
        page_companies()
    elif page == 'company_detail':
        page_company_detail()
    elif page == 'settings':
        page_settings()
    elif page == 'traction':
        # Import and run traction dashboard
        try:
            from pages.traction_dashboard import page_traction_dashboard
            page_traction_dashboard()
        except ImportError as e:
            st.error(f"Traction module not found. Ensure traction/ folder exists. Error: {e}")
            st.info("Install dependencies: pip install beautifulsoup4 feedparser")

if __name__ == "__main__":
    main()
