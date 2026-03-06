"""
Traction Dashboard - Streamlit page component
High-traction tracker with growth scoring.
"""

import streamlit as st
import pandas as pd
import sqlite3
import json
from datetime import datetime
import plotly.express as px
import plotly.graph_objects as go

from traction.scraper import TractionScraper, GrowthScorer


def get_connection(db_path="pipeline_data.db"):
    return sqlite3.connect(db_path)


def page_traction_dashboard():
    """Main traction tracking dashboard."""
    st.title("📈 Traction Tracker")
    st.caption("Growth signals & investment potential scoring")
    
    # Tabs
    tab1, tab2, tab3 = st.tabs(["🏆 Top Movers", "🔍 Analyze Company", "⚙️ Batch Scan"])
    
    with tab1:
        render_top_movers()
    
    with tab2:
        render_company_analysis()
    
    with tab3:
        render_batch_scan()


def safe_string(val):
    """Convert bytes or other types to string safely."""
    if val is None:
        return ""
    if isinstance(val, bytes):
        return val.decode('utf-8', errors='ignore')
    return str(val)


def render_top_movers():
    """Show companies ranked by growth score."""
    st.subheader("Highest Growth Potential")
    
    conn = get_connection()
    
    # Get latest scores with company info
    query = """
        SELECT 
            gs.company_id,
            c.name,
            c.iq_sector,
            c.stage_entreprise,
            c.total_raised,
            c.employees,
            c.pipeline_stage,
            gs.growth_score,
            gs.hiring_velocity_score,
            gs.funding_momentum_score,
            gs.news_buzz_score,
            gs.confidence,
            gs.factors_positive,
            gs.score_date
        FROM growth_scores gs
        JOIN companies c ON gs.company_id = c.company_id
        WHERE gs.id IN (
            SELECT MAX(id) FROM growth_scores GROUP BY company_id
        )
        ORDER BY gs.growth_score DESC
    """
    
    try:
        df = pd.read_sql(query, conn)
        # Convert any bytes columns to strings
        for col in df.columns:
            if df[col].dtype == object:
                df[col] = df[col].apply(lambda x: x.decode('utf-8', errors='ignore') if isinstance(x, bytes) else x)
    except Exception as e:
        st.error(f"Database error: {e}")
        df = pd.DataFrame()
    
    conn.close()
    
    if len(df) == 0:
        st.info("Aucun score de croissance calculé. Utilisez l'onglet 'Analyze Company' ou 'Batch Scan' pour commencer.")
        return
    
    # Metrics row
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Companies Scored", len(df))
    with col2:
        avg_score = df["growth_score"].mean()
        st.metric("Avg Growth Score", f"{avg_score:.1f}")
    with col3:
        high_potential = len(df[df["growth_score"] >= 60])
        st.metric("High Potential (60+)", high_potential)
    with col4:
        actively_hiring = len(df[df["hiring_velocity_score"] >= 40])
        st.metric("Actively Hiring", actively_hiring)
    
    st.markdown("---")
    
    # Score distribution chart
    col1, col2 = st.columns([2, 1])
    
    with col1:
        # Top 10 bar chart
        top_10 = df.head(10)
        fig = go.Figure()
        
        fig.add_trace(go.Bar(
            y=top_10["name"],
            x=top_10["growth_score"],
            orientation="h",
            marker_color=top_10["growth_score"],
            marker_colorscale="Blues",
            text=top_10["growth_score"].round(1),
            textposition="inside"
        ))
        
        fig.update_layout(
            title="Top 10 by Growth Score",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font_color="#a0aec0",
            height=400,
            yaxis=dict(autorange="reversed"),
            xaxis=dict(range=[0, 100], title="Growth Score"),
            margin=dict(l=10, r=10, t=40, b=10)
        )
        
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        # Score breakdown radar for #1 company
        if len(top_10) > 0:
            top_company = top_10.iloc[0]
            st.markdown(f"### #{1} {top_company['name']}")
            
            categories = ["Hiring", "Funding", "News", "Confidence"]
            values = [
                top_company["hiring_velocity_score"],
                top_company["funding_momentum_score"],
                top_company["news_buzz_score"],
                top_company["confidence"]
            ]
            
            fig = go.Figure()
            fig.add_trace(go.Scatterpolar(
                r=values + [values[0]],
                theta=categories + [categories[0]],
                fill="toself",
                line_color="#63b3ed",
                fillcolor="rgba(99, 179, 237, 0.3)"
            ))
            
            fig.update_layout(
                polar=dict(
                    radialaxis=dict(visible=True, range=[0, 100]),
                    bgcolor="rgba(0,0,0,0)"
                ),
                paper_bgcolor="rgba(0,0,0,0)",
                font_color="#a0aec0",
                height=300,
                margin=dict(l=40, r=40, t=20, b=20),
                showlegend=False
            )
            
            st.plotly_chart(fig, use_container_width=True)
            
            # Positive factors
            factors_raw = top_company.get("factors_positive", "[]") or "[]"
            if isinstance(factors_raw, bytes):
                factors_raw = factors_raw.decode('utf-8', errors='ignore')
            try:
                factors = json.loads(factors_raw)
            except:
                factors = []
            if factors:
                st.markdown("**Growth Signals:**")
                for f in factors:
                    st.markdown(f"✅ {f}")
    
    st.markdown("---")
    
    # Full table
    st.subheader("All Scored Companies")
    
    display_df = df[[
        "name", "iq_sector", "pipeline_stage", "growth_score", 
        "hiring_velocity_score", "funding_momentum_score", "confidence"
    ]].rename(columns={
        "name": "Company",
        "iq_sector": "Sector",
        "pipeline_stage": "Pipeline",
        "growth_score": "Score",
        "hiring_velocity_score": "Hiring",
        "funding_momentum_score": "Funding",
        "confidence": "Confidence %"
    })
    
    st.dataframe(
        display_df.style.background_gradient(subset=["Score"], cmap="Blues"),
        use_container_width=True,
        hide_index=True
    )


def render_company_analysis():
    """Analyze a single company's traction."""
    st.subheader("Analyze Company Traction")
    
    conn = get_connection()
    companies = pd.read_sql("SELECT company_id, name, website FROM companies ORDER BY name", conn)
    conn.close()
    
    if len(companies) == 0:
        st.warning("Aucune entreprise dans la base. Importez d'abord vos données.")
        return
    
    # Convert any bytes columns to strings
    for col in companies.columns:
        if companies[col].dtype == object:
            companies[col] = companies[col].apply(lambda x: x.decode('utf-8', errors='ignore') if isinstance(x, bytes) else x)
    
    # Company selector
    company_options = {row["name"]: row["company_id"] for _, row in companies.iterrows()}
    selected_name = st.selectbox("Sélectionner une entreprise", list(company_options.keys()))
    selected_id = company_options[selected_name]
    
    # Get company details
    conn = get_connection()
    company = pd.read_sql(
        "SELECT * FROM companies WHERE company_id = ?", 
        conn, params=(selected_id,)
    ).iloc[0]
    conn.close()
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.markdown(f"**Website:** {company.get('website', '—')}")
        st.markdown(f"**Sector:** {company.get('iq_sector', '—')}")
        st.markdown(f"**Employees:** {company.get('employees', '—')}")
        st.markdown(f"**Total Raised:** ${company.get('total_raised', 0) or 0:.2f}M")
    
    with col2:
        github_url = st.text_input("GitHub URL (optional)", placeholder="https://github.com/company")
    
    # Scan button
    if st.button("🔍 Scan Traction Signals", type="primary"):
        with st.spinner("Scanning web sources..."):
            scraper = TractionScraper()
            
            snapshot = scraper.collect_traction_snapshot(
                company_id=selected_id,
                company_name=selected_name,
                website=company.get("website"),
                github_url=github_url if github_url else None
            )
            
            # Calculate score
            scorer = GrowthScorer()
            score = scorer.calculate_growth_score(selected_id)
        
        st.success("Scan complete!")
        
        # Display results
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("Growth Score", f"{score['growth_score']:.1f}/100")
        with col2:
            st.metric("Confidence", f"{score['confidence']:.0f}%")
        with col3:
            st.metric("News Mentions", snapshot["news"].get("mentions_count", 0))
        
        st.markdown("---")
        
        # Score breakdown
        st.subheader("Score Components")
        
        components = score.get("components", {})
        for name, value in components.items():
            label = name.replace("_", " ").title()
            st.progress(value / 100, text=f"{label}: {value:.1f}")
        
        # Factors
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**✅ Positive Signals**")
            for f in score.get("factors_positive", []):
                st.markdown(f"- {f}")
            if not score.get("factors_positive"):
                st.markdown("_None detected_")
        
        with col2:
            st.markdown("**⚠️ Concerns**")
            for f in score.get("factors_negative", []):
                st.markdown(f"- {f}")
            if not score.get("factors_negative"):
                st.markdown("_None detected_")
        
        # Raw data expander
        with st.expander("View Raw Scan Data"):
            st.json(snapshot)
    
    # Show existing scores
    st.markdown("---")
    st.subheader("Score History")
    
    conn = get_connection()
    history = pd.read_sql(
        "SELECT * FROM growth_scores WHERE company_id = ? ORDER BY score_date DESC LIMIT 10",
        conn, params=(selected_id,)
    )
    conn.close()
    
    if len(history) > 0:
        st.dataframe(history[["score_date", "growth_score", "confidence"]], hide_index=True)
    else:
        st.info("No scan history for this company yet.")


def render_batch_scan():
    """Batch scan multiple companies."""
    st.subheader("Batch Traction Scan")
    st.caption("Scan multiple companies at once (respects rate limits)")
    
    conn = get_connection()
    companies = pd.read_sql("""
        SELECT c.company_id, c.name, c.website, c.iq_sector, c.pipeline_stage,
               (SELECT MAX(score_date) FROM growth_scores gs WHERE gs.company_id = c.company_id) as last_scan
        FROM companies c
        ORDER BY c.name
    """, conn)
    conn.close()
    
    if len(companies) == 0:
        st.warning("Aucune entreprise dans la base.")
        return
    
    # Convert any bytes columns to strings
    for col in companies.columns:
        if companies[col].dtype == object:
            companies[col] = companies[col].apply(lambda x: x.decode('utf-8', errors='ignore') if isinstance(x, bytes) else x)
    
    # Filters
    col1, col2, col3 = st.columns(3)
    
    with col1:
        sectors = ["All"] + companies["iq_sector"].dropna().unique().tolist()
        selected_sector = st.selectbox("Filter by Sector", sectors)
    
    with col2:
        pipeline_stages = ["All"] + companies["pipeline_stage"].dropna().unique().tolist()
        selected_pipeline = st.selectbox("Filter by Pipeline Stage", pipeline_stages)
    
    with col3:
        scan_unscanned = st.checkbox("Only unscanned companies", value=True)
    
    # Apply filters
    filtered = companies.copy()
    if selected_sector != "All":
        filtered = filtered[filtered["iq_sector"] == selected_sector]
    if selected_pipeline != "All":
        filtered = filtered[filtered["pipeline_stage"] == selected_pipeline]
    if scan_unscanned:
        filtered = filtered[filtered["last_scan"].isna()]
    
    st.write(f"**{len(filtered)} companies** match your criteria")
    
    # Limit selector
    max_companies = st.slider("Max companies to scan", 1, min(50, len(filtered)), min(10, len(filtered)))
    
    # Preview
    st.dataframe(filtered.head(max_companies)[["name", "iq_sector", "website", "last_scan"]], hide_index=True)
    
    # Scan button
    if st.button("🚀 Start Batch Scan", type="primary"):
        scraper = TractionScraper()
        scorer = GrowthScorer()
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        results_container = st.container()
        
        results = []
        
        for idx, (_, company) in enumerate(filtered.head(max_companies).iterrows()):
            progress = (idx + 1) / max_companies
            progress_bar.progress(progress)
            status_text.text(f"Scanning {idx + 1}/{max_companies}: {company['name']}")
            
            try:
                # Collect traction
                snapshot = scraper.collect_traction_snapshot(
                    company_id=company["company_id"],
                    company_name=company["name"],
                    website=company.get("website")
                )
                
                # Calculate score
                score = scorer.calculate_growth_score(company["company_id"])
                
                results.append({
                    "name": company["name"],
                    "score": score.get("growth_score", 0),
                    "status": "✅"
                })
                
            except Exception as e:
                results.append({
                    "name": company["name"],
                    "score": 0,
                    "status": f"❌ {str(e)[:30]}"
                })
        
        progress_bar.progress(1.0)
        status_text.text("Complete!")
        
        with results_container:
            st.success(f"Scanned {len(results)} companies")
            
            results_df = pd.DataFrame(results).sort_values("score", ascending=False)
            st.dataframe(results_df, hide_index=True)


if __name__ == "__main__":
    page_traction_dashboard()
