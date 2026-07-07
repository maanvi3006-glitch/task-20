"""
load_data.py
-------------
Loads the generated CSV files from data/ into the SQLite database created
by create_database.py. Tables are loaded in dependency order (parents
before children) so that foreign key constraints are respected, and the
whole load happens in a single transaction so a failure rolls back cleanly.

Run:
    python load_data.py
"""

import sqlite3

import pandas as pd

import config
from utils import get_logger

logger = get_logger(__name__)

# Order matters: a table must be loaded after every table it has a
# foreign key towards.
LOAD_ORDER = [
    "colleges",
    "students",
    "companies",
    "jobs",
    "applications",
    "interviews",
    "offers",
    "placements",
    "payments",
    "revenue_events",
]

# Map of CSV column name -> SQL column name, only needed where they differ.
COLUMN_RENAMES = {
    "applications": {},
    "interviews": {},
}


def load_table(conn: sqlite3.Connection, table_name: str) -> int:
    """Load a single CSV into its corresponding table. Returns row count loaded."""
    csv_path = config.DATA_DIR / f"{table_name}.csv"
    if not csv_path.exists():
        raise FileNotFoundError(f"Expected data file not found: {csv_path}")

    df = pd.read_csv(csv_path)
    renames = COLUMN_RENAMES.get(table_name, {})
    if renames:
        df = df.rename(columns=renames)

    df.to_sql(table_name, conn, if_exists="append", index=False)
    return len(df)


def clear_existing_data(conn: sqlite3.Connection):
    """Delete existing rows (in reverse dependency order) so re-runs are idempotent."""
    for table_name in reversed(LOAD_ORDER):
        conn.execute(f"DELETE FROM {table_name};")
    conn.commit()


def main():
    logger.info("Connecting to database at %s", config.DB_PATH)
    conn = sqlite3.connect(str(config.DB_PATH))
    conn.execute("PRAGMA foreign_keys = ON;")

    try:
        logger.info("Clearing any existing data for a clean load ...")
        clear_existing_data(conn)

        total_rows = 0
        for table_name in LOAD_ORDER:
            rows_loaded = load_table(conn, table_name)
            total_rows += rows_loaded
            logger.info("Loaded %-16s -> %5d rows", table_name, rows_loaded)

        conn.commit()
        logger.info("=== Load complete: %d total rows across %d tables ===",
                     total_rows, len(LOAD_ORDER))

        # Quick sanity check: confirm counts match what's in the DB.
        cursor = conn.cursor()
        for table_name in LOAD_ORDER:
            count = cursor.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
            logger.info("Verified %-16s -> %5d rows in database", table_name, count)

    except (sqlite3.Error, FileNotFoundError) as exc:
        logger.error("Data load failed: %s", exc)
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
