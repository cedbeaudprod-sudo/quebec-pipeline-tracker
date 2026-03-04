# 🚀 Quebec Pipeline Tracker

A local Streamlit application for tracking VC deal flow, traction signals, and growth potential for Quebec startups.

![Python](https://img.shields.io/badge/Python-3.9+-blue?logo=python)
![Streamlit](https://img.shields.io/badge/Streamlit-1.28+-FF4B4B?logo=streamlit)
![SQLite](https://img.shields.io/badge/Database-SQLite-003B57?logo=sqlite)
![License](https://img.shields.io/badge/License-MIT-green)

## ✨ Features

### 📊 Pipeline Dashboard
- Key metrics: total companies, active pipeline, total raised
- Sector distribution and pipeline stage breakdown
- Recent activity feed

### 🎯 Kanban Pipeline
- 7 customizable stages: Prospect → Closing → Pass
- Visual company cards with key metrics
- Quick status indicators

### 📈 **Traction Tracker**
- **Web scraping** for growth signals:
  - News mentions (Google News RSS)
  - Job postings (Indeed, career pages)
  - Website analysis (tech stack, careers page)
  - GitHub activity (stars, forks, commits)
- **Growth Score** (0-100) with weighted components:
  - Hiring Velocity (25%)
  - Funding Momentum (30%)
  - News Buzz (15%)
  - Web Presence (15%)
  - Tech Activity (15%)
- Batch scanning for portfolio-wide analysis
- Historical score tracking

### 🏢 Company Management
- Full-text search and multi-filter
- Detailed company profiles
- Custom notes, tags, priority ratings
- Activity logging

### ⚙️ Data Management
- Import PitchBook Excel exports
- Export to CSV
- SQLite persistence

---

## 🛠️ Installation

### Prerequisites
- Python 3.9 or higher

### Quick Start

```bash
# Clone the repository
git clone https://github.com/YOUR_USERNAME/quebec-pipeline-tracker.git
cd quebec-pipeline-tracker

# Create virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run the app
streamlit run app.py
```

The app opens at `http://localhost:8501`

### Windows Quick Launch
Double-click `LANCER_APP.bat` to install dependencies and launch automatically.

---

## 📁 Project Structure

```
quebec-pipeline-tracker/
├── app.py                    # Main Streamlit application
├── requirements.txt          # Python dependencies
├── LANCER_APP.bat           # Windows launcher
├── traction/                 # Traction tracking module
│   ├── __init__.py
│   └── scraper.py           # Web scraping & growth scoring
├── pages/                    # Streamlit page components
│   └── traction_dashboard.py
├── .gitignore
├── LICENSE
└── README.md
```

---

## 📖 Usage

### 1. Import Data
1. Go to **⚙️ Paramètres**
2. Upload your PitchBook Excel export
3. Click **Importer**

### 2. Track Pipeline
1. **Pipeline** view shows companies in kanban columns
2. Click any company to edit stage, priority, notes
3. Log activities (calls, meetings, emails)

### 3. Analyze Traction
1. Go to **📈 Traction**
2. **Top Movers**: See companies ranked by growth score
3. **Analyze Company**: Scan individual company for signals
4. **Batch Scan**: Score multiple companies at once

---

## 🧮 Growth Score Methodology

| Component | Weight | Data Sources |
|-----------|--------|--------------|
| Hiring Velocity | 25% | Job postings / employee count |
| Funding Momentum | 30% | Total raised + recency of last round |
| News Buzz | 15% | News mentions + sentiment |
| Web Presence | 15% | Website, blog, careers page, tech stack |
| Tech Activity | 15% | GitHub stars, forks, commits |

---

## ⚙️ Customization

### Pipeline Stages
Edit `PIPELINE_STAGES` in `app.py`:

```python
PIPELINE_STAGES = [
    "Prospect",
    "Premier Contact", 
    "Due Diligence",
    "Préparation CI",
    "Comité d'Investissement",
    "Closing",
    "Pass"
]
```

### Scraping Rate Limits
Edit `traction/scraper.py`:
```python
REQUEST_DELAY = 2  # Seconds between requests
```

---

## 🔒 Privacy & Ethics

This tool scrapes **publicly available data only**:
- Google News RSS feeds
- Public company websites
- Public GitHub repositories
- Indeed job listings RSS

Rate limiting is enforced to be respectful of servers.

---

## 📝 Roadmap

- [ ] LinkedIn API integration
- [ ] SimilarWeb traffic estimates
- [ ] Automated weekly scans
- [ ] Slack notifications
- [ ] Multi-user support
- [ ] Historical trend charts

---

## 📄 License

MIT License - see `LICENSE` file.

---

<p align="center">Made with ☕ in Quebec</p>
