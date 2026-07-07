# PlaceMux Metrics Documentation

All metrics are computed live from `placemux.db` by `metrics_engine.py`.
This document defines exactly how each KPI is calculated.

## College Metrics

| KPI | Formula |
|---|---|
| Placement Rate | `placed_students / total_students * 100` |
| Offer Acceptance Rate | `accepted_offers / total_offers * 100`, per college |
| Average Student Salary | `AVG(package_lpa)` across a college's placements |
| Median Salary | median of `package_lpa` across a college's placements |
| Highest / Lowest Package | `MAX` / `MIN` of `package_lpa` |
| Total Students | `COUNT(student_id)` per college |
| Total Placed Students | `COUNT(DISTINCT student_id)` in `placements` per college |
| Students Awaiting Placement | students where `placement_status != 'Placed'` |

## Company Metrics

| KPI | Formula |
|---|---|
| Active Recruiters | `COUNT(DISTINCT company_id)` where a job's `status = 'Open'` |
| Companies Hiring | `COUNT(DISTINCT company_id)` with at least one placement |
| Average Hires per Company | `total_placements / companies_hiring` |
| Offer Conversion | `offers_made / applications_received * 100`, per company |
| Interview Conversion | `interviews_passed / interviews_conducted * 100`, per company |

## Student Metrics

| KPI | Formula |
|---|---|
| Applications per Student | `total_applications / students_who_applied` |
| Interview Success Rate | `students_interviewed / students_applied * 100` |
| Offer Success Rate | `students_offered / students_interviewed * 100` |
| Placement Success Rate | `students_placed / students_offered * 100` |

## Revenue Metrics

| KPI | Formula |
|---|---|
| Total Revenue | `SUM(amount)` over `revenue_events` |
| Revenue by College | `SUM(amount)` grouped by `related_type = 'college'` |
| Revenue by Company | `SUM(amount)` grouped by `related_type = 'company'` |
| Payment Success Rate | `COUNT(status='Success') / COUNT(*) * 100` over `payments` |

## Marketplace Health

| KPI | Formula |
|---|---|
| Jobs-to-Seekers Ratio | `open_jobs / students_still_seeking_placement` |
| Overall Conversion | `total_placements / total_applications * 100` |
| Conversion Funnel | Jobs Posted → Applications → Interviews → Offers → Placements |

All percentage-based KPIs guard against division by zero via
`utils.safe_divide`, returning `0.0` rather than raising when a
denominator is empty (e.g. a brand-new college with no students yet).
