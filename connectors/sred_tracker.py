"""
SR&ED / CDAE Signal Tracker
Detects R&D tax credit activity as a traction/investment signal.

Since there's no public database of SR&ED claims, we infer R&D activity from:
- Job postings mentioning SR&ED, CDAE, R&D tax credits
- Company descriptions mentioning R&D activities
- Tech stack and engineering team indicators
- Known SR&ED consulting firm relationships
- Sector-based R&D intensity benchmarks

SR&ED = Scientific Research and Experimental Development (Federal)
CDAE = Crédit d'impôt pour le développement des affaires électroniques (Quebec)

High R&D activity signals:
- Active product development
- Technical innovation
- Cash runway extension via tax credits
- Government validation of R&D work
"""

import re
import sqlite3
from datetime import datetime, timedelta
import json
from typing import Optional, Dict, List, Any, Tuple
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# SR&ED/CDAE keywords for detection
SRED_KEYWORDS = [
    "sr&ed", "sred", "sr ed", "scientific research", "experimental development",
    "r&d tax", "r&d credit", "research tax credit", "tax incentive",
    "cdae", "crédit d'impôt", "credit d'impot", "affaires électroniques",
    "irap", "nrc-irap", "industrial research assistance",
]

# Job title keywords that indicate SR&ED-eligible work
SRED_JOB_KEYWORDS = [
    "r&d", "research", "scientist", "researcher", "phd", "innovation",
    "experimental", "prototype", "proof of concept", "poc",
    "machine learning engineer", "ai researcher", "data scientist",
    "algorithm", "computational", "bioinformatics", "biotech",
]

# Known SR&ED consulting firms in Quebec
SRED_CONSULTANTS = [
    "rnd partners", "r&d partners",
    "boast.ai", "boast ai", "boast capital",
    "ayming", 
    "sr&ed education", "sred education",
    "g6 consulting", "g6s consulting",
    "rdbase", "rd base",
    "northbridge", "north bridge",
    "scitax", "sci tax",
    "catax",
    "leyton",
]

# Sector R&D intensity benchmarks (R&D spend as % of revenue, typical)
SECTOR_RD_INTENSITY = {
    "software": 0.20,
    "saas": 0.22,
    "ai": 0.30,
    "machine learning": 0.30,
    "artificial intelligence": 0.30,
    "biotech": 0.35,
    "biotechnology": 0.35,
    "pharmaceuticals": 0.25,
    "medtech": 0.20,
    "medical devices": 0.20,
    "cleantech": 0.18,
    "greentech": 0.18,
    "fintech": 0.15,
    "hardware": 0.15,
    "electronics": 0.12,
    "manufacturing": 0.05,
    "e-commerce": 0.08,
    "consumer": 0.05,
    "services": 0.03,
}

# Average salary benchmarks for R&D staff (CAD)
RD_SALARY_BENCHMARKS = {
    "software_engineer": 95000,
    "senior_engineer": 130000,
    "data_scientist": 110000,
    "ml_engineer": 125000,
    "researcher": 90000,
    "phd_researcher": 100000,
}


class SREDTracker:
    """
    Tracks SR&ED/CDAE signals and estimates R&D activity.
    """
    
    def __init__(self, db_path: str = "pipeline_data.db"):
        self.db_path = db_path
        self._init_sred_tables()
    
    def _init_sred_tables(self):
        """Initialize SR&ED tracking tables."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        c.execute("""
            CREATE TABLE IF NOT EXISTS sred_signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company_id TEXT,
                scan_date TEXT,
                
                -- Detection flags
                sred_mentioned INTEGER DEFAULT 0,
                cdae_mentioned INTEGER DEFAULT 0,
                rd_jobs_count INTEGER DEFAULT 0,
                consultant_detected TEXT,
                
                -- Estimates
                estimated_rd_spend REAL,
                estimated_rd_headcount INTEGER,
                rd_intensity_score REAL,
                
                -- Sector data
                sector TEXT,
                sector_rd_benchmark REAL,
                
                -- Signals
                signals TEXT,
                confidence TEXT,
                
                -- Raw
                raw_data TEXT,
                
                FOREIGN KEY (company_id) REFERENCES companies(company_id)
            )
        """)
        
        conn.commit()
        conn.close()
    
    def scan_company(self, company_id: str, company_name: str,
                     description: str = None, sector: str = None,
                     employees: int = None, website_text: str = None,
                     job_titles: List[str] = None) -> Dict[str, Any]:
        """
        Scan a company for SR&ED/CDAE signals.
        
        Args:
            company_id: Pipeline tracker company ID
            company_name: Company name
            description: Company description text
            sector: Industry sector
            employees: Employee count
            website_text: Text scraped from company website
            job_titles: List of current job posting titles
        
        Returns:
            SR&ED signal analysis
        """
        result = {
            "company_id": company_id,
            "company_name": company_name,
            "scan_date": datetime.now().isoformat(),
            "signals": [],
            "estimates": {
                "rd_spend_annual": None,
                "rd_headcount": None,
                "sred_credit_potential": None,
                "cdae_credit_potential": None,
            },
            "rd_intensity_score": 0,
            "confidence": "low",
            "summary": {
                "sred_mentioned": False,
                "cdae_mentioned": False,
                "rd_jobs_found": 0,
                "consultant_detected": None,
            }
        }
        
        all_text = " ".join(filter(None, [
            company_name,
            description or "",
            website_text or "",
            " ".join(job_titles or [])
        ])).lower()
        
        # 1. Direct SR&ED/CDAE mention detection
        sred_mentioned = self._detect_sred_mentions(all_text)
        if sred_mentioned:
            result["signals"].append({
                "type": "sred_mention",
                "detail": "Company mentions SR&ED or R&D tax credits",
                "weight": "high"
            })
            result["summary"]["sred_mentioned"] = True
            result["rd_intensity_score"] += 30
        
        cdae_mentioned = self._detect_cdae_mentions(all_text)
        if cdae_mentioned:
            result["signals"].append({
                "type": "cdae_mention",
                "detail": "Company mentions CDAE (Quebec e-business credit)",
                "weight": "high"
            })
            result["summary"]["cdae_mentioned"] = True
            result["rd_intensity_score"] += 25
        
        # 2. R&D job postings
        rd_jobs = self._count_rd_jobs(job_titles or [])
        if rd_jobs > 0:
            result["signals"].append({
                "type": "rd_hiring",
                "detail": f"{rd_jobs} R&D-related job postings found",
                "weight": "medium" if rd_jobs < 3 else "high"
            })
            result["summary"]["rd_jobs_found"] = rd_jobs
            result["rd_intensity_score"] += min(25, rd_jobs * 5)
        
        # 3. SR&ED consultant detection
        consultant = self._detect_consultant(all_text)
        if consultant:
            result["signals"].append({
                "type": "sred_consultant",
                "detail": f"SR&ED consultant relationship detected: {consultant}",
                "weight": "high"
            })
            result["summary"]["consultant_detected"] = consultant
            result["rd_intensity_score"] += 20
        
        # 4. Sector-based R&D intensity
        sector_intensity = self._get_sector_rd_intensity(sector)
        if sector_intensity > 0.15:
            result["signals"].append({
                "type": "high_rd_sector",
                "detail": f"Sector ({sector}) typically has {sector_intensity*100:.0f}% R&D intensity",
                "weight": "medium"
            })
            result["rd_intensity_score"] += int(sector_intensity * 50)
        
        # 5. Estimate R&D spend and headcount
        if employees:
            estimates = self._estimate_rd_metrics(
                employees=employees,
                sector=sector,
                rd_jobs=rd_jobs,
                sred_mentioned=sred_mentioned
            )
            result["estimates"] = estimates
            
            if estimates.get("rd_spend_annual"):
                result["signals"].append({
                    "type": "rd_spend_estimate",
                    "detail": f"Estimated annual R&D spend: ${estimates['rd_spend_annual']:,.0f}",
                    "weight": "medium"
                })
            
            if estimates.get("sred_credit_potential"):
                result["signals"].append({
                    "type": "sred_credit_estimate",
                    "detail": f"Potential SR&ED credit: ${estimates['sred_credit_potential']:,.0f}/year",
                    "weight": "high"
                })
        
        # 6. Calculate confidence
        signal_count = len(result["signals"])
        if signal_count >= 4 or sred_mentioned:
            result["confidence"] = "high"
        elif signal_count >= 2:
            result["confidence"] = "medium"
        else:
            result["confidence"] = "low"
        
        # Cap score at 100
        result["rd_intensity_score"] = min(100, result["rd_intensity_score"])
        
        # Save to database
        self._save_scan_result(result, sector)
        
        return result
    
    def _detect_sred_mentions(self, text: str) -> bool:
        """Detect SR&ED related mentions in text."""
        for keyword in SRED_KEYWORDS[:8]:  # Primary SR&ED keywords
            if keyword in text:
                return True
        return False
    
    def _detect_cdae_mentions(self, text: str) -> bool:
        """Detect CDAE (Quebec) mentions in text."""
        cdae_keywords = ["cdae", "crédit d'impôt", "affaires électroniques", 
                         "e-business credit", "multimedia credit"]
        for keyword in cdae_keywords:
            if keyword in text:
                return True
        return False
    
    def _count_rd_jobs(self, job_titles: List[str]) -> int:
        """Count R&D related job postings."""
        rd_count = 0
        for title in job_titles:
            title_lower = title.lower()
            for keyword in SRED_JOB_KEYWORDS:
                if keyword in title_lower:
                    rd_count += 1
                    break
        return rd_count
    
    def _detect_consultant(self, text: str) -> Optional[str]:
        """Detect SR&ED consultant relationships."""
        for consultant in SRED_CONSULTANTS:
            if consultant in text:
                return consultant.title()
        return None
    
    def _get_sector_rd_intensity(self, sector: str) -> float:
        """Get typical R&D intensity for sector."""
        if not sector:
            return 0.10  # Default
        
        sector_lower = sector.lower()
        
        for sector_key, intensity in SECTOR_RD_INTENSITY.items():
            if sector_key in sector_lower:
                return intensity
        
        # Check for tech indicators
        tech_indicators = ["tech", "software", "digital", "platform", "saas"]
        for indicator in tech_indicators:
            if indicator in sector_lower:
                return 0.15
        
        return 0.08  # Default for unknown sectors
    
    def _estimate_rd_metrics(self, employees: int, sector: str = None,
                             rd_jobs: int = 0, sred_mentioned: bool = False) -> Dict[str, Any]:
        """
        Estimate R&D spend, headcount, and potential tax credits.
        """
        estimates = {
            "rd_spend_annual": None,
            "rd_headcount": None,
            "rd_ratio": None,
            "sred_credit_potential": None,
            "cdae_credit_potential": None,
        }
        
        if not employees or employees <= 0:
            return estimates
        
        # Estimate R&D headcount
        sector_intensity = self._get_sector_rd_intensity(sector)
        
        # Base R&D ratio on sector and signals
        if sred_mentioned:
            rd_ratio = max(sector_intensity, 0.30)  # At least 30% if claiming SR&ED
        elif rd_jobs > 5:
            rd_ratio = max(sector_intensity, 0.25)
        elif rd_jobs > 0:
            rd_ratio = max(sector_intensity, 0.15)
        else:
            rd_ratio = sector_intensity
        
        estimates["rd_ratio"] = rd_ratio
        estimates["rd_headcount"] = int(employees * rd_ratio)
        
        # Estimate R&D spend (headcount * average salary)
        avg_rd_salary = 105000  # Blended average for Quebec tech
        estimates["rd_spend_annual"] = estimates["rd_headcount"] * avg_rd_salary
        
        # SR&ED credit estimate
        # Federal SR&ED: ~35% for CCPCs on first $3M, 15% after
        # Simplified: assume average 25% effective rate on R&D spend
        sred_rate = 0.25
        estimates["sred_credit_potential"] = int(estimates["rd_spend_annual"] * sred_rate)
        
        # CDAE estimate
        # 30% credit on salaries up to $83,333/employee (Quebec)
        if sector and any(kw in sector.lower() for kw in ["software", "tech", "saas", "digital"]):
            max_cdae_salary = 83333
            cdae_eligible_salaries = estimates["rd_headcount"] * min(avg_rd_salary, max_cdae_salary)
            estimates["cdae_credit_potential"] = int(cdae_eligible_salaries * 0.30)
        
        return estimates
    
    def _save_scan_result(self, result: Dict, sector: str):
        """Save SR&ED scan result to database."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        estimates = result.get("estimates", {})
        summary = result.get("summary", {})
        
        c.execute("""
            INSERT INTO sred_signals (
                company_id, scan_date,
                sred_mentioned, cdae_mentioned, rd_jobs_count, consultant_detected,
                estimated_rd_spend, estimated_rd_headcount, rd_intensity_score,
                sector, sector_rd_benchmark,
                signals, confidence, raw_data
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            result["company_id"],
            result["scan_date"],
            1 if summary.get("sred_mentioned") else 0,
            1 if summary.get("cdae_mentioned") else 0,
            summary.get("rd_jobs_found", 0),
            summary.get("consultant_detected"),
            estimates.get("rd_spend_annual"),
            estimates.get("rd_headcount"),
            result.get("rd_intensity_score", 0),
            sector,
            self._get_sector_rd_intensity(sector),
            json.dumps(result.get("signals", [])),
            result.get("confidence"),
            json.dumps(result)
        ))
        
        conn.commit()
        conn.close()
    
    def get_cached_scan(self, company_id: str) -> Optional[Dict]:
        """Get cached SR&ED scan for a company."""
        conn = sqlite3.connect(self.db_path)
        
        try:
            import pandas as pd
            df = pd.read_sql("""
                SELECT * FROM sred_signals
                WHERE company_id = ?
                ORDER BY scan_date DESC
                LIMIT 1
            """, conn, params=(company_id,))
            
            if len(df) > 0:
                record = df.iloc[0].to_dict()
                # Parse JSON fields
                for field in ['signals', 'raw_data']:
                    if record.get(field):
                        try:
                            val = record[field]
                            if isinstance(val, bytes):
                                val = val.decode('utf-8')
                            record[field] = json.loads(val)
                        except:
                            pass
                return record
        except Exception as e:
            logger.error(f"Failed to get cached SR&ED scan: {e}")
        finally:
            conn.close()
        
        return None
    
    def get_rd_score(self, company_id: str) -> Dict[str, Any]:
        """
        Get R&D intensity score for Funding Radar integration.
        """
        cached = self.get_cached_scan(company_id)
        
        result = {
            "company_id": company_id,
            "score": 0,
            "signals": [],
            "estimates": {},
            "data_available": False
        }
        
        if not cached:
            return result
        
        result["data_available"] = True
        result["score"] = cached.get("rd_intensity_score", 0)
        
        # Parse signals
        signals = cached.get("signals", [])
        if isinstance(signals, str):
            try:
                signals = json.loads(signals)
            except:
                signals = []
        result["signals"] = signals
        
        # Add estimates
        result["estimates"] = {
            "rd_spend": cached.get("estimated_rd_spend"),
            "rd_headcount": cached.get("estimated_rd_headcount"),
            "sred_credit": None,  # Would need full raw_data parse
        }
        
        return result
    
    def batch_scan(self, company_ids: List[str]) -> List[Dict]:
        """Scan multiple companies for SR&ED signals."""
        results = []
        conn = sqlite3.connect(self.db_path)
        
        for company_id in company_ids:
            try:
                import pandas as pd
                company_df = pd.read_sql("""
                    SELECT name, description, iq_sector, employees
                    FROM companies WHERE company_id = ?
                """, conn, params=(company_id,))
                
                if len(company_df) > 0:
                    row = company_df.iloc[0]
                    
                    # Get job titles if available
                    job_titles = []
                    try:
                        jobs_df = pd.read_sql("""
                            SELECT title FROM job_postings
                            WHERE company_id = ?
                            ORDER BY scraped_date DESC
                            LIMIT 50
                        """, conn, params=(company_id,))
                        if len(jobs_df) > 0:
                            job_titles = jobs_df['title'].tolist()
                    except:
                        pass
                    
                    result = self.scan_company(
                        company_id=company_id,
                        company_name=row.get('name', ''),
                        description=row.get('description'),
                        sector=row.get('iq_sector'),
                        employees=row.get('employees'),
                        job_titles=job_titles
                    )
                    results.append(result)
                    
            except Exception as e:
                logger.error(f"SR&ED scan failed for {company_id}: {e}")
                results.append({
                    "company_id": company_id,
                    "error": str(e)
                })
        
        conn.close()
        return results


class SREDAnalyzer:
    """
    Analyzes SR&ED data across the portfolio.
    """
    
    def __init__(self, db_path: str = "pipeline_data.db"):
        self.db_path = db_path
    
    def get_portfolio_rd_summary(self) -> Dict[str, Any]:
        """Get R&D summary across all scanned companies."""
        conn = sqlite3.connect(self.db_path)
        
        try:
            import pandas as pd
            df = pd.read_sql("""
                SELECT 
                    ss.*,
                    c.name,
                    c.pipeline_stage
                FROM sred_signals ss
                JOIN companies c ON ss.company_id = c.company_id
                WHERE ss.id IN (
                    SELECT MAX(id) FROM sred_signals GROUP BY company_id
                )
            """, conn)
            
            if len(df) == 0:
                return {"error": "No SR&ED data available"}
            
            # Calculate summary stats
            summary = {
                "companies_scanned": len(df),
                "sred_likely": len(df[df['sred_mentioned'] == 1]),
                "cdae_likely": len(df[df['cdae_mentioned'] == 1]),
                "total_estimated_rd_spend": df['estimated_rd_spend'].sum(),
                "total_estimated_rd_headcount": df['estimated_rd_headcount'].sum(),
                "avg_rd_intensity": df['rd_intensity_score'].mean(),
                "high_rd_companies": len(df[df['rd_intensity_score'] >= 60]),
                "by_sector": df.groupby('sector')['rd_intensity_score'].mean().to_dict(),
            }
            
            return summary
            
        except Exception as e:
            logger.error(f"Portfolio summary failed: {e}")
            return {"error": str(e)}
        finally:
            conn.close()


if __name__ == "__main__":
    # Test
    tracker = SREDTracker()
    
    result = tracker.scan_company(
        company_id="test-001",
        company_name="Hopper Inc.",
        description="AI-powered travel booking platform with proprietary machine learning algorithms",
        sector="AI / Machine Learning",
        employees=500,
        job_titles=["Senior ML Engineer", "Data Scientist", "Research Scientist", "Software Engineer"]
    )
    
    print(json.dumps(result, indent=2, default=str))
