"""
validation.py
--------------
Data-quality validation for the PlaceMux database. Checks for:
    - Missing/null values in required fields
    - Duplicate records (by primary key and by natural key)
    - Invalid salary/package values
    - Broken foreign keys (orphan rows)
    - Basic referential/business-rule sanity checks

Produces a structured report (list of ValidationResult) and can render it
as Markdown for docs/ or print it to the console.

Run:
    python validation.py
"""

from dataclasses import dataclass, field
from datetime import datetime

import pandas as pd

import config
from utils import get_connection, get_logger

logger = get_logger(__name__)


@dataclass
class ValidationResult:
    check_name: str
    category: str
    passed: bool
    issue_count: int
    details: str = ""
    sample: list = field(default_factory=list)


class DataValidator:
    """Runs a suite of data-quality checks against the PlaceMux SQLite database."""

    def __init__(self, db_path=None):
        self.db_path = db_path or config.DB_PATH
        self.results: list[ValidationResult] = []

    def _query_df(self, sql: str) -> pd.DataFrame:
        with get_connection(self.db_path) as conn:
            return pd.read_sql_query(sql, conn)

    # ------------------------------------------------------------------
    # 1. MISSING DATA
    # ------------------------------------------------------------------
    REQUIRED_FIELDS = {
        "students": ["name", "college_id", "department", "email", "cgpa"],
        "companies": ["name", "industry", "city"],
        "jobs": ["company_id", "title", "package_lpa"],
        "applications": ["student_id", "job_id", "applied_date"],
        "placements": ["student_id", "college_id", "company_id", "package_lpa"],
        "payments": ["amount", "payment_date", "status"],
    }

    def check_missing_data(self):
        for table, fields in self.REQUIRED_FIELDS.items():
            df = self._query_df(f"SELECT * FROM {table};")
            for field_name in fields:
                if field_name not in df.columns:
                    continue
                null_count = int(df[field_name].isna().sum())
                self.results.append(ValidationResult(
                    check_name=f"missing_{table}_{field_name}",
                    category="Missing Data",
                    passed=null_count == 0,
                    issue_count=null_count,
                    details=f"{null_count} null value(s) in {table}.{field_name}",
                ))

    # ------------------------------------------------------------------
    # 2. DUPLICATE RECORDS
    # ------------------------------------------------------------------
    DUPLICATE_KEYS = {
        "students": ["email"],
        "colleges": ["name", "city"],
        "companies": ["name", "city"],
        "placements": ["offer_id"],
    }

    def check_duplicates(self):
        for table, keys in self.DUPLICATE_KEYS.items():
            df = self._query_df(f"SELECT * FROM {table};")
            if not all(k in df.columns for k in keys):
                continue
            dup_count = int(df.duplicated(subset=keys, keep=False).sum())
            self.results.append(ValidationResult(
                check_name=f"duplicates_{table}",
                category="Duplicate Records",
                passed=dup_count == 0,
                issue_count=dup_count,
                details=f"{dup_count} duplicate row(s) in {table} on key {keys}",
            ))

    # ------------------------------------------------------------------
    # 3. INVALID SALARY VALUES
    # ------------------------------------------------------------------
    def check_invalid_salaries(self):
        checks = [
            ("jobs", "package_lpa"),
            ("offers", "package_lpa"),
            ("placements", "package_lpa"),
        ]
        for table, col in checks:
            df = self._query_df(f"SELECT {col} FROM {table};")
            invalid = df[(df[col] < 0) | (df[col] > config.MAX_PACKAGE_LPA * 2) | df[col].isna()]
            self.results.append(ValidationResult(
                check_name=f"invalid_salary_{table}",
                category="Invalid Salary Values",
                passed=len(invalid) == 0,
                issue_count=len(invalid),
                details=f"{len(invalid)} row(s) in {table}.{col} outside plausible salary range",
            ))

    # ------------------------------------------------------------------
    # 4. BROKEN FOREIGN KEYS
    # ------------------------------------------------------------------
    FK_CHECKS = [
        ("students", "college_id", "colleges", "college_id"),
        ("jobs", "company_id", "companies", "company_id"),
        ("applications", "student_id", "students", "student_id"),
        ("applications", "job_id", "jobs", "job_id"),
        ("interviews", "application_id", "applications", "application_id"),
        ("offers", "application_id", "applications", "application_id"),
        ("placements", "offer_id", "offers", "offer_id"),
        ("placements", "student_id", "students", "student_id"),
        ("placements", "company_id", "companies", "company_id"),
    ]

    def check_foreign_keys(self):
        for child_table, child_col, parent_table, parent_col in self.FK_CHECKS:
            sql = f"""
                SELECT COUNT(*) AS orphan_count
                FROM {child_table} c
                LEFT JOIN {parent_table} p ON c.{child_col} = p.{parent_col}
                WHERE c.{child_col} IS NOT NULL AND p.{parent_col} IS NULL;
            """
            df = self._query_df(sql)
            orphan_count = int(df.iloc[0]["orphan_count"])
            self.results.append(ValidationResult(
                check_name=f"fk_{child_table}_{child_col}",
                category="Broken Foreign Keys",
                passed=orphan_count == 0,
                issue_count=orphan_count,
                details=f"{orphan_count} orphaned row(s): {child_table}.{child_col} -> {parent_table}.{parent_col}",
            ))

    # ------------------------------------------------------------------
    # 5. BUSINESS-RULE SANITY CHECKS
    # ------------------------------------------------------------------
    def check_business_rules(self):
        # A placement should never predate its own offer.
        sql = """
        SELECT COUNT(*) AS n
        FROM placements p
        JOIN offers o ON o.offer_id = p.offer_id
        WHERE p.joining_date < o.offer_date;
        """
        df = self._query_df(sql)
        n = int(df.iloc[0]["n"])
        self.results.append(ValidationResult(
            check_name="business_rule_placement_before_offer",
            category="Business Rules",
            passed=n == 0,
            issue_count=n,
            details=f"{n} placement(s) with a joining_date earlier than their offer_date",
        ))

        # CGPA out of the valid 0-10 range.
        sql = "SELECT COUNT(*) AS n FROM students WHERE cgpa < 0 OR cgpa > 10;"
        df = self._query_df(sql)
        n = int(df.iloc[0]["n"])
        self.results.append(ValidationResult(
            check_name="business_rule_cgpa_range",
            category="Business Rules",
            passed=n == 0,
            issue_count=n,
            details=f"{n} student(s) with CGPA outside the 0-10 range",
        ))

    # ------------------------------------------------------------------
    # RUN ALL + REPORT
    # ------------------------------------------------------------------
    def run_all(self) -> list[ValidationResult]:
        self.results = []
        logger.info("Running data validation suite ...")
        self.check_missing_data()
        self.check_duplicates()
        self.check_invalid_salaries()
        self.check_foreign_keys()
        self.check_business_rules()
        passed = sum(1 for r in self.results if r.passed)
        logger.info("Validation complete: %d/%d checks passed", passed, len(self.results))
        return self.results

    def to_markdown(self) -> str:
        lines = [
            "# PlaceMux Data Validation Report",
            f"_Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}_",
            "",
        ]
        total = len(self.results)
        passed = sum(1 for r in self.results if r.passed)
        lines.append(f"**Overall: {passed}/{total} checks passed.**")
        lines.append("")

        categories = sorted(set(r.category for r in self.results))
        for category in categories:
            lines.append(f"## {category}")
            lines.append("")
            lines.append("| Check | Status | Issues | Details |")
            lines.append("|---|---|---|---|")
            for r in self.results:
                if r.category != category:
                    continue
                status = "✅ Pass" if r.passed else "❌ Fail"
                lines.append(f"| {r.check_name} | {status} | {r.issue_count} | {r.details} |")
            lines.append("")
        return "\n".join(lines)

    def save_report(self, path=None):
        path = path or (config.DOCS_DIR / "validation_report.md")
        report_md = self.to_markdown()
        with open(path, "w") as f:
            f.write(report_md)
        logger.info("Validation report saved to %s", path)
        return path


if __name__ == "__main__":
    validator = DataValidator()
    validator.run_all()
    report_path = validator.save_report()
    print(validator.to_markdown())
