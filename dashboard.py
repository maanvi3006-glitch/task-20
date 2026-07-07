"""
dashboard.py
------------
PlaceMux College-Value Dashboard.

A multi-page Streamlit application built on top of MetricsEngine that
gives colleges, companies, and PlaceMux internal stakeholders a single
place to evaluate placement performance, hiring outcomes, student
engagement, company participation, and overall marketplace health.

Run:
    streamlit run dashboard.py
"""

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

import config
from metrics_engine import MetricsEngine
from utils import format_currency, format_percentage

# ----------------------------------------------------------------------
# Page config & shared styling
# ----------------------------------------------------------------------
st.set_page_config(
    page_title="PlaceMux College-Value Dashboard",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded",
)

PRIMARY_COLOR = "#4C6EF5"
ACCENT_COLOR = "#12B886"
WARN_COLOR = "#F59F00"
DANGER_COLOR = "#E03131"

st.markdown(
    """
    <style>
    .kpi-card {
        background-color: #F8F9FA;
        border: 1px solid #E9ECEF;
        border-radius: 10px;
        padding: 18px 16px;
        text-align: center;
    }
    .kpi-value { font-size: 1.8rem; font-weight: 700; color: #212529; }
    .kpi-label { font-size: 0.85rem; color: #6C757D; margin-top: 4px; }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_resource
def get_engine() -> MetricsEngine:
    return MetricsEngine()


def kpi_card(label: str, value: str):
    st.markdown(
        f"""
        <div class="kpi-card">
            <div class="kpi-value">{value}</div>
            <div class="kpi-label">{label}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


engine = get_engine()

# ----------------------------------------------------------------------
# Sidebar: navigation + global filters
# ----------------------------------------------------------------------
st.sidebar.title("🎓 PlaceMux")
st.sidebar.caption("College-Value Dashboard")

PAGES = [
    "Executive Summary",
    "College Dashboard",
    "Company Dashboard",
    "Student Dashboard",
    "Revenue Dashboard",
    "Marketplace Health",
]
page = st.sidebar.radio("Navigate", PAGES)

st.sidebar.markdown("---")
st.sidebar.subheader("Filters")

college_summary_df = engine.college_summary()
college_options = ["All"] + sorted(college_summary_df["college_name"].dropna().unique().tolist())
selected_college_name = st.sidebar.selectbox("College", college_options)
selected_college_id = None
if selected_college_name != "All":
    match = college_summary_df.loc[college_summary_df["college_name"] == selected_college_name]
    if not match.empty:
        selected_college_id = int(match.iloc[0]["college_id"])

department_options = ["All"] + config.DEPARTMENTS
selected_department = st.sidebar.selectbox("Department", department_options)

batch_options = ["All"] + [str(y) for y in config.BATCH_YEARS]
selected_batch = st.sidebar.selectbox("Batch Year", batch_options)

status_options = ["All", "Placed", "In Process", "Not Placed"]
selected_status = st.sidebar.selectbox("Placement Status", status_options)

salary_range = st.sidebar.slider(
    "Salary Range (LPA)", 0.0, float(config.MAX_PACKAGE_LPA), (0.0, float(config.MAX_PACKAGE_LPA))
)

st.sidebar.markdown("---")
st.sidebar.caption("Data source: SQLite (placemux.db) · Built for Task 20 demo")


def build_student_filters() -> dict:
    filters = {}
    if selected_college_id:
        filters["college_id"] = selected_college_id
    if selected_department != "All":
        filters["department"] = selected_department
    if selected_batch != "All":
        filters["batch_year"] = int(selected_batch)
    if selected_status != "All":
        filters["placement_status"] = selected_status
    return filters


# ----------------------------------------------------------------------
# PAGE 1: EXECUTIVE SUMMARY
# ----------------------------------------------------------------------
def page_executive_summary():
    st.title("📊 Executive Summary")
    st.caption("A birds-eye view of the entire PlaceMux marketplace.")

    summary = engine.executive_summary()
    cols = st.columns(5)
    with cols[0]:
        kpi_card("Total Placements", f"{int(summary['total_placements']):,}")
    with cols[1]:
        kpi_card("Hiring Companies", f"{int(summary['total_hiring_companies']):,}")
    with cols[2]:
        kpi_card("Active Colleges", f"{int(summary['active_colleges']):,}")
    with cols[3]:
        kpi_card("Total Revenue", format_currency(summary["total_revenue"]))
    with cols[4]:
        kpi_card("Avg. Salary", f"{summary['avg_salary_lpa']:.1f} LPA")

    st.markdown("---")

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Placement Trend")
        trend_df = engine.placement_trend()
        if not trend_df.empty:
            fig = px.line(trend_df, x="month", y="placements_count", markers=True,
                          title="Monthly Placements", color_discrete_sequence=[PRIMARY_COLOR])
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No placement trend data available.")

    with col2:
        st.subheader("Marketplace Funnel")
        funnel_df = engine.marketplace_funnel()
        fig = go.Figure(go.Funnel(
            y=funnel_df["stage"], x=funnel_df["count"],
            marker={"color": [PRIMARY_COLOR, ACCENT_COLOR, WARN_COLOR, "#7048E8", DANGER_COLOR]}
        ))
        fig.update_layout(title="Jobs to Placements Funnel")
        st.plotly_chart(fig, use_container_width=True)

    st.subheader("Top Colleges by Placement Rate")
    top_colleges = college_summary_df.sort_values("placement_rate_pct", ascending=False).head(10)
    fig = px.bar(top_colleges, x="college_name", y="placement_rate_pct",
                 color="tier", title="Top 10 Colleges by Placement Rate (%)")
    fig.update_layout(xaxis_title="", yaxis_title="Placement Rate (%)")
    st.plotly_chart(fig, use_container_width=True)


# ----------------------------------------------------------------------
# PAGE 2: COLLEGE DASHBOARD
# ----------------------------------------------------------------------
def page_college_dashboard():
    st.title("🏫 College Dashboard")
    st.caption("Placement performance, salary outcomes, and hiring partners by college.")

    df = college_summary_df.copy()
    if selected_college_id:
        df = df[df["college_id"] == selected_college_id]

    if df.empty:
        st.warning("No data for the selected college.")
        return

    if selected_college_id:
        row = df.iloc[0]
        cols = st.columns(4)
        with cols[0]:
            kpi_card("Placement Rate", format_percentage(row["placement_rate_pct"] or 0))
        with cols[1]:
            kpi_card("Total Students", f"{int(row['total_students']):,}")
        with cols[2]:
            kpi_card("Placed Students", f"{int(row['total_placed']):,}")
        with cols[3]:
            kpi_card("Avg Salary", f"{row['avg_salary_lpa'] or 0:.1f} LPA")
    else:
        cols = st.columns(4)
        with cols[0]:
            kpi_card("Avg Placement Rate", format_percentage(df["placement_rate_pct"].mean()))
        with cols[1]:
            kpi_card("Total Students", f"{int(df['total_students'].sum()):,}")
        with cols[2]:
            kpi_card("Total Placed", f"{int(df['total_placed'].sum()):,}")
        with cols[3]:
            kpi_card("Avg Salary", f"{df['avg_salary_lpa'].mean():.1f} LPA")

    st.markdown("---")
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Placement Rate by College" if not selected_college_id else "Salary Distribution")
        if not selected_college_id:
            fig = px.bar(df.sort_values("placement_rate_pct", ascending=False).head(20),
                         x="college_name", y="placement_rate_pct", color="tier")
            fig.update_layout(xaxis_title="", yaxis_title="Placement Rate (%)")
            st.plotly_chart(fig, use_container_width=True)
        else:
            students_df = engine.student_detail({"college_id": selected_college_id})
            placed = students_df.dropna(subset=["package_lpa"])
            if not placed.empty:
                fig = px.histogram(placed, x="package_lpa", nbins=25, color_discrete_sequence=[ACCENT_COLOR])
                fig.update_layout(xaxis_title="Package (LPA)", yaxis_title="Students")
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No placement data yet for this college.")

    with col2:
        st.subheader("Top Hiring Companies")
        top_companies = engine.top_hiring_companies(college_id=selected_college_id, limit=10)
        if not top_companies.empty:
            fig = px.bar(top_companies, x="hires", y="company_name", orientation="h",
                         color_discrete_sequence=[PRIMARY_COLOR])
            fig.update_layout(yaxis={"categoryorder": "total ascending"}, xaxis_title="Hires", yaxis_title="")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No hiring data available yet.")

    st.subheader("Department Performance")
    dept_df = engine.department_performance(college_id=selected_college_id)
    if not dept_df.empty:
        fig = px.bar(dept_df, x="department", y="placement_rate_pct", color="avg_salary_lpa",
                     color_continuous_scale="Blues", title="Placement Rate by Department")
        fig.update_layout(xaxis_title="", yaxis_title="Placement Rate (%)")
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(dept_df, use_container_width=True, hide_index=True)

    st.subheader("Placement Trend")
    trend_df = engine.placement_trend()
    if not trend_df.empty:
        fig = px.area(trend_df, x="month", y="placements_count", color_discrete_sequence=[ACCENT_COLOR])
        st.plotly_chart(fig, use_container_width=True)


# ----------------------------------------------------------------------
# PAGE 3: COMPANY DASHBOARD
# ----------------------------------------------------------------------
def page_company_dashboard():
    st.title("🏢 Company Dashboard")
    st.caption("Hiring funnel, conversion rates, and recruiting activity by company.")

    company_df = engine.company_summary()
    company_options = ["All"] + sorted(company_df["company_name"].dropna().unique().tolist())
    selected_company_name = st.selectbox("Select a Company", company_options)

    selected_company_id = None
    if selected_company_name != "All":
        match = company_df.loc[company_df["company_name"] == selected_company_name]
        if not match.empty:
            selected_company_id = int(match.iloc[0]["company_id"])

    cols = st.columns(4)
    with cols[0]:
        kpi_card("Active Recruiters", f"{engine.active_recruiters_count():,}")
    with cols[1]:
        kpi_card("Companies Hiring", f"{engine.companies_hiring_count():,}")
    with cols[2]:
        kpi_card("Avg Hires / Company", f"{engine.average_hires_per_company():.2f}")
    with cols[3]:
        total_offers = int(company_df["offers_made"].sum())
        total_apps = int(company_df["applications_received"].sum())
        kpi_card("Overall Offer Conv.", format_percentage(100 * total_offers / max(total_apps, 1)))

    st.markdown("---")
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Hiring Funnel")
        funnel_df = engine.hiring_funnel(company_id=selected_company_id)
        fig = go.Figure(go.Funnel(y=funnel_df["stage"], x=funnel_df["count"],
                                   marker={"color": [PRIMARY_COLOR, ACCENT_COLOR, WARN_COLOR, "#7048E8"]}))
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("Top Companies by Hires")
        top10 = company_df.sort_values("hires", ascending=False).head(10)
        fig = px.bar(top10, x="hires", y="company_name", orientation="h", color="industry")
        fig.update_layout(yaxis={"categoryorder": "total ascending"}, yaxis_title="", xaxis_title="Hires")
        st.plotly_chart(fig, use_container_width=True)

    st.subheader("Interview & Offer Conversion by Industry")
    industry_agg = company_df.groupby("industry").agg(
        avg_offer_conv=("offer_conversion_pct", "mean"),
        avg_interview_conv=("interview_conversion_pct", "mean"),
        hires=("hires", "sum"),
    ).reset_index()
    fig = px.scatter(industry_agg, x="avg_interview_conv", y="avg_offer_conv", size="hires",
                     color="industry", hover_name="industry",
                     labels={"avg_interview_conv": "Avg Interview Conversion (%)",
                             "avg_offer_conv": "Avg Offer Conversion (%)"})
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("Company Detail Table")
    display_df = company_df if not selected_company_id else company_df[company_df["company_id"] == selected_company_id]
    st.dataframe(display_df, use_container_width=True, hide_index=True)


# ----------------------------------------------------------------------
# PAGE 4: STUDENT DASHBOARD
# ----------------------------------------------------------------------
def page_student_dashboard():
    st.title("🎓 Student Dashboard")
    st.caption("Individual student outcomes, skills, and interview performance.")

    filters = build_student_filters()
    students_df = engine.student_detail(filters)

    if students_df.empty:
        st.warning("No students match the current filters.")
        return

    cols = st.columns(4)
    total = len(students_df)
    placed = (students_df["placement_status"] == "Placed").sum()
    with cols[0]:
        kpi_card("Students (filtered)", f"{total:,}")
    with cols[1]:
        kpi_card("Placed", f"{placed:,}")
    with cols[2]:
        kpi_card("Placement Rate", format_percentage(100 * placed / max(total, 1)))
    with cols[3]:
        avg_salary = students_df["package_lpa"].dropna().mean()
        kpi_card("Avg Salary", f"{avg_salary:.1f} LPA" if pd.notna(avg_salary) else "N/A")

    st.markdown("---")
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Placement Status")
        status_counts = students_df["placement_status"].value_counts().reset_index()
        status_counts.columns = ["status", "count"]
        fig = px.pie(status_counts, names="status", values="count", hole=0.45,
                     color_discrete_sequence=[ACCENT_COLOR, WARN_COLOR, DANGER_COLOR])
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("Salary Distribution")
        placed_df = students_df.dropna(subset=["package_lpa"])
        if not placed_df.empty:
            fig = px.box(placed_df, y="package_lpa", points="all", color_discrete_sequence=[PRIMARY_COLOR])
            fig.update_layout(yaxis_title="Package (LPA)")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No placed students in this filter to show a salary distribution.")

    st.subheader("Top Skills Among Filtered Students")
    all_skills = students_df["skills"].dropna().str.split(", ").explode()
    if not all_skills.empty:
        skill_counts = all_skills.value_counts().reset_index()
        skill_counts.columns = ["skill", "count"]
        fig = px.bar(skill_counts.head(15), x="count", y="skill", orientation="h",
                     color_discrete_sequence=[ACCENT_COLOR])
        fig.update_layout(yaxis={"categoryorder": "total ascending"}, yaxis_title="", xaxis_title="Students")
        st.plotly_chart(fig, use_container_width=True)

    st.subheader("Student Detail & Interview History")
    lookup_id = st.number_input("Look up a Student ID for interview history", min_value=0, step=1, value=0)
    if lookup_id:
        with_history_sql_df = engine._query_df(f"""
            SELECT s.student_id, s.name, i.interview_date, i.round_number, i.result, i.feedback_score,
                   co.name AS company_name, j.title
            FROM interviews i
            JOIN applications a ON a.application_id = i.application_id
            JOIN students s ON s.student_id = a.student_id
            JOIN jobs j ON j.job_id = a.job_id
            JOIN companies co ON co.company_id = j.company_id
            WHERE s.student_id = {int(lookup_id)}
            ORDER BY i.interview_date;
        """)
        if with_history_sql_df.empty:
            st.info("No interview history found for that student ID.")
        else:
            st.dataframe(with_history_sql_df, use_container_width=True, hide_index=True)

    st.dataframe(
        students_df[["student_id", "name", "college_name", "department", "batch_year",
                     "cgpa", "placement_status", "package_lpa", "company_name"]].head(500),
        use_container_width=True, hide_index=True,
    )


# ----------------------------------------------------------------------
# PAGE 5: REVENUE DASHBOARD
# ----------------------------------------------------------------------
def page_revenue_dashboard():
    st.title("💰 Revenue Dashboard")
    st.caption("Platform revenue across colleges, companies, and payment types.")

    total_rev = engine.total_revenue()
    trend_df = engine.revenue_trend()
    payment_df = engine.payment_success_rate()

    cols = st.columns(4)
    with cols[0]:
        kpi_card("Total Revenue", format_currency(total_rev))
    with cols[1]:
        latest_month_rev = trend_df.iloc[-1]["revenue"] if not trend_df.empty else 0
        kpi_card("Latest Month Revenue", format_currency(latest_month_rev))
    with cols[2]:
        success_pct = payment_df.loc[payment_df["status"] == "Success", "pct"]
        kpi_card("Payment Success Rate", format_percentage(success_pct.iloc[0] if not success_pct.empty else 0))
    with cols[3]:
        kpi_card("Total Payments", f"{int(payment_df['count'].sum()):,}")

    st.markdown("---")
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Revenue Trend (Monthly)")
        if not trend_df.empty:
            fig = px.line(trend_df, x="month", y="revenue", markers=True, color_discrete_sequence=[PRIMARY_COLOR])
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No revenue trend data available.")

    with col2:
        st.subheader("Payment Status Breakdown")
        fig = px.pie(payment_df, names="status", values="count", hole=0.4,
                     color_discrete_sequence=[ACCENT_COLOR, WARN_COLOR, DANGER_COLOR, "#7048E8"])
        st.plotly_chart(fig, use_container_width=True)

    col3, col4 = st.columns(2)
    with col3:
        st.subheader("Revenue by College (Top 15)")
        rev_college = engine.revenue_by_college().head(15)
        if not rev_college.empty:
            fig = px.bar(rev_college, x="total_revenue", y="college_name", orientation="h",
                         color_discrete_sequence=[PRIMARY_COLOR])
            fig.update_layout(yaxis={"categoryorder": "total ascending"}, yaxis_title="", xaxis_title="Revenue (₹)")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No college-linked revenue yet.")

    with col4:
        st.subheader("Revenue by Company (Top 15)")
        rev_company = engine.revenue_by_company().head(15)
        if not rev_company.empty:
            fig = px.bar(rev_company, x="total_revenue", y="company_name", orientation="h",
                         color_discrete_sequence=[ACCENT_COLOR])
            fig.update_layout(yaxis={"categoryorder": "total ascending"}, yaxis_title="", xaxis_title="Revenue (₹)")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No company-linked revenue yet.")


# ----------------------------------------------------------------------
# PAGE 6: MARKETPLACE HEALTH
# ----------------------------------------------------------------------
def page_marketplace_health():
    st.title("🌐 Marketplace Health")
    st.caption("Supply, demand, and liquidity across the PlaceMux ecosystem.")

    liquidity = engine.liquidity_metrics()
    cols = st.columns(4)
    with cols[0]:
        kpi_card("Open Jobs", f"{liquidity['open_jobs']:,}")
    with cols[1]:
        kpi_card("Students Seeking", f"{liquidity['seeking_students']:,}")
    with cols[2]:
        kpi_card("Jobs-to-Seekers Ratio", f"{liquidity['jobs_to_seekers_ratio']:.3f}")
    with cols[3]:
        kpi_card("Overall Conversion", format_percentage(liquidity["overall_conversion_pct"]))

    st.markdown("---")
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Conversion Funnel")
        funnel_df = engine.marketplace_funnel()
        fig = go.Figure(go.Funnel(
            y=funnel_df["stage"], x=funnel_df["count"],
            marker={"color": [PRIMARY_COLOR, ACCENT_COLOR, WARN_COLOR, "#7048E8", DANGER_COLOR]}
        ))
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("Funnel Stage Volumes")
        funnel_df = engine.marketplace_funnel()
        fig = px.bar(funnel_df, x="stage", y="count", color="stage",
                     color_discrete_sequence=px.colors.qualitative.Set2)
        fig.update_layout(showlegend=False, xaxis_title="", yaxis_title="Count")
        st.plotly_chart(fig, use_container_width=True)

    st.subheader("Applications vs. Placements Heatmap by Department")
    dept_df = engine.department_performance()
    if not dept_df.empty:
        heat_data = dept_df.set_index("department")[["total_students", "placed_students"]].T
        fig = px.imshow(heat_data, text_auto=True, aspect="auto",
                        color_continuous_scale="Blues",
                        labels=dict(x="Department", y="Metric", color="Count"))
        st.plotly_chart(fig, use_container_width=True)

    st.subheader("Student Funnel Rates")
    funnel_rates = engine.student_funnel_rates()
    rate_df = pd.DataFrame([
        {"stage": "Applied", "students": funnel_rates["students_applied"]},
        {"stage": "Interviewed", "students": funnel_rates["students_interviewed"]},
        {"stage": "Offered", "students": funnel_rates["students_offered"]},
        {"stage": "Placed", "students": funnel_rates["students_placed"]},
    ])
    fig = px.funnel(rate_df, x="students", y="stage")
    st.plotly_chart(fig, use_container_width=True)

    m1, m2, m3 = st.columns(3)
    with m1:
        kpi_card("Applications / Student", f"{funnel_rates['applications_per_student']:.2f}")
    with m2:
        kpi_card("Interview Success Rate", format_percentage(funnel_rates["interview_success_rate_pct"]))
    with m3:
        kpi_card("Placement Success Rate", format_percentage(funnel_rates["placement_success_rate_pct"]))


# ----------------------------------------------------------------------
# ROUTER
# ----------------------------------------------------------------------
PAGE_ROUTER = {
    "Executive Summary": page_executive_summary,
    "College Dashboard": page_college_dashboard,
    "Company Dashboard": page_company_dashboard,
    "Student Dashboard": page_student_dashboard,
    "Revenue Dashboard": page_revenue_dashboard,
    "Marketplace Health": page_marketplace_health,
}

PAGE_ROUTER[page]()
