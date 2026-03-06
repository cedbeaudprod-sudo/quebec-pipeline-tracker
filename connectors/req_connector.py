"""
REQ Connector - Registraire des entreprises du Québec
Official Quebec corporate registry data.

Data available:
- NEQ (Numéro d'entreprise du Québec)
- Legal name and operating names
- Incorporation date
- Legal form (Inc., SENC, etc.)
- Status (Active, Dissolved, Struck off)
- Registered address
- Directors/Officers
- Activity sectors (SCIAN codes)

Source: https://www.registreentreprises.gouv.qc.ca
"""

import requests
from bs4 import BeautifulSoup
import re
import time
import sqlite3
from datetime import datetime, timedelta
from urllib.parse import quote_plus, urlencode
import json
from typing import Optional, Dict, List, Any, Tuple
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

REQUEST_DELAY = 2.0  # Be respectful to government servers
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

# REQ Base URLs
REQ_SEARCH_URL = "https://www.registreentreprises.gouv.qc.ca/RQAnonyworksearchme/GR/GR03/GR03A2_19A_PIU_RechsijmplActworksv_PC/PageRech.aspx"
REQ_DETAIL_BASE = "https://www.registreentreprises.gouv.qc.ca"


class REQConnector:
    """
    Connector to Quebec's corporate registry (Registraire des entreprises).
    Fetches official company data for validation and enrichment.
    """
    
    # Legal form mappings
    LEGAL_FORMS = {
        "Société par actions": "Corporation (Inc.)",
        "Société en nom collectif": "General Partnership (SENC)",
        "Société en commandite": "Limited Partnership (SEC)",
        "Entreprise individuelle": "Sole Proprietorship",
        "Coopérative": "Cooperative",
        "OBNL": "Non-Profit (OBNL)",
        "Société en participation": "Joint Venture",
    }
    
    # Status mappings
    STATUS_MAP = {
        "Immatriculée": "active",
        "Radiée": "struck_off",
        "Dissoute": "dissolved",
        "En liquidation": "liquidating",
        "Fermée": "closed",
    }
    
    def __init__(self, db_path: str = "pipeline_data.db"):
        self.db_path = db_path
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": USER_AGENT,
            "Accept-Language": "fr-CA,fr;q=0.9,en;q=0.8"
        })
        self._init_req_tables()
    
    def _init_req_tables(self):
        """Initialize REQ data tables."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        c.execute("""
            CREATE TABLE IF NOT EXISTS req_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company_id TEXT,
                neq TEXT,
                legal_name TEXT,
                operating_names TEXT,
                legal_form TEXT,
                status TEXT,
                status_raw TEXT,
                incorporation_date TEXT,
                registered_address TEXT,
                city TEXT,
                postal_code TEXT,
                directors TEXT,
                scian_codes TEXT,
                last_annual_update TEXT,
                scraped_date TEXT,
                raw_data TEXT,
                validation_flags TEXT,
                
                FOREIGN KEY (company_id) REFERENCES companies(company_id)
            )
        """)
        
        c.execute("""
            CREATE TABLE IF NOT EXISTS req_directors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company_id TEXT,
                neq TEXT,
                name TEXT,
                role TEXT,
                start_date TEXT,
                end_date TEXT,
                is_current INTEGER DEFAULT 1,
                scraped_date TEXT,
                
                FOREIGN KEY (company_id) REFERENCES companies(company_id)
            )
        """)
        
        conn.commit()
        conn.close()
    
    def _safe_request(self, url: str, method: str = "GET", data: Dict = None, timeout: int = 15) -> Optional[requests.Response]:
        """Make a rate-limited request."""
        try:
            time.sleep(REQUEST_DELAY)
            if method == "POST":
                response = self.session.post(url, data=data, timeout=timeout)
            else:
                response = self.session.get(url, timeout=timeout)
            response.raise_for_status()
            return response
        except Exception as e:
            logger.warning(f"Request failed for {url}: {e}")
            return None
    
    def search_company(self, company_name: str, include_inactive: bool = False) -> List[Dict[str, Any]]:
        """
        Search REQ for a company by name.
        Returns list of matching companies with basic info.
        """
        results = []
        
        try:
            # REQ search is complex with ASP.NET viewstate
            # We'll use a simplified approach that works for most cases
            
            # Clean company name for search
            search_name = company_name.strip()
            # Remove common suffixes for broader search
            for suffix in [" Inc.", " Inc", " Ltée", " Ltd", " SENC", " SEC"]:
                search_name = search_name.replace(suffix, "")
            
            # Build search URL (simplified direct search)
            search_url = f"https://www.registreentreprises.gouv.qc.ca/RQAnonyworksearchme/GR/GR03/GR03A2_19A_PIU_RechSworksimworkspl_PC/PageRech.aspx?T1.NomEntworksreworkspr={quote_plus(search_name)}"
            
            # Alternative: Use the API-like endpoint if available
            # For now, we'll simulate the search results structure
            
            logger.info(f"Searching REQ for: {search_name}")
            
            # Since REQ requires complex session handling, we'll create a mock structure
            # that can be filled in when we have actual scraping working
            
            # Attempt to get search page
            response = self._safe_request(search_url)
            
            if response:
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Look for result table
                result_rows = soup.find_all('tr', class_=re.compile(r'result|ligne|row', re.I))
                
                for row in result_rows[:10]:  # Limit results
                    cells = row.find_all('td')
                    if len(cells) >= 3:
                        result = {
                            "neq": self._extract_neq(cells[0].get_text(strip=True)),
                            "name": cells[1].get_text(strip=True) if len(cells) > 1 else "",
                            "status": cells[2].get_text(strip=True) if len(cells) > 2 else "",
                            "source": "req_search"
                        }
                        if result["neq"] or result["name"]:
                            results.append(result)
            
        except Exception as e:
            logger.error(f"REQ search failed for {company_name}: {e}")
        
        return results
    
    def _extract_neq(self, text: str) -> str:
        """Extract NEQ number from text."""
        # NEQ format: 10 digits, often formatted as 1234567890 or 1234-5678-90
        neq_match = re.search(r'(\d{10}|\d{4}[-\s]?\d{4}[-\s]?\d{2})', text)
        if neq_match:
            return re.sub(r'[-\s]', '', neq_match.group(1))
        return ""
    
    def get_company_details(self, neq: str) -> Dict[str, Any]:
        """
        Get detailed company information from REQ by NEQ number.
        """
        result = {
            "neq": neq,
            "legal_name": None,
            "operating_names": [],
            "legal_form": None,
            "status": None,
            "status_raw": None,
            "incorporation_date": None,
            "registered_address": None,
            "city": None,
            "postal_code": None,
            "directors": [],
            "scian_codes": [],
            "last_annual_update": None,
            "scraped_date": datetime.now().isoformat(),
            "error": None
        }
        
        if not neq or len(neq) != 10:
            result["error"] = "Invalid NEQ format"
            return result
        
        try:
            # REQ detail page URL
            detail_url = f"https://www.registreentreprises.gouv.qc.ca/RQAnonyworksearchme/GR/GR03/GR03A2_19A_PIU_RechSworksimworkspl_PC/PageEworksxtworksrait.aspx?T1.Ession={neq}"
            
            response = self._safe_request(detail_url)
            
            if response:
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Parse company details from page
                result = self._parse_company_page(soup, result)
            else:
                result["error"] = "Failed to fetch details page"
                
        except Exception as e:
            logger.error(f"REQ detail fetch failed for NEQ {neq}: {e}")
            result["error"] = str(e)
        
        return result
    
    def _parse_company_page(self, soup: BeautifulSoup, result: Dict) -> Dict:
        """Parse REQ company detail page."""
        
        # Common field patterns in REQ pages
        field_patterns = {
            "legal_name": [r"nom\s*juridique", r"dénomination\s*sociale", r"raison\s*sociale"],
            "neq": [r"neq", r"numéro\s*d'entreprise"],
            "legal_form": [r"forme\s*juridique", r"type\s*d'entreprise"],
            "status": [r"état", r"statut"],
            "incorporation_date": [r"date\s*de\s*constitution", r"date\s*d'immatriculation"],
            "address": [r"adresse", r"siège\s*social"],
        }
        
        # Try to find labeled fields
        for label_elem in soup.find_all(['label', 'th', 'dt', 'span'], class_=re.compile(r'label|champ|field', re.I)):
            label_text = label_elem.get_text(strip=True).lower()
            
            # Find associated value
            value_elem = label_elem.find_next(['td', 'dd', 'span', 'div'])
            if not value_elem:
                continue
            value_text = value_elem.get_text(strip=True)
            
            # Match to fields
            for field, patterns in field_patterns.items():
                for pattern in patterns:
                    if re.search(pattern, label_text, re.I):
                        if field == "legal_name" and not result["legal_name"]:
                            result["legal_name"] = value_text
                        elif field == "legal_form" and not result["legal_form"]:
                            result["legal_form"] = value_text
                            # Map to standardized form
                            for fr_form, en_form in self.LEGAL_FORMS.items():
                                if fr_form.lower() in value_text.lower():
                                    result["legal_form"] = en_form
                                    break
                        elif field == "status" and not result["status"]:
                            result["status_raw"] = value_text
                            result["status"] = self._map_status(value_text)
                        elif field == "incorporation_date" and not result["incorporation_date"]:
                            result["incorporation_date"] = self._parse_date(value_text)
                        elif field == "address" and not result["registered_address"]:
                            result["registered_address"] = value_text
                            # Try to extract city and postal code
                            postal_match = re.search(r'([A-Z]\d[A-Z]\s*\d[A-Z]\d)', value_text)
                            if postal_match:
                                result["postal_code"] = postal_match.group(1)
                        break
        
        # Look for directors table
        directors_table = soup.find('table', id=re.compile(r'dirigeant|admin|director', re.I))
        if directors_table:
            for row in directors_table.find_all('tr')[1:]:  # Skip header
                cells = row.find_all('td')
                if len(cells) >= 2:
                    result["directors"].append({
                        "name": cells[0].get_text(strip=True),
                        "role": cells[1].get_text(strip=True) if len(cells) > 1 else "Director"
                    })
        
        return result
    
    def _map_status(self, status_text: str) -> str:
        """Map French status to standardized English."""
        status_lower = status_text.lower()
        for fr_status, en_status in self.STATUS_MAP.items():
            if fr_status.lower() in status_lower:
                return en_status
        return "unknown"
    
    def _parse_date(self, date_text: str) -> Optional[str]:
        """Parse French date format to ISO."""
        # Common formats: "15 janvier 2020", "2020-01-15", "15/01/2020"
        
        # Try ISO format first
        iso_match = re.search(r'(\d{4})-(\d{2})-(\d{2})', date_text)
        if iso_match:
            return f"{iso_match.group(1)}-{iso_match.group(2)}-{iso_match.group(3)}"
        
        # French month names
        months_fr = {
            "janvier": "01", "février": "02", "mars": "03", "avril": "04",
            "mai": "05", "juin": "06", "juillet": "07", "août": "08",
            "septembre": "09", "octobre": "10", "novembre": "11", "décembre": "12"
        }
        
        for month_name, month_num in months_fr.items():
            if month_name in date_text.lower():
                match = re.search(r'(\d{1,2})\s+' + month_name + r'\s+(\d{4})', date_text.lower())
                if match:
                    day = match.group(1).zfill(2)
                    year = match.group(2)
                    return f"{year}-{month_num}-{day}"
        
        # Try DD/MM/YYYY
        slash_match = re.search(r'(\d{2})/(\d{2})/(\d{4})', date_text)
        if slash_match:
            return f"{slash_match.group(3)}-{slash_match.group(2)}-{slash_match.group(1)}"
        
        return None
    
    def lookup_and_validate(self, company_id: str, company_name: str, 
                            known_neq: str = None) -> Dict[str, Any]:
        """
        Look up company in REQ and validate against pipeline data.
        Returns validation results and any discrepancies found.
        """
        result = {
            "company_id": company_id,
            "company_name": company_name,
            "lookup_date": datetime.now().isoformat(),
            "found": False,
            "neq": None,
            "req_data": None,
            "validation": {
                "status_ok": None,
                "name_match": None,
                "is_active": None,
                "flags": []
            }
        }
        
        # If we have a known NEQ, use it directly
        if known_neq:
            req_data = self.get_company_details(known_neq)
            if not req_data.get("error"):
                result["found"] = True
                result["neq"] = known_neq
                result["req_data"] = req_data
        else:
            # Search by name
            search_results = self.search_company(company_name)
            if search_results:
                # Take best match (first result for now)
                best_match = search_results[0]
                if best_match.get("neq"):
                    req_data = self.get_company_details(best_match["neq"])
                    if not req_data.get("error"):
                        result["found"] = True
                        result["neq"] = best_match["neq"]
                        result["req_data"] = req_data
        
        # Validate if found
        if result["found"] and result["req_data"]:
            self._validate_company(result)
            self._save_req_record(company_id, result)
        
        return result
    
    def _validate_company(self, result: Dict):
        """Run validation checks on REQ data."""
        req_data = result["req_data"]
        validation = result["validation"]
        
        # Check status
        status = req_data.get("status", "unknown")
        validation["is_active"] = status == "active"
        validation["status_ok"] = status in ["active", "unknown"]
        
        if status == "struck_off":
            validation["flags"].append({
                "type": "status_warning",
                "severity": "high",
                "message": "Company is struck off (radiée) from REQ"
            })
        elif status == "dissolved":
            validation["flags"].append({
                "type": "status_critical",
                "severity": "critical",
                "message": "Company is dissolved"
            })
        elif status == "liquidating":
            validation["flags"].append({
                "type": "status_warning",
                "severity": "high",
                "message": "Company is in liquidation"
            })
        
        # Check name match
        req_name = req_data.get("legal_name", "").lower()
        search_name = result["company_name"].lower()
        
        # Simple fuzzy match
        name_words = set(search_name.split())
        req_words = set(req_name.split())
        common_words = name_words & req_words
        
        if len(common_words) >= min(2, len(name_words)):
            validation["name_match"] = "exact" if search_name == req_name else "close"
        else:
            validation["name_match"] = "weak"
            validation["flags"].append({
                "type": "name_mismatch",
                "severity": "low",
                "message": f"Name mismatch: '{result['company_name']}' vs REQ: '{req_data.get('legal_name')}'"
            })
        
        # Check incorporation date (company age)
        inc_date = req_data.get("incorporation_date")
        if inc_date:
            try:
                inc_datetime = datetime.strptime(inc_date, "%Y-%m-%d")
                company_age_years = (datetime.now() - inc_datetime).days / 365
                
                if company_age_years < 1:
                    validation["flags"].append({
                        "type": "new_company",
                        "severity": "info",
                        "message": f"Company incorporated less than 1 year ago ({inc_date})"
                    })
            except:
                pass
    
    def _save_req_record(self, company_id: str, result: Dict):
        """Save REQ lookup result to database."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        req_data = result.get("req_data", {})
        
        c.execute("""
            INSERT INTO req_records (
                company_id, neq, legal_name, operating_names, legal_form,
                status, status_raw, incorporation_date, registered_address,
                city, postal_code, directors, scian_codes, scraped_date,
                raw_data, validation_flags
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            company_id,
            result.get("neq"),
            req_data.get("legal_name"),
            json.dumps(req_data.get("operating_names", [])),
            req_data.get("legal_form"),
            req_data.get("status"),
            req_data.get("status_raw"),
            req_data.get("incorporation_date"),
            req_data.get("registered_address"),
            req_data.get("city"),
            req_data.get("postal_code"),
            json.dumps(req_data.get("directors", [])),
            json.dumps(req_data.get("scian_codes", [])),
            datetime.now().isoformat(),
            json.dumps(req_data),
            json.dumps(result.get("validation", {}).get("flags", []))
        ))
        
        # Save directors separately
        for director in req_data.get("directors", []):
            c.execute("""
                INSERT INTO req_directors (
                    company_id, neq, name, role, scraped_date
                ) VALUES (?, ?, ?, ?, ?)
            """, (
                company_id,
                result.get("neq"),
                director.get("name"),
                director.get("role"),
                datetime.now().isoformat()
            ))
        
        conn.commit()
        conn.close()
    
    def get_cached_record(self, company_id: str) -> Optional[Dict]:
        """Get cached REQ record for a company."""
        conn = sqlite3.connect(self.db_path)
        
        try:
            import pandas as pd
            df = pd.read_sql("""
                SELECT * FROM req_records
                WHERE company_id = ?
                ORDER BY scraped_date DESC
                LIMIT 1
            """, conn, params=(company_id,))
            
            if len(df) > 0:
                record = df.iloc[0].to_dict()
                # Parse JSON fields
                for field in ['operating_names', 'directors', 'scian_codes', 'validation_flags', 'raw_data']:
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
            logger.error(f"Failed to get cached REQ record: {e}")
        finally:
            conn.close()
        
        return None
    
    def batch_validate(self, company_ids: List[str]) -> List[Dict]:
        """Validate multiple companies against REQ."""
        results = []
        
        conn = sqlite3.connect(self.db_path)
        
        for company_id in company_ids:
            try:
                import pandas as pd
                company_df = pd.read_sql(
                    "SELECT name FROM companies WHERE company_id = ?",
                    conn, params=(company_id,)
                )
                
                if len(company_df) > 0:
                    company_name = company_df.iloc[0]['name']
                    result = self.lookup_and_validate(company_id, company_name)
                    results.append(result)
                    
            except Exception as e:
                logger.error(f"Batch validation failed for {company_id}: {e}")
                results.append({
                    "company_id": company_id,
                    "error": str(e)
                })
        
        conn.close()
        return results


class REQAnalyzer:
    """
    Analyzes REQ data for investment signals.
    """
    
    def __init__(self, db_path: str = "pipeline_data.db"):
        self.db_path = db_path
    
    def get_validation_score(self, company_id: str) -> Dict[str, Any]:
        """
        Generate a validation score based on REQ data.
        Used for due diligence and risk assessment.
        """
        connector = REQConnector(self.db_path)
        cached = connector.get_cached_record(company_id)
        
        result = {
            "company_id": company_id,
            "score": 50,  # Neutral baseline
            "signals": [],
            "data_available": False
        }
        
        if not cached:
            result["signals"].append({
                "type": "no_req_data",
                "detail": "No REQ validation performed yet",
                "weight": "low"
            })
            return result
        
        result["data_available"] = True
        score = 50
        
        # Status check
        status = cached.get("status")
        if status == "active":
            score += 20
            result["signals"].append({
                "type": "req_active",
                "detail": "Company is active in REQ",
                "weight": "medium"
            })
        elif status in ["struck_off", "dissolved", "liquidating"]:
            score -= 50
            result["signals"].append({
                "type": "req_inactive",
                "detail": f"Company status: {status}",
                "weight": "high"
            })
        
        # Incorporation age
        inc_date = cached.get("incorporation_date")
        if inc_date:
            try:
                inc_datetime = datetime.strptime(inc_date, "%Y-%m-%d")
                age_years = (datetime.now() - inc_datetime).days / 365
                
                if age_years >= 3:
                    score += 10
                    result["signals"].append({
                        "type": "established",
                        "detail": f"Incorporated {age_years:.1f} years ago",
                        "weight": "low"
                    })
                elif age_years < 1:
                    result["signals"].append({
                        "type": "new_company",
                        "detail": f"Incorporated less than 1 year ago",
                        "weight": "medium"
                    })
            except:
                pass
        
        # Directors
        directors = cached.get("directors", [])
        if isinstance(directors, str):
            try:
                directors = json.loads(directors)
            except:
                directors = []
        
        if len(directors) >= 3:
            score += 10
            result["signals"].append({
                "type": "board_structure",
                "detail": f"{len(directors)} directors on record",
                "weight": "low"
            })
        
        # Validation flags from lookup
        flags = cached.get("validation_flags", [])
        if isinstance(flags, str):
            try:
                flags = json.loads(flags)
            except:
                flags = []
        
        for flag in flags:
            if flag.get("severity") == "critical":
                score -= 30
            elif flag.get("severity") == "high":
                score -= 15
            
            result["signals"].append({
                "type": flag.get("type", "flag"),
                "detail": flag.get("message", ""),
                "weight": flag.get("severity", "low")
            })
        
        result["score"] = max(0, min(100, score))
        return result


if __name__ == "__main__":
    # Test
    connector = REQConnector()
    
    # Test search
    results = connector.search_company("Hopper")
    print(json.dumps(results, indent=2))
