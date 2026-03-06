"""
Unit tests for the traction scraper module.
"""

import pytest
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from traction.scraper import TractionScraper, GrowthScorer


class TestTractionScraper:
    """Tests for TractionScraper class."""
    
    @pytest.fixture
    def scraper(self, tmp_path):
        """Create a scraper with temporary database."""
        db_path = tmp_path / "test.db"
        return TractionScraper(str(db_path))
    
    def test_init_creates_tables(self, scraper):
        """Test that initialization creates required tables."""
        import sqlite3
        conn = sqlite3.connect(scraper.db_path)
        cursor = conn.cursor()
        
        # Check traction_snapshots table exists
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='traction_snapshots'"
        )
        assert cursor.fetchone() is not None
        
        # Check growth_scores table exists
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='growth_scores'"
        )
        assert cursor.fetchone() is not None
        
        conn.close()
    
    def test_scrape_news_returns_dict(self, scraper):
        """Test that news scraping returns expected structure."""
        result = scraper.scrape_news_mentions("Test Company")
        
        assert isinstance(result, dict)
        assert "mentions_count" in result
        assert "articles" in result
        assert "sentiment_avg" in result
    
    def test_analyze_website_handles_missing_url(self, scraper):
        """Test website analysis handles missing URLs gracefully."""
        result = scraper.analyze_website(None)
        
        assert isinstance(result, dict)
        assert result["status"] is None
    
    def test_analyze_website_handles_invalid_url(self, scraper):
        """Test website analysis handles invalid URLs gracefully."""
        result = scraper.analyze_website("not-a-valid-url-12345.fake")
        
        assert isinstance(result, dict)
        # Should fail gracefully
        assert result["status"] in [None, 0]
    
    def test_count_job_postings_returns_dict(self, scraper):
        """Test job counting returns expected structure."""
        result = scraper.count_job_postings("Anthropic")
        
        assert isinstance(result, dict)
        assert "total_jobs" in result
        assert "sources" in result
        assert "job_titles" in result
    
    def test_scrape_github_handles_missing_url(self, scraper):
        """Test GitHub scraping handles missing URL."""
        result = scraper.scrape_github(None)
        
        assert isinstance(result, dict)
        assert result["stars"] == 0


class TestGrowthScorer:
    """Tests for GrowthScorer class."""
    
    @pytest.fixture
    def scorer(self, tmp_path):
        """Create a scorer with temporary database."""
        db_path = tmp_path / "test.db"
        # Initialize tables first
        TractionScraper(str(db_path))
        return GrowthScorer(str(db_path))
    
    def test_calculate_score_handles_missing_company(self, scorer):
        """Test scoring handles non-existent company."""
        result = scorer.calculate_growth_score("non-existent-id")
        
        assert isinstance(result, dict)
        assert "error" in result


class TestIntegration:
    """Integration tests for the full workflow."""
    
    @pytest.fixture
    def setup(self, tmp_path):
        """Set up scraper and scorer with shared database."""
        db_path = tmp_path / "test.db"
        scraper = TractionScraper(str(db_path))
        scorer = GrowthScorer(str(db_path))
        return scraper, scorer, str(db_path)
    
    def test_full_workflow(self, setup):
        """Test collecting traction and calculating score."""
        scraper, scorer, db_path = setup
        
        # Create a test company in the database
        import sqlite3
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS companies (
                company_id TEXT PRIMARY KEY,
                name TEXT,
                website TEXT,
                employees INTEGER,
                total_raised REAL,
                last_financing_date TEXT
            )
        """)
        
        cursor.execute("""
            INSERT INTO companies (company_id, name, website, employees, total_raised)
            VALUES ('test-001', 'Test Startup', 'https://example.com', 50, 10.5)
        """)
        conn.commit()
        conn.close()
        
        # Collect traction (with a fake website that won't resolve)
        snapshot = scraper.collect_traction_snapshot(
            company_id="test-001",
            company_name="Test Startup",
            website="https://example.com"
        )
        
        assert isinstance(snapshot, dict)
        assert snapshot["company_id"] == "test-001"
        
        # Calculate score
        score = scorer.calculate_growth_score("test-001")
        
        assert isinstance(score, dict)
        assert "growth_score" in score
        assert 0 <= score["growth_score"] <= 100


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
