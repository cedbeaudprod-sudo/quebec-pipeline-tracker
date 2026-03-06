"""
Connectors module for Quebec Pipeline Tracker.
External data source integrations.
"""

from .jobs_scraper import JobsScraper, JobsAnalyzer
from .req_connector import REQConnector, REQAnalyzer
from .sred_tracker import SREDTracker, SREDAnalyzer

__all__ = [
    "JobsScraper", "JobsAnalyzer",
    "REQConnector", "REQAnalyzer", 
    "SREDTracker", "SREDAnalyzer"
]
