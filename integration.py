"""
integration.py
---------------
Integration layer that ties together every PlaceMux module into a single
end-to-end pipeline: schema creation -> data generation -> loading ->
validation -> metrics smoke-test. This mirrors what the four manual
commands in the README do, but as one script -- useful for CI/demo runs
and for the Task 20 "Portals Integration & Dry Run" checkpoint.

Run:
    python integration.py
"""

import sys
import time

import create_database
import generate_data
import load_data
from metrics_engine import MetricsEngine
from utils import get_logger
from validation import DataValidator

logger = get_logger(__name__)


def run_pipeline(skip_generation: bool = False) -> bool:
    """
    Runs the full PlaceMux pipeline end-to-end.

    Args:
        skip_generation: if True, reuse existing CSVs in data/ instead of
            regenerating them (useful for a fast reload/demo dry run).

    Returns:
        True if the pipeline completed and validation passed with no
        broken foreign keys; False otherwise.
    """
    start = time.time()
    logger.info("=" * 70)
    logger.info("PLACEMUX END-TO-END INTEGRATION RUN")
    logger.info("=" * 70)

    logger.info("[1/5] Creating database schema ...")
    create_database.create_database()

    if not skip_generation:
        logger.info("[2/5] Generating synthetic datasets ...")
        generate_data.main()
    else:
        logger.info("[2/5] Skipping generation, reusing existing CSVs in data/ ...")

    logger.info("[3/5] Loading data into SQLite ...")
    load_data.main()

    logger.info("[4/5] Running data validation suite ...")
    validator = DataValidator()
    results = validator.run_all()
    validator.save_report()

    broken_fk = [r for r in results if r.category == "Broken Foreign Keys" and not r.passed]
    critical_ok = len(broken_fk) == 0

    logger.info("[5/5] Smoke-testing metrics engine ...")
    engine = MetricsEngine()
    summary = engine.executive_summary()
    logger.info("Executive summary -> %s", summary)

    elapsed = time.time() - start
    logger.info("=" * 70)
    if critical_ok:
        logger.info("INTEGRATION RUN SUCCEEDED in %.1fs. Dashboard is ready:", elapsed)
        logger.info("    streamlit run dashboard.py")
    else:
        logger.error("INTEGRATION RUN COMPLETED WITH CRITICAL DATA ISSUES (%d broken FK checks).",
                      len(broken_fk))
    logger.info("=" * 70)
    return critical_ok


if __name__ == "__main__":
    skip_gen = "--skip-generation" in sys.argv
    success = run_pipeline(skip_generation=skip_gen)
    sys.exit(0 if success else 1)
