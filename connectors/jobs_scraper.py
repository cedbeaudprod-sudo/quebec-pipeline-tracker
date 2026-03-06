"""
Jobs Scraper Connector
Scrapes job postings to detect hiring signals for Funding Radar.

Sources:
- Indeed RSS (primary - no auth required)
- Company careers pages
- Google Jobs search

Outputs:
- Job posting counts
- Senior hire detection (CFO, VP, C-level)
- Hiring velocity trends
- Role type breakdown
"""

import requests
from bs4 import BeautifulSoup
import feedparser
import re
import time
import sqlite3
from datetime import datetime, timedelta
from urllib.parse import quote_plus, urlparse
import json
from typing import Optional, Dict, List, Any, Tuple
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Rate limiting
REQUEST_DELAY = 1.5
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"


class JobsScraper:
    """
    Scrapes job postings from multiple sources to detect hiring signals.
    """
    
    # Senior roles that indicate fundraising/scaling
    SENIOR_ROLES = {
        "executive": [
            "ceo", "chief executive", "president",
            "cfo", "chief financial", "vp finance", "vice president finance",
            "coo", "chief operating", "vp operations", "vice president operations",
            "cto", "chief technology", "vp engineering", "vice president engineering",
            "cmo", "chief marketing", "vp marketing", "vice president marketing",
            "cro", "chief revenue", "vp sales", "vice president sales",
            "cpo", "chief product", "vp product", "vice president product",
            "chro", "chief human", "vp people", "vice president people", "vp hr",
        ],
        "director": [
            "director of finance", "director of sales", "director of marketing",
            "director of engineering", "director of product", "director of operations",
            "director of hr", "director of people", "director of business development",
        ],
        "fundraising_signal": [
            "controller", "fp&a", "financial planning", "investor relations",
            "corporate development", "m&a", "business development",
            "head of finance", "head of sales", "head of growth",
        ]
    }
    
    # Technical roles (indicate product development)
    TECH_ROLES = [
        "software engineer", "developer", "full stack", "frontend", "backend",
        "devops", "sre", "data engineer", "data scientist", "ml engineer",
        "machine learning", "ai engineer", "cloud engineer", "architect",
        "qa engineer", "test engineer", "security engineer", "infrastructure",
    ]
    
    # Growth roles (indicate scaling)
    GROWTH_ROLES = [
        "account executive", "sales rep", "business development", "bdm", "bdr", "sdr",
        "customer success", "account manager", "sales manager", "growth",
        "demand gen", "performance marketing", "paid media", "partnerships",
    ]
    
    def __init__(self, db_path: str = "pipeline_data.db"):
        self.db_path = db_path
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT})
        self._init_jobs_tables()
    
    def _init_jobs_tables(self):
        """Initialize job tracking tables."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        c.execute("""
            CREATE TABLE IF NOT EXISTS job_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company_id TEXT,
                snapshot_date TEXT,
                
                -- Counts
                total_jobs INTEGER DEFAULT 0,
                senior_jobs INTEGER DEFAULT 0,
                tech_jobs INTEGER DEFAULT 0,
                growth_jobs INTEGER DEFAULT 0,
                other_jobs INTEGER DEFAULT 0,
                
                -- Sources
                indeed_count INTEGER DEFAULT 0,
                careers_page_count INTEGER DEFAULT 0,
                linkedin_count INTEGER DEFAULT 0,
                
                -- Details
                job_titles TEXT,
                senior_roles_found TEXT,
                sources_checked TEXT,
                
                -- Raw data
                raw_data TEXT,
                
                FOREIGN KEY (company_id) REFERENCES companies(company_id)
            )
        """)
        
        c.execute("""
            CREATE TABLE IF NOT EXISTS job_postings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company_id TEXT,
                title TEXT,
                location TEXT,
                source TEXT,
                url TEXT,
                posted_date TEXT,
                scraped_date TEXT,
                role_type TEXT,
                is_senior INTEGER DEFAULT 0,
                raw_data TEXT,
                
                FOREIGN KEY (company_id) REFERENCES companies(company_id)
            )
        """)
        
        conn.commit()
        conn.close()
    
    def _safe_request(self, url: str, timeout: int = 10) -> Optional[requests.Response]:
        """Make a rate-limited request."""
        try:
            time.sleep(REQUEST_DELAY)
            response = self.session.get(url, timeout=timeout)
            response.raise_for_status()
            return response
        except Exception as e:
            logger.warning(f"Request failed for {url}: {e}")
            return None
    
    def _classify_role(self, title: str) -> Dict[str, Any]:
        """
        Classify a job title into categories.
        Returns role type and whether it's a senior position.
        """
        title_lower = title.lower()
        
        # Check for senior roles
        is_senior = False
        senior_type = None
        
        for category, keywords in self.SENIOR_ROLES.items():
            for keyword in keywords:
                if keyword in title_lower:
                    is_senior = True
                    senior_type = category
                    break
            if is_senior:
                break
        
        # Determine role type
        role_type = "other"
        
        # Check tech roles
        for keyword in self.TECH_ROLES:
            if keyword in title_lower:
                role_type = "tech"
                break
        
        # Check growth roles
        if role_type == "other":
            for keyword in self.GROWTH_ROLES:
                if keyword in title_lower:
                    role_type = "growth"
                    break
        
        # If senior, override role type
        if is_senior:
            role_type = "senior"
        
        return {
            "role_type": role_type,
            "is_senior": is_senior,
            "senior_type": senior_type
        }
    
    # =========================================================================
    # INDEED SCRAPER
    # =========================================================================
    
    def scrape_indeed(self, company_name: str, location: str = "Quebec") -> Dict[str, Any]:
        """
        Scrape Indeed RSS for job postings.
        Indeed provides RSS feeds for job searches.
        """
        results = {
            "source": "indeed",
            "jobs": [],
            "count": 0,
            "error": None
        }
        
        try:
            # Build Indeed RSS URL
            query = quote_plus(f'"{company_name}"')
            location_encoded = quote_plus(location)
            
            # Indeed Canada RSS
            rss_url = f"https://ca.indeed.com/rss?q={query}&l={location_encoded}&sort=date"
            
            feed = feedparser.parse(rss_url)
            
            for entry in feed.entries[:25]:  # Limit to 25 jobs
                title = entry.get("title", "")
                
                # Filter: must contain company name in title or summary
                entry_text = f"{title} {entry.get('summary', '')}".lower()
                if company_name.lower() not in entry_text:
                    continue
                
                # Classify the role
                classification = self._classify_role(title)
                
                job = {
                    "title": title,
                    "location": entry.get("location", location),
                    "url": entry.get("link", ""),
                    "posted_date": entry.get("published", ""),
                    "source": "indeed",
                    "role_type": classification["role_type"],
                    "is_senior": classification["is_senior"],
                    "senior_type": classification.get("senior_type")
                }
                
                results["jobs"].append(job)
            
            results["count"] = len(results["jobs"])
            
        except Exception as e:
            logger.error(f"Indeed scraping failed for {company_name}: {e}")
            results["error"] = str(e)
        
        return results
    
    # =========================================================================
    # CAREERS PAGE SCRAPER
    # =========================================================================
    
    def scrape_careers_page(self, careers_url: str, company_name: str) -> Dict[str, Any]:
        """
        Scrape a company's careers page for job listings.
        Handles common patterns: Greenhouse, Lever, Workable, custom pages.
        """
        results = {
            "source": "careers_page",
            "jobs": [],
            "count": 0,
            "platform": None,
            "error": None
        }
        
        if not careers_url:
            return results
        
        # Ensure URL has scheme
        if not careers_url.startswith("http"):
            careers_url = f"https://{careers_url}"
        
        response = self._safe_request(careers_url)
        if not response:
            results["error"] = "Failed to fetch careers page"
            return results
        
        try:
            soup = BeautifulSoup(response.text, "html.parser")
            url_lower = careers_url.lower()
            
            # Detect platform
            if "greenhouse.io" in url_lower or "boards.greenhouse" in url_lower:
                results["platform"] = "greenhouse"
                results = self._parse_greenhouse(soup, results, company_name)
            elif "lever.co" in url_lower or "jobs.lever" in url_lower:
                results["platform"] = "lever"
                results = self._parse_lever(soup, results, company_name)
            elif "workable.com" in url_lower:
                results["platform"] = "workable"
                results = self._parse_workable(soup, results, company_name)
            else:
                results["platform"] = "custom"
                results = self._parse_generic_careers(soup, results, company_name)
            
            results["count"] = len(results["jobs"])
            
        except Exception as e:
            logger.error(f"Careers page scraping failed for {careers_url}: {e}")
            results["error"] = str(e)
        
        return results
    
    def _parse_greenhouse(self, soup: BeautifulSoup, results: Dict, company_name: str) -> Dict:
        """Parse Greenhouse job board."""
        job_elements = soup.find_all("div", class_=re.compile(r"opening"))
        job_elements += soup.find_all("a", class_=re.compile(r"job"))
        
        for elem in job_elements:
            title_elem = elem.find(["h2", "h3", "h4", "a", "span"], class_=re.compile(r"title|name"))
            if not title_elem:
                title_elem = elem.find("a")
            
            if title_elem:
                title = title_elem.get_text(strip=True)
                classification = self._classify_role(title)
                
                location_elem = elem.find(class_=re.compile(r"location"))
                location = location_elem.get_text(strip=True) if location_elem else ""
                
                results["jobs"].append({
                    "title": title,
                    "location": location,
                    "source": "greenhouse",
                    "role_type": classification["role_type"],
                    "is_senior": classification["is_senior"]
                })
        
        return results
    
    def _parse_lever(self, soup: BeautifulSoup, results: Dict, company_name: str) -> Dict:
        """Parse Lever job board."""
        postings = soup.find_all("div", class_=re.compile(r"posting"))
        
        for posting in postings:
            title_elem = posting.find(["h5", "a"], class_=re.compile(r"posting-title"))
            if not title_elem:
                title_elem = posting.find("a")
            
            if title_elem:
                title = title_elem.get_text(strip=True)
                classification = self._classify_role(title)
                
                location_elem = posting.find(class_=re.compile(r"location|workplaceTypes"))
                location = location_elem.get_text(strip=True) if location_elem else ""
                
                results["jobs"].append({
                    "title": title,
                    "location": location,
                    "source": "lever",
                    "role_type": classification["role_type"],
                    "is_senior": classification["is_senior"]
                })
        
        return results
    
    def _parse_workable(self, soup: BeautifulSoup, results: Dict, company_name: str) -> Dict:
        """Parse Workable job board."""
        jobs = soup.find_all("li", {"data-ui": "job"})
        jobs += soup.find_all("div", class_=re.compile(r"job-listing"))
        
        for job in jobs:
            title_elem = job.find(["h3", "a", "span"], class_=re.compile(r"title|name"))
            if not title_elem:
                title_elem = job.find("a")
            
            if title_elem:
                title = title_elem.get_text(strip=True)
                classification = self._classify_role(title)
                
                location_elem = job.find(class_=re.compile(r"location"))
                location = location_elem.get_text(strip=True) if location_elem else ""
                
                results["jobs"].append({
                    "title": title,
                    "location": location,
                    "source": "workable",
                    "role_type": classification["role_type"],
                    "is_senior": classification["is_senior"]
                })
        
        return results
    
    def _parse_generic_careers(self, soup: BeautifulSoup, results: Dict, company_name: str) -> Dict:
        """Parse generic careers page looking for common patterns."""
        
        # Common job listing patterns
        job_containers = []
        
        # Look for job-related elements
        for pattern in [r"job", r"position", r"opening", r"career", r"vacancy", r"role"]:
            job_containers += soup.find_all(["div", "li", "article"], class_=re.compile(pattern, re.I))
        
        # Also look for lists that might contain jobs
        job_lists = soup.find_all("ul", class_=re.compile(r"job|position|career|opening", re.I))
        for ul in job_lists:
            job_containers += ul.find_all("li")
        
        seen_titles = set()
        
        for container in job_containers[:30]:  # Limit
            # Try to find title
            title_elem = container.find(["h2", "h3", "h4", "h5", "a", "span"], 
                                         class_=re.compile(r"title|name|heading", re.I))
            if not title_elem:
                # Fallback: first link or heading
                title_elem = container.find(["a", "h2", "h3", "h4", "h5"])
            
            if title_elem:
                title = title_elem.get_text(strip=True)
                
                # Skip if too short, too long, or already seen
                if len(title) < 3 or len(title) > 100 or title in seen_titles:
                    continue
                
                # Skip navigation items
                skip_words = ["apply", "search", "filter", "all jobs", "view all", "about", "contact"]
                if any(skip in title.lower() for skip in skip_words):
                    continue
                
                seen_titles.add(title)
                classification = self._classify_role(title)
                
                # Try to find location
                location_elem = container.find(class_=re.compile(r"location|city|region", re.I))
                location = location_elem.get_text(strip=True) if location_elem else ""
                
                results["jobs"].append({
                    "title": title,
                    "location": location,
                    "source": "careers_page",
                    "role_type": classification["role_type"],
                    "is_senior": classification["is_senior"]
                })
        
        return results
    
    # =========================================================================
    # MAIN COLLECTION
    # =========================================================================
    
    def collect_job_snapshot(self, company_id: str, company_name: str, 
                             website: str = None, careers_url: str = None) -> Dict[str, Any]:
        """
        Collect job postings from all sources for a company.
        """
        logger.info(f"Collecting jobs for: {company_name}")
        
        snapshot = {
            "company_id": company_id,
            "company_name": company_name,
            "snapshot_date": datetime.now().isoformat(),
            "sources": {},
            "all_jobs": [],
            "summary": {
                "total": 0,
                "senior": 0,
                "tech": 0,
                "growth": 0,
                "other": 0
            },
            "senior_roles_found": []
        }
        
        # 1. Indeed
        indeed_results = self.scrape_indeed(company_name, "Quebec")
        snapshot["sources"]["indeed"] = indeed_results
        snapshot["all_jobs"].extend(indeed_results.get("jobs", []))
        
        # Also try Canada-wide
        indeed_canada = self.scrape_indeed(company_name, "Canada")
        for job in indeed_canada.get("jobs", []):
            if job not in snapshot["all_jobs"]:
                snapshot["all_jobs"].append(job)
        
        # 2. Careers page
        if careers_url:
            careers_results = self.scrape_careers_page(careers_url, company_name)
            snapshot["sources"]["careers_page"] = careers_results
            snapshot["all_jobs"].extend(careers_results.get("jobs", []))
        elif website:
            # Try to find careers page from main website
            careers_url = self._find_careers_page(website)
            if careers_url:
                careers_results = self.scrape_careers_page(careers_url, company_name)
                snapshot["sources"]["careers_page"] = careers_results
                snapshot["all_jobs"].extend(careers_results.get("jobs", []))
        
        # Deduplicate jobs
        seen = set()
        unique_jobs = []
        for job in snapshot["all_jobs"]:
            key = job.get("title", "").lower()[:50]
            if key and key not in seen:
                seen.add(key)
                unique_jobs.append(job)
        snapshot["all_jobs"] = unique_jobs
        
        # Calculate summary
        for job in snapshot["all_jobs"]:
            snapshot["summary"]["total"] += 1
            role_type = job.get("role_type", "other")
            
            if job.get("is_senior"):
                snapshot["summary"]["senior"] += 1
                snapshot["senior_roles_found"].append(job.get("title"))
            elif role_type == "tech":
                snapshot["summary"]["tech"] += 1
            elif role_type == "growth":
                snapshot["summary"]["growth"] += 1
            else:
                snapshot["summary"]["other"] += 1
        
        # Save snapshot
        self._save_snapshot(snapshot)
        
        return snapshot
    
    def _find_careers_page(self, website: str) -> Optional[str]:
        """Try to find careers page from main website."""
        if not website:
            return None
        
        if not website.startswith("http"):
            website = f"https://{website}"
        
        response = self._safe_request(website)
        if not response:
            return None
        
        try:
            soup = BeautifulSoup(response.text, "html.parser")
            
            # Look for careers links
            for link in soup.find_all("a", href=True):
                href = link.get("href", "").lower()
                text = link.get_text(strip=True).lower()
                
                if any(kw in href or kw in text for kw in ["careers", "jobs", "join", "hiring", "team"]):
                    full_url = href
                    if not full_url.startswith("http"):
                        base = urlparse(website)
                        full_url = f"{base.scheme}://{base.netloc}/{href.lstrip('/')}"
                    return full_url
        except:
            pass
        
        return None
    
    def _save_snapshot(self, snapshot: Dict[str, Any]):
        """Save job snapshot to database."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        summary = snapshot.get("summary", {})
        
        c.execute("""
            INSERT INTO job_snapshots (
                company_id, snapshot_date,
                total_jobs, senior_jobs, tech_jobs, growth_jobs, other_jobs,
                indeed_count, careers_page_count,
                job_titles, senior_roles_found, sources_checked, raw_data
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            snapshot["company_id"],
            snapshot["snapshot_date"],
            summary.get("total", 0),
            summary.get("senior", 0),
            summary.get("tech", 0),
            summary.get("growth", 0),
            summary.get("other", 0),
            snapshot["sources"].get("indeed", {}).get("count", 0),
            snapshot["sources"].get("careers_page", {}).get("count", 0),
            json.dumps([j.get("title") for j in snapshot["all_jobs"]]),
            json.dumps(snapshot.get("senior_roles_found", [])),
            json.dumps(list(snapshot["sources"].keys())),
            json.dumps(snapshot)
        ))
        
        # Also save individual job postings
        for job in snapshot["all_jobs"]:
            c.execute("""
                INSERT INTO job_postings (
                    company_id, title, location, source, url,
                    posted_date, scraped_date, role_type, is_senior, raw_data
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                snapshot["company_id"],
                job.get("title"),
                job.get("location"),
                job.get("source"),
                job.get("url"),
                job.get("posted_date"),
                snapshot["snapshot_date"],
                job.get("role_type"),
                1 if job.get("is_senior") else 0,
                json.dumps(job)
            ))
        
        conn.commit()
        conn.close()


class JobsAnalyzer:
    """
    Analyzes job data to generate hiring signals for Funding Radar.
    """
    
    def __init__(self, db_path: str = "pipeline_data.db"):
        self.db_path = db_path
    
    def get_hiring_score(self, company_id: str, employee_count: int = None) -> Dict[str, Any]:
        """
        Calculate hiring score from job data.
        Returns score components for Funding Radar integration.
        """
        conn = sqlite3.connect(self.db_path)
        
        # Get latest job snapshot
        snapshot_df = None
        try:
            import pandas as pd
            snapshot_df = pd.read_sql("""
                SELECT * FROM job_snapshots 
                WHERE company_id = ? 
                ORDER BY snapshot_date DESC LIMIT 1
            """, conn, params=(company_id,))
        except:
            pass
        
        conn.close()
        
        result = {
            "company_id": company_id,
            "score": 0,
            "signals": [],
            "data": {
                "total_jobs": 0,
                "senior_jobs": 0,
                "tech_jobs": 0,
                "growth_jobs": 0,
                "hiring_ratio": 0
            }
        }
        
        if snapshot_df is None or len(snapshot_df) == 0:
            return result
        
        snapshot = snapshot_df.iloc[0]
        
        total_jobs = snapshot.get("total_jobs", 0) or 0
        senior_jobs = snapshot.get("senior_jobs", 0) or 0
        tech_jobs = snapshot.get("tech_jobs", 0) or 0
        growth_jobs = snapshot.get("growth_jobs", 0) or 0
        
        result["data"]["total_jobs"] = total_jobs
        result["data"]["senior_jobs"] = senior_jobs
        result["data"]["tech_jobs"] = tech_jobs
        result["data"]["growth_jobs"] = growth_jobs
        
        score = 0
        
        # Senior hire detection (strong fundraising signal)
        if senior_jobs >= 3:
            score += 40
            result["signals"].append({
                "type": "senior_hiring_spree",
                "detail": f"Hiring {senior_jobs} senior/executive roles",
                "weight": "high"
            })
        elif senior_jobs >= 1:
            score += 25
            
            # Try to get specific roles
            try:
                roles = json.loads(snapshot.get("senior_roles_found", "[]"))
                if roles:
                    result["signals"].append({
                        "type": "senior_hire",
                        "detail": f"Hiring: {', '.join(roles[:3])}",
                        "weight": "high"
                    })
            except:
                result["signals"].append({
                    "type": "senior_hire",
                    "detail": f"Hiring {senior_jobs} senior role(s)",
                    "weight": "high"
                })
        
        # Hiring velocity (if we know employee count)
        if employee_count and employee_count > 0:
            hiring_ratio = total_jobs / employee_count
            result["data"]["hiring_ratio"] = round(hiring_ratio, 3)
            
            if hiring_ratio > 0.3:
                score += 30
                result["signals"].append({
                    "type": "hiring_surge",
                    "detail": f"{total_jobs} jobs = {hiring_ratio*100:.0f}% of workforce",
                    "weight": "high"
                })
            elif hiring_ratio > 0.15:
                score += 20
                result["signals"].append({
                    "type": "hiring_active",
                    "detail": f"Active hiring ({total_jobs} positions)",
                    "weight": "medium"
                })
            elif hiring_ratio > 0.05:
                score += 10
                result["signals"].append({
                    "type": "hiring_normal",
                    "detail": f"{total_jobs} open positions",
                    "weight": "low"
                })
        else:
            # Without employee count, use absolute numbers
            if total_jobs >= 15:
                score += 25
                result["signals"].append({
                    "type": "hiring_surge",
                    "detail": f"{total_jobs} open positions",
                    "weight": "high"
                })
            elif total_jobs >= 8:
                score += 15
                result["signals"].append({
                    "type": "hiring_active",
                    "detail": f"{total_jobs} open positions",
                    "weight": "medium"
                })
            elif total_jobs >= 3:
                score += 10
                result["signals"].append({
                    "type": "hiring_normal",
                    "detail": f"{total_jobs} open positions",
                    "weight": "low"
                })
        
        # Tech team growth (product development signal)
        if tech_jobs >= 5:
            score += 15
            result["signals"].append({
                "type": "tech_expansion",
                "detail": f"Building tech team ({tech_jobs} engineering roles)",
                "weight": "medium"
            })
        
        # Sales/growth hiring (scaling signal)
        if growth_jobs >= 5:
            score += 15
            result["signals"].append({
                "type": "growth_scaling",
                "detail": f"Scaling go-to-market ({growth_jobs} sales/growth roles)",
                "weight": "medium"
            })
        
        result["score"] = min(100, score)
        
        return result
    
    def get_hiring_trend(self, company_id: str, days: int = 90) -> Dict[str, Any]:
        """
        Analyze hiring trend over time.
        Returns velocity and direction.
        """
        conn = sqlite3.connect(self.db_path)
        
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        
        try:
            import pandas as pd
            df = pd.read_sql("""
                SELECT snapshot_date, total_jobs, senior_jobs
                FROM job_snapshots 
                WHERE company_id = ? AND snapshot_date >= ?
                ORDER BY snapshot_date ASC
            """, conn, params=(company_id, cutoff))
        except:
            df = None
        
        conn.close()
        
        result = {
            "trend": "unknown",
            "velocity": 0,
            "data_points": 0
        }
        
        if df is None or len(df) < 2:
            return result
        
        result["data_points"] = len(df)
        
        # Calculate trend
        first_count = df.iloc[0]["total_jobs"]
        last_count = df.iloc[-1]["total_jobs"]
        
        if last_count > first_count * 1.5:
            result["trend"] = "accelerating"
            result["velocity"] = last_count - first_count
        elif last_count > first_count:
            result["trend"] = "increasing"
            result["velocity"] = last_count - first_count
        elif last_count < first_count * 0.5:
            result["trend"] = "declining"
            result["velocity"] = last_count - first_count
        else:
            result["trend"] = "stable"
            result["velocity"] = 0
        
        return result


if __name__ == "__main__":
    # Test run
    scraper = JobsScraper()
    
    # Test with a known company
    result = scraper.collect_job_snapshot(
        company_id="test-001",
        company_name="Hopper",
        website="https://www.hopper.com"
    )
    
    print(json.dumps(result, indent=2, default=str))
    
    # Test analyzer
    analyzer = JobsAnalyzer()
    score = analyzer.get_hiring_score("test-001", employee_count=500)
    print(json.dumps(score, indent=2))
