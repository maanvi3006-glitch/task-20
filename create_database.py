"""
create_database.py
-------------------
Creates the normalized SQLite schema for PlaceMux: 10 core tables with
primary keys, foreign keys, CHECK constraints, and indexes on the columns
most frequently used for filtering and joins in the metrics engine and
dashboard.

Run:
    python create_database.py
"""

import sqlite3

import config
from utils import get_logger

logger = get_logger(__name__)

SCHEMA_STATEMENTS = [
    # ------------------------------------------------------------------
    # COLLEGES
    # ------------------------------------------------------------------
    """
    CREATE TABLE IF NOT EXISTS colleges (
        college_id      INTEGER PRIMARY KEY AUTOINCREMENT,
        name            TEXT NOT NULL,
        city            TEXT NOT NULL,
        state           TEXT NOT NULL,
        tier            TEXT NOT NULL CHECK (tier IN ('Tier-1','Tier-2','Tier-3')),
        established_year INTEGER NOT NULL,
        total_students  INTEGER NOT NULL DEFAULT 0,
        onboarded_date  TEXT NOT NULL
    );
    """,
    # ------------------------------------------------------------------
    # STUDENTS
    # ------------------------------------------------------------------
    """
    CREATE TABLE IF NOT EXISTS students (
        student_id      INTEGER PRIMARY KEY AUTOINCREMENT,
        college_id      INTEGER NOT NULL,
        name            TEXT NOT NULL,
        gender          TEXT NOT NULL,
        department      TEXT NOT NULL,
        batch_year      INTEGER NOT NULL,
        cgpa            REAL NOT NULL CHECK (cgpa >= 0 AND cgpa <= 10),
        skills          TEXT,
        email           TEXT NOT NULL UNIQUE,
        phone           TEXT,
        city            TEXT,
        placement_status TEXT NOT NULL DEFAULT 'Not Placed'
            CHECK (placement_status IN ('Not Placed','In Process','Placed')),
        FOREIGN KEY (college_id) REFERENCES colleges(college_id)
            ON DELETE CASCADE
    );
    """,
    # ------------------------------------------------------------------
    # COMPANIES
    # ------------------------------------------------------------------
    """
    CREATE TABLE IF NOT EXISTS companies (
        company_id      INTEGER PRIMARY KEY AUTOINCREMENT,
        name            TEXT NOT NULL,
        industry        TEXT NOT NULL,
        size_band       TEXT NOT NULL,
        city            TEXT NOT NULL,
        tier            TEXT NOT NULL CHECK (tier IN ('Tier-1','Tier-2','Tier-3')),
        registered_date TEXT NOT NULL
    );
    """,
    # ------------------------------------------------------------------
    # JOBS
    # ------------------------------------------------------------------
    """
    CREATE TABLE IF NOT EXISTS jobs (
        job_id          INTEGER PRIMARY KEY AUTOINCREMENT,
        company_id      INTEGER NOT NULL,
        title           TEXT NOT NULL,
        department      TEXT NOT NULL,
        package_lpa     REAL NOT NULL CHECK (package_lpa >= 0),
        job_type        TEXT NOT NULL,
        posted_date     TEXT NOT NULL,
        status          TEXT NOT NULL DEFAULT 'Open'
            CHECK (status IN ('Open','Closed','Filled')),
        FOREIGN KEY (company_id) REFERENCES companies(company_id)
            ON DELETE CASCADE
    );
    """,
    # ------------------------------------------------------------------
    # APPLICATIONS
    # ------------------------------------------------------------------
    """
    CREATE TABLE IF NOT EXISTS applications (
        application_id  INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id       INTEGER NOT NULL,
        job_id           INTEGER NOT NULL,
        applied_date     TEXT NOT NULL,
        status           TEXT NOT NULL DEFAULT 'Applied',
        FOREIGN KEY (student_id) REFERENCES students(student_id)
            ON DELETE CASCADE,
        FOREIGN KEY (job_id) REFERENCES jobs(job_id)
            ON DELETE CASCADE
    );
    """,
    # ------------------------------------------------------------------
    # INTERVIEWS
    # ------------------------------------------------------------------
    """
    CREATE TABLE IF NOT EXISTS interviews (
        interview_id     INTEGER PRIMARY KEY AUTOINCREMENT,
        application_id   INTEGER NOT NULL,
        interview_date    TEXT NOT NULL,
        round_number      INTEGER NOT NULL DEFAULT 1,
        result            TEXT NOT NULL CHECK (result IN ('Pass','Fail','On Hold')),
        feedback_score    REAL CHECK (feedback_score >= 0 AND feedback_score <= 10),
        FOREIGN KEY (application_id) REFERENCES applications(application_id)
            ON DELETE CASCADE
    );
    """,
    # ------------------------------------------------------------------
    # OFFERS
    # ------------------------------------------------------------------
    """
    CREATE TABLE IF NOT EXISTS offers (
        offer_id         INTEGER PRIMARY KEY AUTOINCREMENT,
        application_id   INTEGER NOT NULL UNIQUE,
        offer_date        TEXT NOT NULL,
        package_lpa       REAL NOT NULL CHECK (package_lpa >= 0),
        status            TEXT NOT NULL DEFAULT 'Pending'
            CHECK (status IN ('Pending','Accepted','Declined','Expired')),
        FOREIGN KEY (application_id) REFERENCES applications(application_id)
            ON DELETE CASCADE
    );
    """,
    # ------------------------------------------------------------------
    # PLACEMENTS
    # ------------------------------------------------------------------
    """
    CREATE TABLE IF NOT EXISTS placements (
        placement_id     INTEGER PRIMARY KEY AUTOINCREMENT,
        offer_id          INTEGER NOT NULL UNIQUE,
        student_id        INTEGER NOT NULL,
        college_id        INTEGER NOT NULL,
        company_id        INTEGER NOT NULL,
        joining_date       TEXT NOT NULL,
        package_lpa        REAL NOT NULL CHECK (package_lpa >= 0),
        status             TEXT NOT NULL DEFAULT 'Confirmed'
            CHECK (status IN ('Confirmed','Joined','Deferred','Dropped')),
        FOREIGN KEY (offer_id) REFERENCES offers(offer_id) ON DELETE CASCADE,
        FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE,
        FOREIGN KEY (college_id) REFERENCES colleges(college_id) ON DELETE CASCADE,
        FOREIGN KEY (company_id) REFERENCES companies(company_id) ON DELETE CASCADE
    );
    """,
    # ------------------------------------------------------------------
    # PAYMENTS
    # ------------------------------------------------------------------
    """
    CREATE TABLE IF NOT EXISTS payments (
        payment_id        INTEGER PRIMARY KEY AUTOINCREMENT,
        college_id         INTEGER,
        company_id         INTEGER,
        amount              REAL NOT NULL CHECK (amount >= 0),
        payment_date        TEXT NOT NULL,
        payment_type        TEXT NOT NULL,
        status               TEXT NOT NULL DEFAULT 'Success'
            CHECK (status IN ('Success','Pending','Failed','Refunded')),
        FOREIGN KEY (college_id) REFERENCES colleges(college_id) ON DELETE SET NULL,
        FOREIGN KEY (company_id) REFERENCES companies(company_id) ON DELETE SET NULL
    );
    """,
    # ------------------------------------------------------------------
    # REVENUE EVENTS
    # ------------------------------------------------------------------
    """
    CREATE TABLE IF NOT EXISTS revenue_events (
        event_id           INTEGER PRIMARY KEY AUTOINCREMENT,
        payment_id          INTEGER,
        related_type         TEXT NOT NULL,
        related_id           INTEGER NOT NULL,
        amount                REAL NOT NULL CHECK (amount >= 0),
        event_date            TEXT NOT NULL,
        category              TEXT NOT NULL,
        FOREIGN KEY (payment_id) REFERENCES payments(payment_id) ON DELETE CASCADE
    );
    """,
]

INDEX_STATEMENTS = [
    "CREATE INDEX IF NOT EXISTS idx_students_college ON students(college_id);",
    "CREATE INDEX IF NOT EXISTS idx_students_batch ON students(batch_year);",
    "CREATE INDEX IF NOT EXISTS idx_students_status ON students(placement_status);",
    "CREATE INDEX IF NOT EXISTS idx_jobs_company ON jobs(company_id);",
    "CREATE INDEX IF NOT EXISTS idx_applications_student ON applications(student_id);",
    "CREATE INDEX IF NOT EXISTS idx_applications_job ON applications(job_id);",
    "CREATE INDEX IF NOT EXISTS idx_applications_status ON applications(status);",
    "CREATE INDEX IF NOT EXISTS idx_interviews_application ON interviews(application_id);",
    "CREATE INDEX IF NOT EXISTS idx_offers_application ON offers(application_id);",
    "CREATE INDEX IF NOT EXISTS idx_offers_status ON offers(status);",
    "CREATE INDEX IF NOT EXISTS idx_placements_college ON placements(college_id);",
    "CREATE INDEX IF NOT EXISTS idx_placements_company ON placements(company_id);",
    "CREATE INDEX IF NOT EXISTS idx_placements_student ON placements(student_id);",
    "CREATE INDEX IF NOT EXISTS idx_payments_college ON payments(college_id);",
    "CREATE INDEX IF NOT EXISTS idx_payments_company ON payments(company_id);",
    "CREATE INDEX IF NOT EXISTS idx_revenue_payment ON revenue_events(payment_id);",
]


def create_database():
    """Create all tables and indexes. Safe to run multiple times (idempotent)."""
    logger.info("Connecting to database at %s", config.DB_PATH)
    conn = sqlite3.connect(str(config.DB_PATH))
    try:
        conn.execute("PRAGMA foreign_keys = ON;")
        cursor = conn.cursor()

        logger.info("Creating tables ...")
        for statement in SCHEMA_STATEMENTS:
            cursor.execute(statement)

        logger.info("Creating indexes ...")
        for statement in INDEX_STATEMENTS:
            cursor.execute(statement)

        conn.commit()
        logger.info("Database schema created successfully with %d tables.",
                     len(SCHEMA_STATEMENTS))
    except sqlite3.Error as exc:
        logger.error("Failed to create database schema: %s", exc)
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    create_database()
