"""
metrics_engine.py
------------------
Central KPI calculation layer for the PlaceMux College-Value Dashboard.

Every metric is computed via SQL against the SQLite database and returned
as a plain Python value or a pandas DataFrame, so the Streamlit dashboard
(dashboard.py) never has to write SQL itself -- it just calls a method on
MetricsEngine.

Metrics are grouped into four families, matching the Task 20 brief:
    - College metrics
    - Company metrics
    - Student metrics
    - Revenue metrics
"""

import pandas as pd

import config
from utils import get_connection, get_logger, safe_divide

logger = get_logger(__name__)


class MetricsEngine:
    """Computes KPIs for the PlaceMux marketplace from the SQLite database."""

    def __init__(self, db_path=None):
        self.db_path = db_path or config.DB_PATH

    def _query_df(self, sql: str, params: tuple = ()) -> pd.DataFrame:
        """Run a SQL query and return a pandas DataFrame."""
        with get_connection(self.db_path) as conn:
            return pd.read_sql_query(sql, conn, params=params)

    # ------------------------------------------------------------------
    # COLLEGE METRICS
    # ------------------------------------------------------------------
    def college_summary(self) -> pd.DataFrame:
        """Per-college placement summary: rate, salaries, counts."""
        sql = """
        SELECT
            c.college_id,
            c.name AS college_name,
            c.city,
            c.state,
            c.tier,
            COUNT(DISTINCT s.student_id) AS total_students,
            COUNT(DISTINCT p.student_id) AS total_placed,
            ROUND(100.0 * COUNT(DISTINCT p.student_id) /
                  NULLIF(COUNT(DISTINCT s.student_id), 0), 2) AS placement_rate_pct,
            ROUND(AVG(p.package_lpa), 2) AS avg_salary_lpa,
            ROUND(MAX(p.package_lpa), 2) AS highest_package_lpa,
            ROUND(MIN(p.package_lpa), 2) AS lowest_package_lpa
        FROM colleges c
        LEFT JOIN students s ON s.college_id = c.college_id
        LEFT JOIN placements p ON p.college_id = c.college_id
        GROUP BY c.college_id, c.name, c.city, c.state, c.tier
        ORDER BY placement_rate_pct DESC;
        """
        return self._query_df(sql)

    def college_median_salary(self) -> pd.DataFrame:
        """Median salary per college (SQLite has no native MEDIAN, so compute in pandas)."""
        sql = """
        SELECT college_id, package_lpa
        FROM placements;
        """
        df = self._query_df(sql)
        if df.empty:
            return pd.DataFrame(columns=["college_id", "median_salary_lpa"])
        result = df.groupby("college_id")["package_lpa"].median().reset_index()
        result.columns = ["college_id", "median_salary_lpa"]
        result["median_salary_lpa"] = result["median_salary_lpa"].round(2)
        return result

    def offer_acceptance_rate(self) -> pd.DataFrame:
        """Offer acceptance rate per college (based on students' offers)."""
        sql = """
        SELECT
            s.college_id,
            c.name AS college_name,
            COUNT(o.offer_id) AS total_offers,
            SUM(CASE WHEN o.status = 'Accepted' THEN 1 ELSE 0 END) AS accepted_offers,
            ROUND(100.0 * SUM(CASE WHEN o.status = 'Accepted' THEN 1 ELSE 0 END) /
                  NULLIF(COUNT(o.offer_id), 0), 2) AS acceptance_rate_pct
        FROM offers o
        JOIN applications a ON a.application_id = o.application_id
        JOIN students s ON s.student_id = a.student_id
        JOIN colleges c ON c.college_id = s.college_id
        GROUP BY s.college_id, c.name
        ORDER BY acceptance_rate_pct DESC;
        """
        return self._query_df(sql)

    def students_awaiting_placement(self) -> pd.DataFrame:
        sql = """
        SELECT
            c.college_id,
            c.name AS college_name,
            COUNT(*) AS students_awaiting
        FROM students s
        JOIN colleges c ON c.college_id = s.college_id
        WHERE s.placement_status != 'Placed'
        GROUP BY c.college_id, c.name
        ORDER BY students_awaiting DESC;
        """
        return self._query_df(sql)

    def department_performance(self, college_id=None) -> pd.DataFrame:
        """Placement performance broken down by department, optionally for one college."""
        sql = """
        SELECT
            s.department,
            COUNT(DISTINCT s.student_id) AS total_students,
            COUNT(DISTINCT p.student_id) AS placed_students,
            ROUND(100.0 * COUNT(DISTINCT p.student_id) /
                  NULLIF(COUNT(DISTINCT s.student_id), 0), 2) AS placement_rate_pct,
            ROUND(AVG(p.package_lpa), 2) AS avg_salary_lpa
        FROM students s
        LEFT JOIN placements p ON p.student_id = s.student_id
        {where_clause}
        GROUP BY s.department
        ORDER BY placement_rate_pct DESC;
        """
        where_clause = "WHERE s.college_id = ?" if college_id else ""
        sql = sql.format(where_clause=where_clause)
        params = (college_id,) if college_id else ()
        return self._query_df(sql, params)

    def placement_trend(self) -> pd.DataFrame:
        """Monthly placement volume and average salary over time."""
        sql = """
        SELECT
            strftime('%Y-%m', joining_date) AS month,
            COUNT(*) AS placements_count,
            ROUND(AVG(package_lpa), 2) AS avg_salary_lpa
        FROM placements
        GROUP BY month
        ORDER BY month;
        """
        return self._query_df(sql)

    def top_hiring_companies(self, college_id=None, limit=10) -> pd.DataFrame:
        sql = """
        SELECT
            co.name AS company_name,
            COUNT(*) AS hires
        FROM placements p
        JOIN companies co ON co.company_id = p.company_id
        {where_clause}
        GROUP BY co.name
        ORDER BY hires DESC
        LIMIT ?;
        """
        where_clause = "WHERE p.college_id = ?" if college_id else ""
        sql = sql.format(where_clause=where_clause)
        params = (college_id, limit) if college_id else (limit,)
        return self._query_df(sql, params)

    # ------------------------------------------------------------------
    # COMPANY METRICS
    # ------------------------------------------------------------------
    def company_summary(self) -> pd.DataFrame:
        sql = """
        SELECT
            co.company_id,
            co.name AS company_name,
            co.industry,
            co.tier,
            COUNT(DISTINCT j.job_id) AS jobs_posted,
            COUNT(DISTINCT a.application_id) AS applications_received,
            COUNT(DISTINCT i.interview_id) AS interviews_conducted,
            COUNT(DISTINCT o.offer_id) AS offers_made,
            COUNT(DISTINCT p.placement_id) AS hires,
            ROUND(100.0 * COUNT(DISTINCT o.offer_id) /
                  NULLIF(COUNT(DISTINCT a.application_id), 0), 2) AS offer_conversion_pct,
            ROUND(100.0 * COUNT(DISTINCT CASE WHEN i.result = 'Pass' THEN i.interview_id END) /
                  NULLIF(COUNT(DISTINCT i.interview_id), 0), 2) AS interview_conversion_pct
        FROM companies co
        LEFT JOIN jobs j ON j.company_id = co.company_id
        LEFT JOIN applications a ON a.job_id = j.job_id
        LEFT JOIN interviews i ON i.application_id = a.application_id
        LEFT JOIN offers o ON o.application_id = a.application_id
        LEFT JOIN placements p ON p.company_id = co.company_id
        GROUP BY co.company_id, co.name, co.industry, co.tier
        ORDER BY hires DESC;
        """
        return self._query_df(sql)

    def active_recruiters_count(self) -> int:
        sql = "SELECT COUNT(DISTINCT company_id) AS n FROM jobs WHERE status = 'Open';"
        df = self._query_df(sql)
        return int(df.iloc[0]["n"]) if not df.empty else 0

    def companies_hiring_count(self) -> int:
        sql = "SELECT COUNT(DISTINCT company_id) AS n FROM placements;"
        df = self._query_df(sql)
        return int(df.iloc[0]["n"]) if not df.empty else 0

    def average_hires_per_company(self) -> float:
        sql = """
        SELECT COUNT(*) * 1.0 / NULLIF(COUNT(DISTINCT company_id), 0) AS avg_hires
        FROM placements;
        """
        df = self._query_df(sql)
        return round(float(df.iloc[0]["avg_hires"]), 2) if not df.empty and df.iloc[0]["avg_hires"] else 0.0

    def hiring_funnel(self, company_id=None) -> pd.DataFrame:
        """Applications -> Interviews -> Offers -> Placements funnel counts."""
        where_job = "WHERE j.company_id = ?" if company_id else ""
        params = (company_id,) if company_id else ()

        sql_apps = f"""
            SELECT COUNT(DISTINCT a.application_id) AS n
            FROM applications a JOIN jobs j ON j.job_id = a.job_id {where_job};
        """
        sql_interviews = f"""
            SELECT COUNT(DISTINCT i.application_id) AS n
            FROM interviews i
            JOIN applications a ON a.application_id = i.application_id
            JOIN jobs j ON j.job_id = a.job_id {where_job};
        """
        sql_offers = f"""
            SELECT COUNT(DISTINCT o.application_id) AS n
            FROM offers o
            JOIN applications a ON a.application_id = o.application_id
            JOIN jobs j ON j.job_id = a.job_id {where_job};
        """
        where_placement = "WHERE p.company_id = ?" if company_id else ""
        sql_placements = f"""
            SELECT COUNT(*) AS n FROM placements p {where_placement};
        """

        stages = [
            ("Applications", self._query_df(sql_apps, params).iloc[0]["n"]),
            ("Interviews", self._query_df(sql_interviews, params).iloc[0]["n"]),
            ("Offers", self._query_df(sql_offers, params).iloc[0]["n"]),
            ("Placements (Joins)", self._query_df(sql_placements, params).iloc[0]["n"]),
        ]
        return pd.DataFrame(stages, columns=["stage", "count"])

    # ------------------------------------------------------------------
    # STUDENT METRICS
    # ------------------------------------------------------------------
    def student_funnel_rates(self) -> dict:
        """Aggregate, marketplace-wide student conversion rates."""
        sql = """
        SELECT
            (SELECT COUNT(*) FROM students) AS total_students,
            (SELECT COUNT(*) FROM applications) AS total_applications,
            (SELECT COUNT(DISTINCT student_id) FROM applications) AS students_applied,
            (SELECT COUNT(DISTINCT a.student_id)
               FROM interviews i JOIN applications a ON a.application_id = i.application_id) AS students_interviewed,
            (SELECT COUNT(DISTINCT a.student_id)
               FROM offers o JOIN applications a ON a.application_id = o.application_id) AS students_offered,
            (SELECT COUNT(DISTINCT student_id) FROM placements) AS students_placed;
        """
        df = self._query_df(sql)
        row = df.iloc[0].to_dict()
        row["applications_per_student"] = round(
            safe_divide(row["total_applications"], row["students_applied"]), 2)
        row["interview_success_rate_pct"] = round(
            100 * safe_divide(row["students_interviewed"], row["students_applied"]), 2)
        row["offer_success_rate_pct"] = round(
            100 * safe_divide(row["students_offered"], row["students_interviewed"]), 2)
        row["placement_success_rate_pct"] = round(
            100 * safe_divide(row["students_placed"], row["students_offered"]), 2)
        return row

    def student_detail(self, filters: dict = None) -> pd.DataFrame:
        """Row-level student detail with placement status, joined with placement info."""
        filters = filters or {}
        clauses, params = [], []

        if filters.get("college_id"):
            clauses.append("s.college_id = ?")
            params.append(filters["college_id"])
        if filters.get("department"):
            clauses.append("s.department = ?")
            params.append(filters["department"])
        if filters.get("batch_year"):
            clauses.append("s.batch_year = ?")
            params.append(filters["batch_year"])
        if filters.get("placement_status"):
            clauses.append("s.placement_status = ?")
            params.append(filters["placement_status"])

        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""

        sql = f"""
        SELECT
            s.student_id, s.name, s.department, s.batch_year, s.cgpa, s.skills,
            s.placement_status, c.name AS college_name,
            p.package_lpa, p.joining_date, co.name AS company_name
        FROM students s
        JOIN colleges c ON c.college_id = s.college_id
        LEFT JOIN placements p ON p.student_id = s.student_id
        LEFT JOIN companies co ON co.company_id = p.company_id
        {where_sql}
        ORDER BY s.student_id;
        """
        return self._query_df(sql, tuple(params))

    # ------------------------------------------------------------------
    # REVENUE METRICS
    # ------------------------------------------------------------------
    def total_revenue(self) -> float:
        sql = "SELECT SUM(amount) AS total FROM revenue_events;"
        df = self._query_df(sql)
        return round(float(df.iloc[0]["total"]), 2) if not df.empty and df.iloc[0]["total"] else 0.0

    def revenue_by_college(self) -> pd.DataFrame:
        sql = """
        SELECT
            c.name AS college_name,
            ROUND(SUM(r.amount), 2) AS total_revenue
        FROM revenue_events r
        JOIN colleges c ON c.college_id = r.related_id AND r.related_type = 'college'
        GROUP BY c.name
        ORDER BY total_revenue DESC;
        """
        return self._query_df(sql)

    def revenue_by_company(self) -> pd.DataFrame:
        sql = """
        SELECT
            co.name AS company_name,
            ROUND(SUM(r.amount), 2) AS total_revenue
        FROM revenue_events r
        JOIN companies co ON co.company_id = r.related_id AND r.related_type = 'company'
        GROUP BY co.name
        ORDER BY total_revenue DESC;
        """
        return self._query_df(sql)

    def revenue_trend(self) -> pd.DataFrame:
        sql = """
        SELECT
            strftime('%Y-%m', event_date) AS month,
            ROUND(SUM(amount), 2) AS revenue
        FROM revenue_events
        GROUP BY month
        ORDER BY month;
        """
        return self._query_df(sql)

    def payment_success_rate(self) -> pd.DataFrame:
        sql = """
        SELECT
            status,
            COUNT(*) AS count,
            ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM payments), 2) AS pct
        FROM payments
        GROUP BY status
        ORDER BY count DESC;
        """
        return self._query_df(sql)

    # ------------------------------------------------------------------
    # MARKETPLACE HEALTH / EXECUTIVE SUMMARY
    # ------------------------------------------------------------------
    def executive_summary(self) -> dict:
        sql = """
        SELECT
            (SELECT COUNT(*) FROM placements) AS total_placements,
            (SELECT COUNT(DISTINCT company_id) FROM placements) AS total_hiring_companies,
            (SELECT COUNT(*) FROM colleges) AS active_colleges,
            (SELECT ROUND(AVG(package_lpa), 2) FROM placements) AS avg_salary_lpa;
        """
        df = self._query_df(sql)
        result = df.iloc[0].to_dict()
        result["total_revenue"] = self.total_revenue()
        return result

    def marketplace_funnel(self) -> pd.DataFrame:
        sql = """
        SELECT 'Jobs Posted' AS stage, COUNT(*) AS count FROM jobs
        UNION ALL
        SELECT 'Applications', COUNT(*) FROM applications
        UNION ALL
        SELECT 'Interviews', COUNT(*) FROM interviews
        UNION ALL
        SELECT 'Offers', COUNT(*) FROM offers
        UNION ALL
        SELECT 'Placements', COUNT(*) FROM placements;
        """
        return self._query_df(sql)

    def liquidity_metrics(self) -> dict:
        """
        Marketplace 'liquidity' -- how efficiently supply (jobs) meets demand
        (students/applications), a common marketplace-health lens.
        """
        sql = """
        SELECT
            (SELECT COUNT(*) FROM jobs WHERE status = 'Open') AS open_jobs,
            (SELECT COUNT(*) FROM students WHERE placement_status != 'Placed') AS seeking_students,
            (SELECT COUNT(*) FROM applications) AS total_applications,
            (SELECT COUNT(*) FROM placements) AS total_placements;
        """
        df = self._query_df(sql)
        row = df.iloc[0].to_dict()
        row["jobs_to_seekers_ratio"] = round(
            safe_divide(row["open_jobs"], row["seeking_students"]), 3)
        row["overall_conversion_pct"] = round(
            100 * safe_divide(row["total_placements"], row["total_applications"]), 2)
        return row


if __name__ == "__main__":
    engine = MetricsEngine()
    logger.info("Executive summary: %s", engine.executive_summary())
    logger.info("Total revenue: %s", engine.total_revenue())
    logger.info("Student funnel rates: %s", engine.student_funnel_rates())
