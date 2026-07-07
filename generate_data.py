"""
generate_data.py
-----------------
Generates realistic, logically-consistent synthetic datasets for the
PlaceMux ecosystem using Faker, NumPy and Pandas, and writes them out as
CSV files under data/.

The generation follows the natural lifecycle of a placement:
    colleges -> students -> companies -> jobs -> applications
    -> interviews -> offers -> placements -> payments -> revenue_events

Each downstream table samples from valid rows of its parent table(s) so
that foreign keys always resolve, and so that funnel counts shrink in a
realistic way (not every application gets an interview, not every
interview gets an offer, not every offer converts to a placement).

Run:
    python generate_data.py
"""

import random
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
from faker import Faker

import config
from utils import get_logger

logger = get_logger(__name__)

fake = Faker("en_IN")
Faker.seed(config.RANDOM_SEED)
random.seed(config.RANDOM_SEED)
np.random.seed(config.RANDOM_SEED)

START_DATE = datetime.strptime(config.DATA_START_DATE, "%Y-%m-%d")
END_DATE = datetime.strptime(config.DATA_END_DATE, "%Y-%m-%d")


def _random_date(start: datetime = START_DATE, end: datetime = END_DATE) -> str:
    """Return a random ISO date string between start and end."""
    delta_days = (end - start).days
    offset = random.randint(0, max(delta_days, 1))
    return (start + timedelta(days=offset)).strftime("%Y-%m-%d")


def _random_date_after(after_date_str: str, max_gap_days: int = 45) -> str:
    """Return a random ISO date string that occurs after a given date."""
    after = datetime.strptime(after_date_str, "%Y-%m-%d")
    gap = random.randint(1, max_gap_days)
    result = after + timedelta(days=gap)
    if result > END_DATE:
        result = END_DATE
    return result.strftime("%Y-%m-%d")


# ----------------------------------------------------------------------
# 1. COLLEGES
# ----------------------------------------------------------------------
def generate_colleges(n=config.NUM_COLLEGES) -> pd.DataFrame:
    logger.info("Generating %d colleges ...", n)
    rows = []
    for college_id in range(1, n + 1):
        city = fake.city()
        state = fake.state()
        tier = np.random.choice(config.COLLEGE_TIERS, p=[0.2, 0.45, 0.35])
        rows.append({
            "college_id": college_id,
            "name": f"{fake.city()} Institute of Technology" if random.random() < 0.5
                    else f"{fake.last_name()} College of Engineering",
            "city": city,
            "state": state,
            "tier": tier,
            "established_year": random.randint(1965, 2015),
            "total_students": 0,  # back-filled after students are generated
            "onboarded_date": _random_date(START_DATE, START_DATE + timedelta(days=200)),
        })
    return pd.DataFrame(rows)


# ----------------------------------------------------------------------
# 2. STUDENTS
# ----------------------------------------------------------------------
def generate_students(colleges_df: pd.DataFrame, n=config.NUM_STUDENTS) -> pd.DataFrame:
    logger.info("Generating %d students ...", n)
    college_ids = colleges_df["college_id"].values
    rows = []
    for student_id in range(1, n + 1):
        gender = np.random.choice(["Male", "Female", "Other"], p=[0.55, 0.43, 0.02])
        first = fake.first_name_male() if gender == "Male" else fake.first_name_female()
        last = fake.last_name()
        skills = ", ".join(random.sample(config.SKILLS_POOL, k=random.randint(3, 7)))
        rows.append({
            "student_id": student_id,
            "college_id": int(np.random.choice(college_ids)),
            "name": f"{first} {last}",
            "gender": gender,
            "department": random.choice(config.DEPARTMENTS),
            "batch_year": random.choice(config.BATCH_YEARS),
            "cgpa": round(np.random.normal(7.5, 1.0), 2),
            "skills": skills,
            "email": f"{first.lower()}.{last.lower()}{student_id}@placemux-student.com",
            "phone": fake.msisdn()[:10],
            "city": fake.city(),
            "placement_status": "Not Placed",  # back-filled after placements are generated
        })
    df = pd.DataFrame(rows)
    df["cgpa"] = df["cgpa"].clip(4.0, 10.0)
    return df


# ----------------------------------------------------------------------
# 3. COMPANIES
# ----------------------------------------------------------------------
def generate_companies(n=config.NUM_COMPANIES) -> pd.DataFrame:
    logger.info("Generating %d companies ...", n)
    rows = []
    for company_id in range(1, n + 1):
        tier = np.random.choice(config.COLLEGE_TIERS, p=[0.15, 0.4, 0.45])
        rows.append({
            "company_id": company_id,
            "name": fake.company(),
            "industry": random.choice(config.INDUSTRIES),
            "size_band": np.random.choice(config.COMPANY_SIZES, p=[0.25, 0.25, 0.25, 0.15, 0.1]),
            "city": fake.city(),
            "tier": tier,
            "registered_date": _random_date(START_DATE, START_DATE + timedelta(days=300)),
        })
    return pd.DataFrame(rows)


# ----------------------------------------------------------------------
# 4. JOBS
# ----------------------------------------------------------------------
JOB_TITLE_TEMPLATES = [
    "Software Engineer", "Data Analyst", "Business Analyst", "Backend Developer",
    "Frontend Developer", "Full Stack Developer", "Data Scientist", "QA Engineer",
    "DevOps Engineer", "Product Analyst", "ML Engineer", "Systems Engineer",
    "Associate Consultant", "Graduate Trainee Engineer", "Cloud Engineer",
]


def generate_jobs(companies_df: pd.DataFrame, n=config.NUM_JOBS) -> pd.DataFrame:
    logger.info("Generating %d jobs ...", n)
    company_ids = companies_df["company_id"].values
    rows = []
    for job_id in range(1, n + 1):
        posted = _random_date(START_DATE, END_DATE - timedelta(days=60))
        rows.append({
            "job_id": job_id,
            "company_id": int(np.random.choice(company_ids)),
            "title": random.choice(JOB_TITLE_TEMPLATES),
            "department": random.choice(config.DEPARTMENTS),
            "package_lpa": round(float(np.clip(np.random.lognormal(mean=1.75, sigma=0.45),
                                                config.MIN_PACKAGE_LPA, config.MAX_PACKAGE_LPA)), 2),
            "job_type": np.random.choice(config.JOB_TYPES, p=[0.65, 0.2, 0.15]),
            "posted_date": posted,
            "status": np.random.choice(["Open", "Closed", "Filled"], p=[0.3, 0.35, 0.35]),
        })
    return pd.DataFrame(rows)


# ----------------------------------------------------------------------
# 5. APPLICATIONS
# ----------------------------------------------------------------------
def generate_applications(students_df: pd.DataFrame, jobs_df: pd.DataFrame,
                           n=config.NUM_APPLICATIONS) -> pd.DataFrame:
    logger.info("Generating %d applications ...", n)
    # Bias applications so students tend to apply to jobs in a matching department,
    # but allow cross-department applications too (realistic behaviour).
    students_by_dept = students_df.groupby("department")["student_id"].apply(list).to_dict()
    jobs_by_dept = jobs_df.groupby("department")["job_id"].apply(list).to_dict()
    job_posted = jobs_df.set_index("job_id")["posted_date"].to_dict()
    all_student_ids = students_df["student_id"].values
    all_job_ids = jobs_df["job_id"].values
    departments = list(config.DEPARTMENTS)

    rows = []
    for application_id in range(1, n + 1):
        if random.random() < 0.75:
            dept = random.choice(departments)
            student_id = random.choice(students_by_dept.get(dept, all_student_ids.tolist()))
            job_id = random.choice(jobs_by_dept.get(dept, all_job_ids.tolist()))
        else:
            student_id = int(np.random.choice(all_student_ids))
            job_id = int(np.random.choice(all_job_ids))

        applied_date = _random_date_after(job_posted.get(job_id, config.DATA_START_DATE), max_gap_days=30)
        rows.append({
            "application_id": application_id,
            "student_id": int(student_id),
            "job_id": int(job_id),
            "applied_date": applied_date,
            "status": "Applied",  # back-filled below based on downstream funnel
        })
    return pd.DataFrame(rows)


# ----------------------------------------------------------------------
# 6. INTERVIEWS
# ----------------------------------------------------------------------
def generate_interviews(applications_df: pd.DataFrame, n=config.NUM_INTERVIEWS) -> pd.DataFrame:
    logger.info("Generating %d interviews ...", n)
    # Sample a subset of applications to be interviewed (some get multiple rounds).
    n_unique_apps = min(int(n * 0.97), len(applications_df))
    sampled_apps = applications_df.sample(n=n_unique_apps, random_state=config.RANDOM_SEED)

    rows = []
    interview_id = 1
    remaining = n
    app_records = sampled_apps[["application_id", "applied_date"]].to_dict("records")
    idx = 0
    while remaining > 0:
        rec = app_records[idx % len(app_records)]
        round_number = (idx // len(app_records)) + 1
        if round_number > 3:
            break
        result = np.random.choice(config.INTERVIEW_RESULTS, p=[0.55, 0.3, 0.15])
        rows.append({
            "interview_id": interview_id,
            "application_id": rec["application_id"],
            "interview_date": _random_date_after(rec["applied_date"], max_gap_days=25),
            "round_number": round_number,
            "result": result,
            "feedback_score": round(float(np.clip(np.random.normal(6.5, 1.8), 0, 10)), 1),
        })
        interview_id += 1
        remaining -= 1
        idx += 1

    return pd.DataFrame(rows)


# ----------------------------------------------------------------------
# 7. OFFERS
# ----------------------------------------------------------------------
def generate_offers(applications_df: pd.DataFrame, interviews_df: pd.DataFrame,
                     jobs_df: pd.DataFrame, n=config.NUM_OFFERS) -> pd.DataFrame:
    logger.info("Generating %d offers ...", n)
    # Offers are only made to applications that had at least one 'Pass' interview result.
    passing_app_ids = interviews_df.loc[interviews_df["result"] == "Pass", "application_id"].unique()
    np.random.shuffle(passing_app_ids)

    n = min(n, len(passing_app_ids))
    chosen_app_ids = passing_app_ids[:n]

    app_lookup = applications_df.set_index("application_id")[["applied_date", "job_id"]].to_dict("index")
    job_package = jobs_df.set_index("job_id")["package_lpa"].to_dict()

    rows = []
    for offer_id, application_id in enumerate(chosen_app_ids, start=1):
        app_info = app_lookup[application_id]
        base_package = job_package.get(app_info["job_id"], config.MIN_PACKAGE_LPA)
        offered_package = round(float(base_package * np.random.uniform(0.9, 1.15)), 2)
        rows.append({
            "offer_id": offer_id,
            "application_id": int(application_id),
            "offer_date": _random_date_after(app_info["applied_date"], max_gap_days=40),
            "package_lpa": offered_package,
            "status": np.random.choice(config.OFFER_STATUSES, p=[0.1, 0.72, 0.13, 0.05]),
        })
    return pd.DataFrame(rows)


# ----------------------------------------------------------------------
# 8. PLACEMENTS
# ----------------------------------------------------------------------
def generate_placements(offers_df: pd.DataFrame, applications_df: pd.DataFrame,
                         students_df: pd.DataFrame, jobs_df: pd.DataFrame,
                         n=config.NUM_PLACEMENTS) -> pd.DataFrame:
    logger.info("Generating %d placements ...", n)
    accepted_offers = offers_df[offers_df["status"] == "Accepted"].copy()
    n = min(n, len(accepted_offers))
    accepted_offers = accepted_offers.sample(n=n, random_state=config.RANDOM_SEED)

    app_lookup = applications_df.set_index("application_id")[["student_id", "job_id"]].to_dict("index")
    student_college = students_df.set_index("student_id")["college_id"].to_dict()
    job_company = jobs_df.set_index("job_id")["company_id"].to_dict()

    rows = []
    for placement_id, (_, offer_row) in enumerate(accepted_offers.iterrows(), start=1):
        app_info = app_lookup[offer_row["application_id"]]
        student_id = app_info["student_id"]
        job_id = app_info["job_id"]
        rows.append({
            "placement_id": placement_id,
            "offer_id": int(offer_row["offer_id"]),
            "student_id": int(student_id),
            "college_id": int(student_college.get(student_id)),
            "company_id": int(job_company.get(job_id)),
            "joining_date": _random_date_after(offer_row["offer_date"], max_gap_days=60),
            "package_lpa": offer_row["package_lpa"],
            "status": np.random.choice(config.PLACEMENT_STATUSES, p=[0.25, 0.55, 0.12, 0.08]),
        })
    return pd.DataFrame(rows)


# ----------------------------------------------------------------------
# 9. PAYMENTS
# ----------------------------------------------------------------------
def generate_payments(colleges_df: pd.DataFrame, companies_df: pd.DataFrame,
                       placements_df: pd.DataFrame, n=config.NUM_PAYMENTS) -> pd.DataFrame:
    logger.info("Generating %d payments ...", n)
    college_ids = colleges_df["college_id"].values
    company_ids = companies_df["company_id"].values

    rows = []
    for payment_id in range(1, n + 1):
        payment_type = np.random.choice(config.PAYMENT_TYPES, p=[0.35, 0.3, 0.2, 0.15])
        if payment_type == "Placement Fee" and len(placements_df):
            placement = placements_df.sample(1, random_state=random.randint(0, 10_000)).iloc[0]
            amount = round(float(placement["package_lpa"]) * 100000 * 0.08, 2)  # 8% commission
            college_id = int(placement["college_id"])
            company_id = int(placement["company_id"])
            pay_date = _random_date_after(placement["joining_date"], max_gap_days=30)
        elif payment_type == "Subscription":
            college_id = int(np.random.choice(college_ids))
            company_id = None
            amount = round(float(np.random.choice([25000, 50000, 100000, 150000])), 2)
            pay_date = _random_date()
        else:
            college_id = None
            company_id = int(np.random.choice(company_ids))
            amount = round(float(np.random.uniform(5000, 75000)), 2)
            pay_date = _random_date()

        rows.append({
            "payment_id": payment_id,
            "college_id": college_id,
            "company_id": company_id,
            "amount": amount,
            "payment_date": pay_date,
            "payment_type": payment_type,
            "status": np.random.choice(config.PAYMENT_STATUSES, p=[0.82, 0.08, 0.07, 0.03]),
        })
    return pd.DataFrame(rows)


# ----------------------------------------------------------------------
# 10. REVENUE EVENTS
# ----------------------------------------------------------------------
def generate_revenue_events(payments_df: pd.DataFrame) -> pd.DataFrame:
    logger.info("Generating revenue events from %d payments ...", len(payments_df))
    category_map = {
        "Placement Fee": "Placement Commission",
        "Subscription": "Subscription Revenue",
        "Job-Posting Fee": "Listing Fee",
        "Premium Listing": "Premium Feature",
    }
    rows = []
    event_id = 1
    for _, payment in payments_df.iterrows():
        if payment["status"] != "Success":
            continue
        related_type = "college" if payment["college_id"] else "company"
        related_id = payment["college_id"] if payment["college_id"] else payment["company_id"]
        rows.append({
            "event_id": event_id,
            "payment_id": int(payment["payment_id"]),
            "related_type": related_type,
            "related_id": int(related_id) if pd.notna(related_id) else 0,
            "amount": payment["amount"],
            "event_date": payment["payment_date"],
            "category": category_map.get(payment["payment_type"], "Other"),
        })
        event_id += 1
    return pd.DataFrame(rows)


# ----------------------------------------------------------------------
# BACK-FILL HELPERS (keep denormalized convenience columns consistent)
# ----------------------------------------------------------------------
def backfill_student_status(students_df: pd.DataFrame, placements_df: pd.DataFrame,
                             applications_df: pd.DataFrame) -> pd.DataFrame:
    placed_ids = set(placements_df["student_id"].unique())
    in_process_ids = set(applications_df["student_id"].unique()) - placed_ids
    students_df["placement_status"] = students_df["student_id"].apply(
        lambda sid: "Placed" if sid in placed_ids else ("In Process" if sid in in_process_ids else "Not Placed")
    )
    return students_df


def backfill_college_totals(colleges_df: pd.DataFrame, students_df: pd.DataFrame) -> pd.DataFrame:
    counts = students_df.groupby("college_id").size()
    colleges_df["total_students"] = colleges_df["college_id"].map(counts).fillna(0).astype(int)
    return colleges_df


def backfill_application_status(applications_df: pd.DataFrame, interviews_df: pd.DataFrame,
                                  offers_df: pd.DataFrame) -> pd.DataFrame:
    interviewed_ids = set(interviews_df["application_id"].unique())
    offered_ids = set(offers_df["application_id"].unique())

    def resolve(app_id):
        if app_id in offered_ids:
            return "Offered"
        if app_id in interviewed_ids:
            return "Interviewing"
        return "Applied"

    applications_df["status"] = applications_df["application_id"].apply(resolve)
    return applications_df


# ----------------------------------------------------------------------
# MAIN PIPELINE
# ----------------------------------------------------------------------
def main():
    logger.info("=== Starting PlaceMux synthetic data generation ===")

    colleges_df = generate_colleges()
    students_df = generate_students(colleges_df)
    companies_df = generate_companies()
    jobs_df = generate_jobs(companies_df)
    applications_df = generate_applications(students_df, jobs_df)
    interviews_df = generate_interviews(applications_df)
    offers_df = generate_offers(applications_df, interviews_df, jobs_df)
    placements_df = generate_placements(offers_df, applications_df, students_df, jobs_df)
    payments_df = generate_payments(colleges_df, companies_df, placements_df)
    revenue_events_df = generate_revenue_events(payments_df)

    # Back-fill denormalized convenience fields for consistency
    students_df = backfill_student_status(students_df, placements_df, applications_df)
    colleges_df = backfill_college_totals(colleges_df, students_df)
    applications_df = backfill_application_status(applications_df, interviews_df, offers_df)

    datasets = {
        "colleges": colleges_df,
        "students": students_df,
        "companies": companies_df,
        "jobs": jobs_df,
        "applications": applications_df,
        "interviews": interviews_df,
        "offers": offers_df,
        "placements": placements_df,
        "payments": payments_df,
        "revenue_events": revenue_events_df,
    }

    for name, df in datasets.items():
        out_path = config.DATA_DIR / f"{name}.csv"
        df.to_csv(out_path, index=False)
        logger.info("Wrote %-16s -> %5d rows -> %s", name, len(df), out_path)

    logger.info("=== Data generation complete ===")


if __name__ == "__main__":
    main()
