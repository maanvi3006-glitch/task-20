# PlaceMux Database Schema

`placemux.db` is a normalized SQLite database with 10 tables modeling the
full placement lifecycle: colleges onboard students, companies post jobs,
students apply, get interviewed, receive offers, get placed, and revenue
events are recorded against the resulting payments.

## Entity-Relationship Overview

```
colleges ──1:N── students ──1:N── applications ──N:1── jobs ──N:1── companies
                     │                  │
                     │                  └──1:N── interviews
                     │                  │
                     │                  └──1:1── offers ──1:1── placements
                     │                                             │
                     └─────────────────────1:N── placements ───────┘
                                                       │
colleges/companies ──1:N── payments ──1:N── revenue_events
```

## Tables

### `colleges`
| Column | Type | Notes |
|---|---|---|
| college_id | INTEGER PK | autoincrement |
| name | TEXT NOT NULL | |
| city | TEXT NOT NULL | |
| state | TEXT NOT NULL | |
| tier | TEXT NOT NULL | CHECK IN ('Tier-1','Tier-2','Tier-3') |
| established_year | INTEGER NOT NULL | |
| total_students | INTEGER | denormalized, back-filled from `students` |
| onboarded_date | TEXT NOT NULL | ISO date |

### `students`
| Column | Type | Notes |
|---|---|---|
| student_id | INTEGER PK | autoincrement |
| college_id | INTEGER FK -> colleges | ON DELETE CASCADE |
| name, gender, department, batch_year | | |
| cgpa | REAL | CHECK 0-10 |
| skills | TEXT | comma-separated |
| email | TEXT UNIQUE | |
| placement_status | TEXT | 'Not Placed' \| 'In Process' \| 'Placed' |

### `companies`
| Column | Type | Notes |
|---|---|---|
| company_id | INTEGER PK | autoincrement |
| name, industry, size_band, city, tier | | |
| registered_date | TEXT | |

### `jobs`
| Column | Type | Notes |
|---|---|---|
| job_id | INTEGER PK | |
| company_id | INTEGER FK -> companies | ON DELETE CASCADE |
| title, department, job_type | | |
| package_lpa | REAL | CHECK >= 0 |
| status | TEXT | 'Open' \| 'Closed' \| 'Filled' |

### `applications`
| Column | Type | Notes |
|---|---|---|
| application_id | INTEGER PK | |
| student_id | INTEGER FK -> students | |
| job_id | INTEGER FK -> jobs | |
| applied_date | TEXT | |
| status | TEXT | 'Applied' \| 'Interviewing' \| 'Offered' |

### `interviews`
| Column | Type | Notes |
|---|---|---|
| interview_id | INTEGER PK | |
| application_id | INTEGER FK -> applications | |
| round_number | INTEGER | 1-3 |
| result | TEXT | 'Pass' \| 'Fail' \| 'On Hold' |
| feedback_score | REAL | CHECK 0-10 |

### `offers`
| Column | Type | Notes |
|---|---|---|
| offer_id | INTEGER PK | |
| application_id | INTEGER FK -> applications | UNIQUE (one offer per application) |
| package_lpa | REAL | CHECK >= 0 |
| status | TEXT | 'Pending' \| 'Accepted' \| 'Declined' \| 'Expired' |

### `placements`
| Column | Type | Notes |
|---|---|---|
| placement_id | INTEGER PK | |
| offer_id | INTEGER FK -> offers | UNIQUE |
| student_id, college_id, company_id | INTEGER FKs | denormalized for fast reporting joins |
| joining_date | TEXT | |
| package_lpa | REAL | |
| status | TEXT | 'Confirmed' \| 'Joined' \| 'Deferred' \| 'Dropped' |

### `payments`
| Column | Type | Notes |
|---|---|---|
| payment_id | INTEGER PK | |
| college_id / company_id | INTEGER FKs (nullable) | ON DELETE SET NULL |
| amount | REAL | CHECK >= 0 |
| payment_type | TEXT | Placement Fee \| Subscription \| Job-Posting Fee \| Premium Listing |
| status | TEXT | Success \| Pending \| Failed \| Refunded |

### `revenue_events`
| Column | Type | Notes |
|---|---|---|
| event_id | INTEGER PK | |
| payment_id | INTEGER FK -> payments | |
| related_type | TEXT | 'college' \| 'company' |
| related_id | INTEGER | polymorphic reference to colleges/companies |
| amount | REAL | |
| category | TEXT | Placement Commission \| Subscription Revenue \| Listing Fee \| Premium Feature |

## Indexes

Indexes are created on every foreign key column plus the columns most
frequently filtered on in the dashboard (`placement_status`, `batch_year`,
`status` on applications/offers). See `create_database.py` -> `INDEX_STATEMENTS`
for the full list.

## Constraints

- All foreign keys enforce referential integrity via `PRAGMA foreign_keys = ON`.
- CHECK constraints guard salary ranges (`package_lpa >= 0`), CGPA (0-10),
  feedback scores (0-10), and enumerated status/tier fields.
- `students.email` and `offers.application_id` / `placements.offer_id` are
  UNIQUE to prevent duplicate accounts and duplicate offers/placements per
  application.
