"""
config.py
---------
Central configuration for the PlaceMux College-Value Dashboard project.
All paths, dataset sizes, and tunable parameters live here so that every
other module (generation, loading, metrics, validation, dashboard) reads
from a single source of truth.
"""

from pathlib import Path

# ----------------------------------------------------------------------
# Paths
# ----------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DOCS_DIR = BASE_DIR / "docs"
DB_PATH = BASE_DIR / "placemux.db"

DATA_DIR.mkdir(exist_ok=True)
DOCS_DIR.mkdir(exist_ok=True)

# ----------------------------------------------------------------------
# Dataset sizes (minimums as specified in the Task 20 brief)
# ----------------------------------------------------------------------
NUM_COLLEGES = 100
NUM_STUDENTS = 5000
NUM_COMPANIES = 1000
NUM_JOBS = 4000
NUM_APPLICATIONS = 20000
NUM_INTERVIEWS = 8000
NUM_OFFERS = 5000          # generated above the 3,500 floor so the accepted-offer
                            # pool comfortably supports the placements minimum below
NUM_PLACEMENTS = 3000
NUM_PAYMENTS = 4000

# ----------------------------------------------------------------------
# Domain reference data
# ----------------------------------------------------------------------
DEPARTMENTS = [
    "Computer Science", "Information Technology", "Electronics & Communication",
    "Mechanical Engineering", "Civil Engineering", "Electrical Engineering",
    "Data Science", "Artificial Intelligence & ML", "Business Administration",
    "Commerce",
]

COLLEGE_TIERS = ["Tier-1", "Tier-2", "Tier-3"]

INDUSTRIES = [
    "Information Technology", "Financial Services", "E-Commerce", "Healthcare",
    "Manufacturing", "EdTech", "Consulting", "Telecommunications",
    "Automotive", "FMCG", "Logistics", "Cybersecurity",
]

COMPANY_SIZES = ["Startup (<50)", "Small (50-200)", "Mid (200-1000)", "Large (1000-5000)", "Enterprise (5000+)"]

JOB_TYPES = ["Full-Time", "Internship", "Internship + PPO"]

BATCH_YEARS = [2023, 2024, 2025, 2026, 2027]

SKILLS_POOL = [
    "Python", "Java", "SQL", "Machine Learning", "React", "Node.js", "AWS",
    "Data Analysis", "Excel", "Communication", "C++", "DevOps", "Django",
    "Power BI", "Tableau", "Deep Learning", "Docker", "Kubernetes",
    "Product Management", "Digital Marketing",
]

APPLICATION_STATUSES = ["Applied", "Shortlisted", "Interviewing", "Rejected", "Offered", "Withdrawn"]
INTERVIEW_RESULTS = ["Pass", "Fail", "On Hold"]
OFFER_STATUSES = ["Pending", "Accepted", "Declined", "Expired"]
PLACEMENT_STATUSES = ["Confirmed", "Joined", "Deferred", "Dropped"]
PAYMENT_TYPES = ["Placement Fee", "Subscription", "Job-Posting Fee", "Premium Listing"]
PAYMENT_STATUSES = ["Success", "Pending", "Failed", "Refunded"]
REVENUE_CATEGORIES = ["Placement Commission", "Subscription Revenue", "Listing Fee", "Premium Feature"]

# ----------------------------------------------------------------------
# Salary bands (in LPA - Lakhs Per Annum)
# ----------------------------------------------------------------------
MIN_PACKAGE_LPA = 2.5
MAX_PACKAGE_LPA = 65.0

# ----------------------------------------------------------------------
# Randomness
# ----------------------------------------------------------------------
RANDOM_SEED = 42

# ----------------------------------------------------------------------
# Date ranges for generated events
# ----------------------------------------------------------------------
DATA_START_DATE = "2023-06-01"
DATA_END_DATE = "2026-06-30"
