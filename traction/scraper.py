"""
Traction Scraper Module
Collects growth signals from various public sources.
"""

import requests
from bs4 import BeautifulSoup
import feedparser
import re
import time
import sqlite3
from datetime import datetime, timedelta
from urllib.parse import urlparse, quote_plus
import json
from typing import Optional, Dict, List, Any, Tuple
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Respectful scraping settings
REQUEST_DELAY = 2  # seconds between requests
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"


class TractionScraper:
    """Scrapes public traction signals for startups."""
    
    def __init__(self, db_path: str = "pipeline_data.db"):
        self.db_path = db_path
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT})
        self._init_traction_tables()
    
    def _init_traction_tables(self):
        """Initialize traction tracking tables."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        # Traction snapshots (point-in-time measurements)
        c.execute("""
            CREATE TABLE IF NOT EXISTS traction_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company_id TEXT,
                snapshot_date TEXT,
                
                -- Employee signals
                linkedin_employees INTEGER,
                linkedin_followers INTEGER,
                job_postings_count INTEGER,
                
                -- Web presence
                website_status INTEGER,
                has_blog INTEGER,
                has_careers_page INTEGER,
                tech_stack TEXT,
                
                -- Social/News
                news_mentions_30d INTEGER,
                news_sentiment_avg REAL,
                twitter_followers INTEGER,
                
                -- GitHub (if applicable)
                github_stars INTEGER,
                github_forks INTEGER,
                github_contributors INTEGER,
                github_commits_30d INTEGER,
                
                -- Computed
                raw_data TEXT,
                
                FOREIGN KEY (company_id) REFERENCES companies(company_id)
            )
        """)
        
        # Growth scores (computed from snapshots)
        c.execute("""
            CREATE TABLE IF NOT EXISTS growth_scores (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company_id TEXT,
                score_date TEXT,
                
                -- Component scores (0-100)
                hiring_velocity_score REAL,
                funding_momentum_score REAL,
                news_buzz_score REAL,
                web_presence_score REAL,
                tech_activity_score REAL,
                
                -- Overall
                growth_score REAL,
                growth_trend TEXT,
                confidence REAL,
                
                -- Metadata
                factors_positive TEXT,
                factors_negative TEXT,
                
                FOREIGN KEY (company_id) REFERENCES companies(company_id)
            )
        """)
        
        conn.commit()
        conn.close()
    
    def _safe_request(self, url: str, timeout: int = 10) -> Optional[requests.Response]:
        """Make a rate-limited, error-handled request."""
        try:
            time.sleep(REQUEST_DELAY)
            response = self.session.get(url, timeout=timeout)
            response.raise_for_status()
            return response
        except Exception as e:
            logger.warning(f"Request failed for {url}: {e}")
            return None
    
    # =========================================================================
    # NEWS SCRAPING
    # =========================================================================
    
    def scrape_news_mentions(self, company_name: str, days: int = 30) -> Dict[str, Any]:
        """
        Scrape news mentions from Google News RSS.
        Returns count and basic sentiment.
        """
        results = {
            "mentions_count": 0,
            "articles": [],
            "sentiment_avg": 0.0
        }
        
        try:
            # Google News RSS feed
            query = quote_plus(f'"{company_name}" startup OR tech OR funding')
            rss_url = f"https://news.google.com/rss/search?q={query}&hl=en-CA&gl=CA&ceid=CA:en"
            
            feed = feedparser.parse(rss_url)
            
            cutoff_date = datetime.now() - timedelta(days=days)
            
            for entry in feed.entries[:20]:  # Limit to 20 articles
                try:
                    pub_date = datetime(*entry.published_parsed[:6])
                    if pub_date >= cutoff_date:
                        results["articles"].append({
                            "title": entry.title,
                            "link": entry.link,
                            "date": pub_date.isoformat(),
                            "source": entry.get("source", {}).get("title", "Unknown")
                        })
                except:
                    continue
            
            results["mentions_count"] = len(results["articles"])
            
            # Basic sentiment (keyword-based, simple)
            positive_words = ["raises", "funding", "growth", "launch", "expansion", "partnership", "award"]
            negative_words = ["layoff", "shutdown", "lawsuit", "decline", "struggles", "cuts"]
            
            sentiment_scores = []
            for article in results["articles"]:
                title_lower = article["title"].lower()
                pos = sum(1 for w in positive_words if w in title_lower)
                neg = sum(1 for w in negative_words if w in title_lower)
                sentiment_scores.append((pos - neg) / max(pos + neg, 1))
            
            if sentiment_scores:
                results["sentiment_avg"] = sum(sentiment_scores) / len(sentiment_scores)
        
        except Exception as e:
            logger.error(f"News scraping failed for {company_name}: {e}")
        
        return results
    
    # =========================================================================
    # WEBSITE ANALYSIS
    # =========================================================================
    
    def analyze_website(self, website_url: str) -> Dict[str, Any]:
        """
        Analyze company website for signals.
        """
        results = {
            "status": None,
            "has_blog": False,
            "has_careers": False,
            "has_pricing": False,
            "tech_signals": [],
            "job_links": []
        }
        
        if not website_url or website_url == "—":
            return results
        
        # Ensure URL has scheme
        if not website_url.startswith("http"):
            website_url = f"https://{website_url}"
        
        response = self._safe_request(website_url)
        if not response:
            results["status"] = 0
            return results
        
        results["status"] = response.status_code
        
        try:
            soup = BeautifulSoup(response.text, "html.parser")
            html_lower = response.text.lower()
            
            # Check for key pages
            all_links = [a.get("href", "").lower() for a in soup.find_all("a")]
            link_text = " ".join(all_links)
            
            results["has_blog"] = any(x in link_text for x in ["/blog", "/news", "/articles"])
            results["has_careers"] = any(x in link_text for x in ["/careers", "/jobs", "jobs.", "careers.", "/join", "workable", "greenhouse", "lever.co"])
            results["has_pricing"] = any(x in link_text for x in ["/pricing", "/plans", "/subscribe"])
            
            # Tech stack signals (from HTML)
            tech_patterns = {
                "React": ["react", "_next"],
                "Vue": ["vue.js", "__vue"],
                "Angular": ["ng-", "angular"],
                "Shopify": ["shopify", "myshopify"],
                "WordPress": ["wp-content", "wordpress"],
                "HubSpot": ["hubspot", "hs-scripts"],
                "Intercom": ["intercom"],
                "Stripe": ["stripe"],
                "Segment": ["segment.com", "analytics.js"],
                "Mixpanel": ["mixpanel"],
                "Google Analytics": ["google-analytics", "gtag"],
            }
            
            for tech, patterns in tech_patterns.items():
                if any(p in html_lower for p in patterns):
                    results["tech_signals"].append(tech)
            
            # Find career page links
            for a in soup.find_all("a", href=True):
                href = a["href"].lower()
                if any(x in href for x in ["careers", "jobs", "greenhouse", "lever.co", "workable"]):
                    full_url = href if href.startswith("http") else f"{website_url.rstrip('/')}/{href.lstrip('/')}"
                    results["job_links"].append(full_url)
        
        except Exception as e:
            logger.error(f"Website analysis failed for {website_url}: {e}")
        
        return results
    
    # =========================================================================
    # JOB POSTINGS
    # =========================================================================
    
    def count_job_postings(self, company_name: str, careers_url: Optional[str] = None) -> Dict[str, Any]:
        """
        Estimate job posting count from various sources.
        """
        results = {
            "total_jobs": 0,
            "sources": {},
            "job_titles": []
        }
        
        # Try LinkedIn Jobs (public search)
        try:
            linkedin_query = quote_plus(company_name)
            linkedin_url = f"https://www.linkedin.com/jobs/search/?keywords={linkedin_query}&location=Canada"
            # Note: LinkedIn blocks scraping, this is just for structure
            # In production, you'd use LinkedIn API or a service like PhantomBuster
            results["sources"]["linkedin_search_url"] = linkedin_url
        except:
            pass
        
        # Try Indeed RSS
        try:
            indeed_query = quote_plus(company_name)
            indeed_rss = f"https://ca.indeed.com/rss?q={indeed_query}&l=Quebec"
            feed = feedparser.parse(indeed_rss)
            
            indeed_jobs = []
            for entry in feed.entries[:10]:
                if company_name.lower() in entry.title.lower() or company_name.lower() in entry.get("summary", "").lower():
                    indeed_jobs.append(entry.title)
            
            results["sources"]["indeed"] = len(indeed_jobs)
            results["job_titles"].extend(indeed_jobs)
            results["total_jobs"] += len(indeed_jobs)
        except Exception as e:
            logger.warning(f"Indeed scraping failed: {e}")
        
        # Try careers page if provided
        if careers_url:
            response = self._safe_request(careers_url)
            if response:
                try:
                    soup = BeautifulSoup(response.text, "html.parser")
                    
                    # Common job listing patterns
                    job_elements = soup.find_all(class_=re.compile(r"job|position|opening|role|career", re.I))
                    job_elements += soup.find_all("li", string=re.compile(r"engineer|developer|manager|analyst|designer|sales", re.I))
                    
                    results["sources"]["careers_page"] = len(job_elements)
                    results["total_jobs"] += len(job_elements)
                except:
                    pass
        
        return results
    
    # =========================================================================
    # GITHUB ACTIVITY
    # =========================================================================
    
    def scrape_github(self, github_url: str) -> Dict[str, Any]:
        """
        Scrape GitHub organization/repo stats (public API, no auth needed for basic).
        """
        results = {
            "stars": 0,
            "forks": 0,
            "contributors": 0,
            "recent_commits": 0,
            "repos": []
        }
        
        if not github_url:
            return results
        
        try:
            # Parse GitHub URL to get org/user
            parsed = urlparse(github_url)
            path_parts = parsed.path.strip("/").split("/")
            
            if not path_parts:
                return results
            
            org_or_user = path_parts[0]
            
            # Get repos via API (no auth, rate limited but works)
            api_url = f"https://api.github.com/users/{org_or_user}/repos?per_page=10&sort=updated"
            response = self._safe_request(api_url)
            
            if response:
                repos = response.json()
                
                for repo in repos[:5]:
                    results["stars"] += repo.get("stargazers_count", 0)
                    results["forks"] += repo.get("forks_count", 0)
                    results["repos"].append({
                        "name": repo["name"],
                        "stars": repo.get("stargazers_count", 0),
                        "updated": repo.get("updated_at")
                    })
        
        except Exception as e:
            logger.error(f"GitHub scraping failed for {github_url}: {e}")
        
        return results
    
    # =========================================================================
    # MAIN COLLECTION
    # =========================================================================
    
    def collect_traction_snapshot(self, company_id: str, company_name: str, 
                                   website: str = None, github_url: str = None) -> Dict[str, Any]:
        """
        Collect all traction signals for a company.
        """
        logger.info(f"Collecting traction for: {company_name}")
        
        snapshot = {
            "company_id": company_id,
            "company_name": company_name,
            "snapshot_date": datetime.now().isoformat(),
            "news": {},
            "website": {},
            "jobs": {},
            "github": {}
        }
        
        # News mentions
        snapshot["news"] = self.scrape_news_mentions(company_name)
        
        # Website analysis
        if website:
            snapshot["website"] = self.analyze_website(website)
            
            # Job postings (use careers link if found)
            careers_url = snapshot["website"].get("job_links", [None])[0] if snapshot["website"].get("job_links") else None
            snapshot["jobs"] = self.count_job_postings(company_name, careers_url)
        
        # GitHub
        if github_url:
            snapshot["github"] = self.scrape_github(github_url)
        
        # Save to database
        self._save_snapshot(snapshot)
        
        return snapshot
    
    def _save_snapshot(self, snapshot: Dict[str, Any]):
        """Save traction snapshot to database."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        c.execute("""
            INSERT INTO traction_snapshots (
                company_id, snapshot_date,
                job_postings_count, news_mentions_30d, news_sentiment_avg,
                website_status, has_blog, has_careers_page, tech_stack,
                github_stars, github_forks,
                raw_data
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            snapshot["company_id"],
            snapshot["snapshot_date"],
            snapshot["jobs"].get("total_jobs", 0),
            snapshot["news"].get("mentions_count", 0),
            snapshot["news"].get("sentiment_avg", 0),
            snapshot["website"].get("status"),
            1 if snapshot["website"].get("has_blog") else 0,
            1 if snapshot["website"].get("has_careers") else 0,
            json.dumps(snapshot["website"].get("tech_signals", [])),
            snapshot["github"].get("stars", 0),
            snapshot["github"].get("forks", 0),
            json.dumps(snapshot)
        ))
        
        conn.commit()
        conn.close()


# =============================================================================
# GROWTH SCORING ENGINE
# =============================================================================

class GrowthScorer:
    """Calculates growth potential scores from traction data."""
    
    def __init__(self, db_path: str = "pipeline_data.db"):
        self.db_path = db_path
    
    def calculate_growth_score(self, company_id: str) -> Dict[str, Any]:
        """
        Calculate comprehensive growth score for a company.
        Returns score components and overall score (0-100).
        """
        conn = sqlite3.connect(self.db_path)
        
        # Get latest snapshot
        snapshot_df = pd.read_sql("""
            SELECT * FROM traction_snapshots 
            WHERE company_id = ? 
            ORDER BY snapshot_date DESC LIMIT 1
        """, conn, params=(company_id,))
        
        # Get company data
        company_df = pd.read_sql("""
            SELECT * FROM companies WHERE company_id = ?
        """, conn, params=(company_id,))
        
        conn.close()
        
        if len(snapshot_df) == 0 or len(company_df) == 0:
            return {"error": "No data available"}
        
        snapshot = snapshot_df.iloc[0]
        company = company_df.iloc[0]
        
        scores = {
            "company_id": company_id,
            "score_date": datetime.now().isoformat(),
            "components": {},
            "factors_positive": [],
            "factors_negative": []
        }
        
        # --- Hiring Velocity Score (0-100) ---
        job_count = snapshot.get("job_postings_count", 0) or 0
        employees = company.get("employees", 0) or 1
        
        # Hiring ratio (jobs / employees) - higher is better for growth
        hiring_ratio = job_count / max(employees, 1)
        hiring_score = min(100, hiring_ratio * 200)  # 50% hiring = 100 score
        
        scores["components"]["hiring_velocity"] = round(hiring_score, 1)
        if hiring_score > 50:
            scores["factors_positive"].append(f"Active hiring ({job_count} positions)")
        elif job_count == 0:
            scores["factors_negative"].append("No visible job postings")
        
        # --- Funding Momentum Score (0-100) ---
        total_raised = company.get("total_raised", 0) or 0
        last_financing_date = company.get("last_financing_date")
        
        funding_score = 0
        if total_raised > 0:
            funding_score += min(40, total_raised * 2)  # Up to 40 points for amount
        
        if last_financing_date:
            try:
                last_date = datetime.strptime(str(last_financing_date)[:10], "%Y-%m-%d")
                months_ago = (datetime.now() - last_date).days / 30
                if months_ago < 12:
                    funding_score += 60 - (months_ago * 5)  # Recent = more points
                    scores["factors_positive"].append(f"Recent funding ({months_ago:.0f} months ago)")
            except:
                pass
        
        scores["components"]["funding_momentum"] = round(min(100, funding_score), 1)
        
        # --- News Buzz Score (0-100) ---
        news_count = snapshot.get("news_mentions_30d", 0) or 0
        sentiment = snapshot.get("news_sentiment_avg", 0) or 0
        
        news_score = min(50, news_count * 10)  # Up to 50 for volume
        news_score += max(-20, min(50, sentiment * 50))  # Up to 50 for sentiment
        
        scores["components"]["news_buzz"] = round(max(0, min(100, news_score)), 1)
        if news_count > 3:
            scores["factors_positive"].append(f"Good media presence ({news_count} mentions)")
        
        # --- Web Presence Score (0-100) ---
        web_score = 0
        if snapshot.get("website_status") == 200:
            web_score += 30
        if snapshot.get("has_blog"):
            web_score += 20
            scores["factors_positive"].append("Active blog/content")
        if snapshot.get("has_careers_page"):
            web_score += 20
        
        tech_stack = json.loads(snapshot.get("tech_stack", "[]") or "[]")
        web_score += min(30, len(tech_stack) * 10)  # Modern tech stack
        
        scores["components"]["web_presence"] = round(web_score, 1)
        
        # --- Tech Activity Score (0-100) ---
        github_stars = snapshot.get("github_stars", 0) or 0
        
        tech_score = min(100, github_stars / 10)  # 1000 stars = 100
        scores["components"]["tech_activity"] = round(tech_score, 1)
        
        if github_stars > 100:
            scores["factors_positive"].append(f"Strong OSS presence ({github_stars} stars)")
        
        # --- OVERALL GROWTH SCORE ---
        weights = {
            "hiring_velocity": 0.25,
            "funding_momentum": 0.30,
            "news_buzz": 0.15,
            "web_presence": 0.15,
            "tech_activity": 0.15
        }
        
        overall = sum(
            scores["components"].get(k, 0) * w 
            for k, w in weights.items()
        )
        
        scores["growth_score"] = round(overall, 1)
        
        # Trend (would need historical data)
        scores["growth_trend"] = "stable"  # TODO: compare with previous scores
        
        # Confidence based on data availability
        data_points = sum([
            1 if job_count > 0 else 0,
            1 if total_raised > 0 else 0,
            1 if news_count > 0 else 0,
            1 if snapshot.get("website_status") else 0,
            1 if github_stars > 0 else 0
        ])
        scores["confidence"] = round(data_points / 5 * 100, 0)
        
        # Save score
        self._save_score(scores)
        
        return scores
    
    def _save_score(self, scores: Dict[str, Any]):
        """Save growth score to database."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        c.execute("""
            INSERT INTO growth_scores (
                company_id, score_date,
                hiring_velocity_score, funding_momentum_score, news_buzz_score,
                web_presence_score, tech_activity_score,
                growth_score, growth_trend, confidence,
                factors_positive, factors_negative
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            scores["company_id"],
            scores["score_date"],
            scores["components"].get("hiring_velocity", 0),
            scores["components"].get("funding_momentum", 0),
            scores["components"].get("news_buzz", 0),
            scores["components"].get("web_presence", 0),
            scores["components"].get("tech_activity", 0),
            scores["growth_score"],
            scores["growth_trend"],
            scores["confidence"],
            json.dumps(scores["factors_positive"]),
            json.dumps(scores["factors_negative"])
        ))
        
        conn.commit()
        conn.close()


# Pandas import for scoring (at module level to avoid issues)
import pandas as pd


# =============================================================================
# FUNDING PREDICTION ENGINE
# =============================================================================

class FundingPredictor:
    """
    Predicts funding windows for companies based on multiple signals.
    Helps BD teams prioritize outreach 3-6 months before companies raise.
    """
    
    # Typical runway by funding stage (in months)
    STAGE_RUNWAY = {
        "Pre-Seed": 15,
        "Seed": 21,
        "Series A": 30,
        "Series B": 42,
        "Series C+": 48,
        "Unknown": 24
    }
    
    # Typical raise amounts by stage (CAD millions)
    STAGE_AMOUNTS = {
        "Pre-Seed": 0.5,
        "Seed": 2.5,
        "Series A": 8,
        "Series B": 25,
        "Series C+": 50
    }
    
    # Senior roles that signal fundraising preparation
    SENIOR_FUNDRAISE_ROLES = [
        "cfo", "chief financial", "vp finance", "head of finance",
        "controller", "vp operations", "chief operating", "coo",
        "vp sales", "chief revenue", "cro", "head of sales",
        "vp business development", "head of bd", "chief business"
    ]
    
    # Expansion keywords in news
    EXPANSION_KEYWORDS = [
        "expansion", "expanding", "new market", "launch", "launching",
        "partnership", "partnering", "acquisition", "acquires",
        "opens office", "new location", "hiring spree", "growth",
        "international", "entering", "debuts"
    ]
    
    def __init__(self, db_path: str = "pipeline_data.db"):
        self.db_path = db_path
        self._init_prediction_tables()
    
    def _init_prediction_tables(self):
        """Initialize funding prediction tables."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        c.execute("""
            CREATE TABLE IF NOT EXISTS funding_predictions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company_id TEXT,
                prediction_date TEXT,
                
                -- Core prediction
                estimated_months_to_raise INTEGER,
                confidence TEXT,
                predicted_window TEXT,
                recommended_action TEXT,
                
                -- Component scores (0-100)
                runway_score REAL,
                hiring_score REAL,
                growth_score REAL,
                market_score REAL,
                benchmark_score REAL,
                
                -- Combined score
                urgency_score REAL,
                
                -- Signals
                primary_signals TEXT,
                all_signals TEXT,
                
                -- Metadata
                next_review_date TEXT,
                
                FOREIGN KEY (company_id) REFERENCES companies(company_id)
            )
        """)
        
        conn.commit()
        conn.close()
    
    def _get_company_data(self, company_id: str) -> Dict[str, Any]:
        """Get all relevant company data for prediction."""
        conn = sqlite3.connect(self.db_path)
        
        # Company basics
        company_df = pd.read_sql(
            "SELECT * FROM companies WHERE company_id = ?",
            conn, params=(company_id,)
        )
        
        # Latest traction snapshot
        snapshot_df = pd.read_sql("""
            SELECT * FROM traction_snapshots 
            WHERE company_id = ? 
            ORDER BY snapshot_date DESC LIMIT 1
        """, conn, params=(company_id,))
        
        # Latest growth score
        score_df = pd.read_sql("""
            SELECT * FROM growth_scores 
            WHERE company_id = ? 
            ORDER BY score_date DESC LIMIT 1
        """, conn, params=(company_id,))
        
        # Historical snapshots for trend analysis
        history_df = pd.read_sql("""
            SELECT * FROM traction_snapshots 
            WHERE company_id = ? 
            ORDER BY snapshot_date DESC LIMIT 5
        """, conn, params=(company_id,))
        
        conn.close()
        
        return {
            "company": company_df.iloc[0].to_dict() if len(company_df) > 0 else {},
            "snapshot": snapshot_df.iloc[0].to_dict() if len(snapshot_df) > 0 else {},
            "growth_score": score_df.iloc[0].to_dict() if len(score_df) > 0 else {},
            "history": history_df.to_dict('records') if len(history_df) > 0 else []
        }
    
    def _infer_funding_stage(self, company: Dict) -> str:
        """Infer current funding stage from available data."""
        total_raised = company.get("total_raised", 0) or 0
        stage = company.get("stage_entreprise", "") or ""
        
        # Try to parse from stage field
        stage_lower = str(stage).lower()
        if "seed" in stage_lower and "pre" in stage_lower:
            return "Pre-Seed"
        elif "seed" in stage_lower:
            return "Seed"
        elif "series a" in stage_lower or "série a" in stage_lower:
            return "Series A"
        elif "series b" in stage_lower or "série b" in stage_lower:
            return "Series B"
        elif "series" in stage_lower or "série" in stage_lower:
            return "Series C+"
        
        # Infer from total raised
        if total_raised < 1:
            return "Pre-Seed"
        elif total_raised < 5:
            return "Seed"
        elif total_raised < 15:
            return "Series A"
        elif total_raised < 40:
            return "Series B"
        else:
            return "Series C+"
    
    def _calculate_runway_score(self, company: Dict, snapshot: Dict) -> Tuple[float, List[Dict]]:
        """
        Calculate runway pressure score (0-100).
        Higher score = more likely to raise soon.
        """
        signals = []
        score = 0
        
        last_financing_date = company.get("last_financing_date")
        last_financing_size = company.get("last_financing_size", 0) or 0
        total_raised = company.get("total_raised", 0) or 0
        employees = company.get("employees", 0) or 0
        
        funding_stage = self._infer_funding_stage(company)
        typical_runway = self.STAGE_RUNWAY.get(funding_stage, 24)
        
        months_since_raise = None
        
        if last_financing_date:
            try:
                last_date = datetime.strptime(str(last_financing_date)[:10], "%Y-%m-%d")
                months_since_raise = (datetime.now() - last_date).days / 30
                
                # Calculate runway consumption percentage
                runway_consumed = months_since_raise / typical_runway
                
                if runway_consumed > 0.8:
                    score += 40
                    signals.append({
                        "type": "runway_critical",
                        "detail": f"~{months_since_raise:.0f} months since last raise ({runway_consumed*100:.0f}% of typical runway)",
                        "weight": "high"
                    })
                elif runway_consumed > 0.6:
                    score += 30
                    signals.append({
                        "type": "runway_moderate",
                        "detail": f"{months_since_raise:.0f} months since {funding_stage} round",
                        "weight": "high"
                    })
                elif runway_consumed > 0.4:
                    score += 15
                    signals.append({
                        "type": "runway_early",
                        "detail": f"{months_since_raise:.0f} months since raise, likely planning next round",
                        "weight": "medium"
                    })
            except:
                pass
        
        # Estimate burn rate proxy (employees * avg salary)
        if employees > 0:
            # Rough estimate: $80K/employee/year average in Quebec tech
            estimated_annual_burn = employees * 80000
            estimated_monthly_burn = estimated_annual_burn / 12
            
            if last_financing_size and last_financing_size > 0:
                # Estimate remaining runway
                if months_since_raise:
                    cash_burned = months_since_raise * estimated_monthly_burn / 1_000_000
                    estimated_remaining = max(0, last_financing_size - cash_burned)
                    months_remaining = estimated_remaining / (estimated_monthly_burn / 1_000_000)
                    
                    if months_remaining < 6:
                        score += 35
                        signals.append({
                            "type": "burn_rate",
                            "detail": f"Estimated ~{months_remaining:.0f} months runway remaining",
                            "weight": "high"
                        })
                    elif months_remaining < 12:
                        score += 20
                        signals.append({
                            "type": "burn_rate",
                            "detail": f"Estimated ~{months_remaining:.0f} months runway",
                            "weight": "medium"
                        })
        
        # Small last round relative to stage suggests bridge/extension
        typical_amount = self.STAGE_AMOUNTS.get(funding_stage, 5)
        if last_financing_size and last_financing_size < typical_amount * 0.5:
            score += 15
            signals.append({
                "type": "small_round",
                "detail": f"Last round (${last_financing_size:.1f}M) smaller than typical {funding_stage}",
                "weight": "medium"
            })
        
        return min(100, score), signals
    
    def _calculate_hiring_score(self, company: Dict, snapshot: Dict) -> Tuple[float, List[Dict]]:
        """
        Calculate hiring momentum score (0-100).
        Senior hires and hiring surges signal fundraising.
        """
        signals = []
        score = 0
        
        job_count = snapshot.get("job_postings_count", 0) or 0
        employees = company.get("employees", 0) or 1
        
        # Parse raw data for job titles
        raw_data = snapshot.get("raw_data", "{}")
        try:
            if isinstance(raw_data, bytes):
                raw_data = raw_data.decode('utf-8')
            raw = json.loads(raw_data) if raw_data else {}
        except:
            raw = {}
        
        job_titles = raw.get("jobs", {}).get("job_titles", [])
        
        # Check for senior fundraising-related hires
        senior_hires = []
        for title in job_titles:
            title_lower = str(title).lower()
            for role in self.SENIOR_FUNDRAISE_ROLES:
                if role in title_lower:
                    senior_hires.append(title)
                    break
        
        if senior_hires:
            score += 35
            signals.append({
                "type": "senior_hire",
                "detail": f"Hiring senior roles: {', '.join(senior_hires[:3])}",
                "weight": "high"
            })
        
        # Hiring velocity (jobs as % of employees)
        if employees > 0:
            hiring_ratio = job_count / employees
            
            if hiring_ratio > 0.3:
                score += 30
                signals.append({
                    "type": "hiring_surge",
                    "detail": f"{job_count} open roles ({hiring_ratio*100:.0f}% of workforce)",
                    "weight": "high"
                })
            elif hiring_ratio > 0.15:
                score += 20
                signals.append({
                    "type": "hiring_active",
                    "detail": f"{job_count} open positions",
                    "weight": "medium"
                })
            elif hiring_ratio > 0.05:
                score += 10
                signals.append({
                    "type": "hiring_normal",
                    "detail": f"{job_count} positions open",
                    "weight": "low"
                })
        
        # Has careers page = actively recruiting
        if snapshot.get("has_careers_page"):
            score += 10
        
        return min(100, score), signals
    
    def _calculate_growth_signals_score(self, company: Dict, snapshot: Dict, growth_score: Dict) -> Tuple[float, List[Dict]]:
        """
        Calculate growth signals score (0-100).
        News, expansion, partnerships indicate fundraising momentum.
        """
        signals = []
        score = 0
        
        # Parse raw data for news
        raw_data = snapshot.get("raw_data", "{}")
        try:
            if isinstance(raw_data, bytes):
                raw_data = raw_data.decode('utf-8')
            raw = json.loads(raw_data) if raw_data else {}
        except:
            raw = {}
        
        news_articles = raw.get("news", {}).get("articles", [])
        news_count = len(news_articles)
        
        # Check for expansion keywords in news
        expansion_signals = []
        for article in news_articles:
            title = str(article.get("title", "")).lower()
            for keyword in self.EXPANSION_KEYWORDS:
                if keyword in title:
                    expansion_signals.append(article.get("title", ""))
                    break
        
        if expansion_signals:
            score += 25
            signals.append({
                "type": "expansion_news",
                "detail": f"Expansion signals in news: {expansion_signals[0][:60]}...",
                "weight": "high"
            })
        
        # General news buzz
        if news_count >= 5:
            score += 20
            signals.append({
                "type": "media_buzz",
                "detail": f"{news_count} news mentions in past 30 days",
                "weight": "medium"
            })
        elif news_count >= 2:
            score += 10
            signals.append({
                "type": "media_presence",
                "detail": f"{news_count} recent news mentions",
                "weight": "low"
            })
        
        # Use existing growth score if available
        existing_growth = growth_score.get("growth_score", 0) or 0
        if existing_growth > 70:
            score += 20
            signals.append({
                "type": "high_traction",
                "detail": f"Strong traction score ({existing_growth:.0f}/100)",
                "weight": "medium"
            })
        elif existing_growth > 50:
            score += 10
        
        # Product maturity signals
        if snapshot.get("has_pricing") or "pricing" in str(snapshot.get("tech_stack", "")).lower():
            score += 10
            signals.append({
                "type": "product_maturity",
                "detail": "Has pricing page (revenue generating)",
                "weight": "low"
            })
        
        return min(100, score), signals
    
    def _calculate_market_score(self, company: Dict) -> Tuple[float, List[Dict]]:
        """
        Calculate market context score (0-100).
        Sector heat and timing factors.
        """
        signals = []
        score = 50  # Base score - neutral
        
        sector = company.get("iq_sector", "") or ""
        sector_lower = str(sector).lower()
        
        # Hot sectors in 2026 (adjust as needed)
        hot_sectors = ["ai", "artificial intelligence", "machine learning", "cleantech", 
                       "climate", "cybersecurity", "fintech", "healthtech", "biotech"]
        cooling_sectors = ["crypto", "web3", "metaverse"]
        
        for hot in hot_sectors:
            if hot in sector_lower:
                score += 20
                signals.append({
                    "type": "hot_sector",
                    "detail": f"{sector} is an active sector for investment",
                    "weight": "medium"
                })
                break
        
        for cold in cooling_sectors:
            if cold in sector_lower:
                score -= 20
                signals.append({
                    "type": "cooling_sector",
                    "detail": f"{sector} sector is seeing reduced activity",
                    "weight": "medium"
                })
                break
        
        # Seasonal timing (Q1 and Q4 are slower for closes)
        current_month = datetime.now().month
        if current_month in [1, 2, 11, 12]:
            score -= 10
            signals.append({
                "type": "seasonal",
                "detail": "Q4/Q1 typically slower for closings",
                "weight": "low"
            })
        elif current_month in [3, 4, 5, 9, 10]:
            score += 10
            signals.append({
                "type": "seasonal",
                "detail": "Good timing for fundraising activity",
                "weight": "low"
            })
        
        return min(100, max(0, score)), signals
    
    def _calculate_benchmark_score(self, company: Dict) -> Tuple[float, List[Dict]]:
        """
        Calculate benchmark score (0-100).
        Compare to typical funding pace for stage.
        """
        signals = []
        score = 50  # Base
        
        year_founded = company.get("year_founded")
        funding_stage = self._infer_funding_stage(company)
        total_raised = company.get("total_raised", 0) or 0
        
        if year_founded:
            try:
                founded_year = int(str(year_founded)[:4])
                company_age = datetime.now().year - founded_year
                
                # Expected stage by age (very rough)
                expected_stages = {
                    1: "Pre-Seed",
                    2: "Seed",
                    3: "Seed",
                    4: "Series A",
                    5: "Series A",
                    6: "Series B",
                }
                
                expected = expected_stages.get(company_age, "Series B")
                
                # Compare progress
                stage_order = ["Pre-Seed", "Seed", "Series A", "Series B", "Series C+"]
                current_idx = stage_order.index(funding_stage) if funding_stage in stage_order else 0
                expected_idx = stage_order.index(expected) if expected in stage_order else 0
                
                if current_idx < expected_idx:
                    score += 20
                    signals.append({
                        "type": "behind_pace",
                        "detail": f"{company_age} years old at {funding_stage} - may accelerate",
                        "weight": "medium"
                    })
                elif current_idx > expected_idx:
                    score -= 10
                    signals.append({
                        "type": "ahead_pace",
                        "detail": f"Funding ahead of typical pace",
                        "weight": "low"
                    })
            except:
                pass
        
        return min(100, max(0, score)), signals
    
    def predict_funding_window(self, company_id: str) -> Dict[str, Any]:
        """
        Main prediction function - calculates when a company will likely raise.
        
        Returns prediction with confidence and signals.
        """
        data = self._get_company_data(company_id)
        
        if not data["company"]:
            return {"error": "Company not found"}
        
        company = data["company"]
        snapshot = data["snapshot"]
        growth_score = data["growth_score"]
        
        # Calculate all component scores
        runway_score, runway_signals = self._calculate_runway_score(company, snapshot)
        hiring_score, hiring_signals = self._calculate_hiring_score(company, snapshot)
        growth_sig_score, growth_signals = self._calculate_growth_signals_score(company, snapshot, growth_score)
        market_score, market_signals = self._calculate_market_score(company)
        benchmark_score, benchmark_signals = self._calculate_benchmark_score(company)
        
        # Combine all signals
        all_signals = runway_signals + hiring_signals + growth_signals + market_signals + benchmark_signals
        
        # Sort by weight
        weight_order = {"high": 0, "medium": 1, "low": 2}
        all_signals.sort(key=lambda x: weight_order.get(x.get("weight", "low"), 2))
        
        # Weighted combined score (urgency score)
        urgency_score = (
            runway_score * 0.30 +
            hiring_score * 0.25 +
            growth_sig_score * 0.20 +
            market_score * 0.15 +
            benchmark_score * 0.10
        )
        
        # Convert score to estimated months
        if urgency_score >= 80:
            estimated_months = 2
            recommended_action = "priority_bd"
        elif urgency_score >= 65:
            estimated_months = 4
            recommended_action = "priority_bd"
        elif urgency_score >= 50:
            estimated_months = 7
            recommended_action = "warm_outreach"
        elif urgency_score >= 35:
            estimated_months = 12
            recommended_action = "monitor"
        elif urgency_score >= 20:
            estimated_months = 18
            recommended_action = "watch"
        else:
            estimated_months = 24
            recommended_action = "low_priority"
        
        # Calculate confidence
        data_completeness = sum([
            1 if company.get("last_financing_date") else 0,
            1 if company.get("total_raised") else 0,
            1 if snapshot.get("job_postings_count") else 0,
            1 if snapshot.get("news_mentions_30d") else 0,
            1 if company.get("employees") else 0,
        ]) / 5
        
        if data_completeness >= 0.8:
            confidence = "high"
        elif data_completeness >= 0.5:
            confidence = "medium"
        else:
            confidence = "low"
        
        # Calculate predicted window
        predicted_date = datetime.now() + timedelta(days=estimated_months * 30)
        predicted_window = f"Q{(predicted_date.month - 1) // 3 + 1} {predicted_date.year}"
        
        prediction = {
            "company_id": company_id,
            "company_name": company.get("name", ""),
            "prediction_date": datetime.now().isoformat(),
            "estimated_months_to_raise": estimated_months,
            "confidence": confidence,
            "predicted_window": predicted_window,
            "recommended_action": recommended_action,
            "scores": {
                "urgency": round(urgency_score, 1),
                "runway": round(runway_score, 1),
                "hiring": round(hiring_score, 1),
                "growth": round(growth_sig_score, 1),
                "market": round(market_score, 1),
                "benchmark": round(benchmark_score, 1)
            },
            "primary_signals": all_signals[:3],
            "all_signals": all_signals,
            "next_review_date": (datetime.now() + timedelta(days=30)).isoformat()
        }
        
        # Save prediction
        self._save_prediction(prediction)
        
        return prediction
    
    def _save_prediction(self, prediction: Dict[str, Any]):
        """Save prediction to database."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        c.execute("""
            INSERT INTO funding_predictions (
                company_id, prediction_date, estimated_months_to_raise,
                confidence, predicted_window, recommended_action,
                runway_score, hiring_score, growth_score, market_score, benchmark_score,
                urgency_score, primary_signals, all_signals, next_review_date
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            prediction["company_id"],
            prediction["prediction_date"],
            prediction["estimated_months_to_raise"],
            prediction["confidence"],
            prediction["predicted_window"],
            prediction["recommended_action"],
            prediction["scores"]["runway"],
            prediction["scores"]["hiring"],
            prediction["scores"]["growth"],
            prediction["scores"]["market"],
            prediction["scores"]["benchmark"],
            prediction["scores"]["urgency"],
            json.dumps(prediction["primary_signals"]),
            json.dumps(prediction["all_signals"]),
            prediction["next_review_date"]
        ))
        
        conn.commit()
        conn.close()
    
    def batch_predict(self, company_ids: List[str]) -> List[Dict[str, Any]]:
        """Run predictions for multiple companies."""
        results = []
        for cid in company_ids:
            try:
                result = self.predict_funding_window(cid)
                results.append(result)
            except Exception as e:
                logger.error(f"Prediction failed for {cid}: {e}")
                results.append({"company_id": cid, "error": str(e)})
        return results
    
    def get_priority_queue(self, limit: int = 50) -> pd.DataFrame:
        """Get companies ranked by urgency for BD outreach."""
        conn = sqlite3.connect(self.db_path)
        
        df = pd.read_sql("""
            SELECT 
                fp.company_id,
                c.name,
                c.iq_sector,
                c.pipeline_stage,
                c.total_raised,
                c.employees,
                fp.estimated_months_to_raise,
                fp.confidence,
                fp.predicted_window,
                fp.recommended_action,
                fp.urgency_score,
                fp.runway_score,
                fp.hiring_score,
                fp.primary_signals,
                fp.prediction_date
            FROM funding_predictions fp
            JOIN companies c ON fp.company_id = c.company_id
            WHERE fp.id IN (
                SELECT MAX(id) FROM funding_predictions GROUP BY company_id
            )
            ORDER BY fp.urgency_score DESC
            LIMIT ?
        """, conn, params=(limit,))
        
        conn.close()
        return df


if __name__ == "__main__":
    # Test run
    scraper = TractionScraper()
    
    # Example: test with a known company
    result = scraper.collect_traction_snapshot(
        company_id="test-001",
        company_name="Element AI",
        website="https://www.servicenow.com",  # They were acquired
        github_url=None
    )
    
    print(json.dumps(result, indent=2, default=str))
    
    # Calculate score
    scorer = GrowthScorer()
    score = scorer.calculate_growth_score("test-001")
    print(json.dumps(score, indent=2))
