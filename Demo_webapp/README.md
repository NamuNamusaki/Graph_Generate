# SmartBioPep Version 2

A web application for analyzing and visualizing peptide sequence bioactivities. Users upload a FASTA sequence with analysis parameters, the backend runs an (in-silico digestion + bioactivity matching) pipeline, and the frontend renders the results as interactive charts, downloadable CSVs, HTML/PDF reports, and an ML-prediction preview.

This repo currently ships a **mock backend** (in-memory job store, no real prediction pipeline or worker yet) so the full frontend flow — login, submit, poll, view results, email link — can be developed and demoed end-to-end before the real pipeline exists.

## Architecture

```
 ┌─────────────┐        HTTP         ┌─────────────┐        SQL        ┌──────────┐
 │  frontend   │ ──────────────────▶ │     api     │ ─────────────────▶│    db    │
 │ (Streamlit) │ ◀────────────────── │  (FastAPI)  │ ◀──────────────── │ (MySQL)  │
 └─────────────┘                     └─────────────┘                    └──────────┘
                                             │
                                             │ (not wired up yet)
                                             ▼
                                       ┌───────────┐        ┌────────┐
                                       │   queue   │◀─────▶│ worker │
                                       │  (Redis)  │        │        │
                                       └───────────┘        └────────┘
```

- **frontend** — Streamlit multi-page app. Never talks to MySQL directly; only calls `api` over HTTP.
- **api** — FastAPI mock backend. Job state (status, progress, results path) is persisted to MySQL via `db.py`; only email-notification bookkeeping stays in an in-memory dict (see [Known gaps](#known-gaps-not-yet-built) for why).
- **db** — MySQL 8, schema for `users` / `projects` / `jobs`. Running via Docker and actively read/written by every job-related API call.
- **queue** / **worker** — Redis is running as a placeholder broker; no worker code exists yet. The real bioactivity-prediction pipeline would eventually run here instead of the mock's `Result_Sequence/` sample data.

## Project structure

```
Demo_webapp/
├── docker-compose.yml       # wires frontend + api + db + queue together
├── .env.example             # copy to .env, fill in real values
├── postman/                 # Postman collection to test the api
│
├── frontend/                 Streamlit UI
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── app.py                entry point: page registration, navbar, global CSS
│   ├── auth.py                login-gate + auth header helper
│   ├── config.py              API base URL (env-driven)
│   ├── state.py                multi-project session-state store
│   ├── bioactivity.csv         Bioactivity name -> id lookup table
│   └── pages/
│       ├── 01_Home.py
│       ├── 02_Login.py
│       ├── 03_Data_prep.py     (Upload)
│       ├── 04_Job_status.py    (Jobstatus)
│       └── 05_Dashboard.py     (Result Dashboard)
│
└── web_api/                  FastAPI mock backend
    ├── Dockerfile
    ├── requirements.txt
    ├── app.py                 all API routes + mock job store
    ├── db.py                  MySQL connection layer (standalone, not wired in yet)
    ├── schema.sql             users / projects / jobs tables
    └── Result_Sequence/       sample result data the mock "worker" points every job at
```

## Prerequisites

- Docker + Docker Compose (recommended way to run everything)
- Or, for running pieces individually: Python 3.11, `pip`

## Quick start (Docker Compose)

```bash
cp .env.example .env        # then edit .env with real passwords
docker compose up --build
```

| Service  | URL                       |
|----------|---------------------------|
| frontend | http://localhost:8501     |
| api      | http://localhost:8000/docs (FastAPI's interactive Swagger UI) |
| db       | localhost:3306 (MySQL Workbench/CLI) |

Demo login: **username** `admin`, **password** `password` (hardcoded in `web_api/app.py`, not a real user table yet).

## Running without Docker

```bash
# Terminal 1 — API
cd web_api
pip install -r requirements.txt
python app.py                       # http://127.0.0.1:8000

# Terminal 2 — Frontend
cd frontend
pip install -r requirements.txt
streamlit run app.py                # http://localhost:8501
```

## Environment variables

| Variable | Read by | Meaning |
|---|---|---|
| `SMARTBIOPEP_API_BASE_URL` | `frontend/config.py` | Where the frontend sends API requests. `http://api:8000` inside Docker Compose (service-name DNS), `http://127.0.0.1:8000` for local dev outside Docker. |
| `SMARTBIOPEP_APP_URL` | `web_api/app.py` | The browser-facing URL the mock backend puts into "your job is ready" emails. Must be an address the user's own browser can open — never a Docker service name. |
| `DB_HOST` / `DB_PORT` / `DB_USER` / `DB_PASSWORD` / `DB_NAME` | `web_api/db.py` | MySQL connection details. `DB_HOST=db` inside Compose. |
| `MYSQL_ROOT_PASSWORD` / `MYSQL_DATABASE` | the official `mysql` image | Initializes the `db` container on first boot. |

See `.env.example` for the full annotated list.

---

## Frontend — file by file

### `app.py` — entry point
Registers every page with `st.navigation()` (all pages registered unconditionally, even ones a logged-out user can't use yet — otherwise a logged-out visit to a protected page's URL, like an emailed results link, hits Streamlit's generic 404 before that page's own `require_login()` redirect ever runs). Injects the app's global CSS (navbar styling) and renders the top navbar.

- **`render_navbar()`** — draws the sticky top navbar. Logged-in view: logo, Home/Upload/Jobstatus/Dashboard links, username, Logout button. Logged-out view: logo, Home link, Login button only.

### `auth.py` — login gate
- **`require_login(redirect_to="pages/02_Login.py", *, next_page=None)`** — call at the top of any page that needs a logged-in session. If not logged in, redirects to Login, carrying `next` (the page to return to) and `job_uuid` (if the URL already had one, e.g. from an emailed results link) as query params — because `st.switch_page()` clears query params by default, anything that needs to survive the redirect has to be passed explicitly.
- **`get_auth_headers()`** — returns `{"Authorization": "Bearer <token>"}` built from `st.session_state['access_token']`, for attaching to every authenticated API call.

### `config.py` — API location
- `API_BASE_URL` — read from `SMARTBIOPEP_API_BASE_URL`, defaults to `http://127.0.0.1:8000`.
- `API_URL` — `API_BASE_URL + "/api"`. **Not currently used anywhere** — every page calls `API_BASE_URL` directly, since `web_api/app.py`'s routes don't have an `/api` prefix (e.g. `/login`, not `/api/login`). Kept here in case that changes later; safe to ignore for now.

### `state.py` — multi-project session state
`st.session_state` is one flat namespace per browser tab — without this layer, starting a second project would overwrite the first one's tracking data mid-session. These helpers store each submitted job under its own key in `st.session_state['projects']`.

- **`ensure_projects_store()`** — initializes `st.session_state['projects']` (dict) and `active_job_id` (None) if missing. Call at the top of every page that touches project state.
- **`create_project(job_id, api_payload, bioactivities_display=None, job_uuid=None)`** — registers a newly submitted job as its own tracked project and makes it active. Stores `job_uuid` (the identifier every API call actually uses) as a sibling field to `job_id` (the internal/UI-tracking identifier), and `bioactivities_display` (human-readable names, frontend-only) separately from `api_payload` (exactly what was POSTed).
- **`get_active_project()`** — returns `(job_id, project_dict)` for whichever project is currently being viewed, or `(None, None)`.
- **`set_active_project(job_id)`** — switches which project is "active" (what Job Status / Dashboard display).
- **`reset_upload_form()`** — clears the Upload page's draft fields after a successful submission, so the form is blank next visit instead of showing the just-submitted project.
- **`project_switcher(label="Viewing project")`** — renders a selectbox for switching between concurrently submitted projects. Renders nothing if there's 0–1 projects, so it's safe to call unconditionally.

### `pages/01_Home.py` — landing page
Static welcome/feature blurb. One button, "Go to Upload Protein Sequence" — sends logged-in users to Upload, logged-out users to Login first.

### `pages/02_Login.py` — login
Form posting `username`/`password` (form-encoded, not JSON) to `POST {API_BASE_URL}/login`. On success: stores `logged_in`, `username`, `access_token` in session state, then redirects to wherever the user was trying to go (`next` query param, defaulting to Home) — re-attaching `job_uuid` if one was present, so an emailed results link survives the login round-trip. Handles 401 (bad credentials), 422 (bad input), 500, and connection/timeout errors with distinct messages.

*Note:* the already-logged-in guard near the top (`if logged_in: switch_page(Home)`) doesn't carry `next`/`job_uuid` through — a minor inconsistency for the edge case of an already-logged-in user clicking a results link, not yet fixed.

### `pages/03_Data_prep.py` — Upload (2-step form)
- **`format_bioac_name(name)`** — title-cases a bioactivity name and replaces underscores with spaces (`"ACE_inhibitor"` → `"ACE Inhibitor"`).
- **`process_fasta_txt(raw_text)`** — wraps a bare pasted sequence in a FASTA header (`>Pasted_sequence_1`) if the user didn't paste one.
- **`load_bioactivity_map()`** *(cached)* — reads `bioactivity.csv`, returns a `{display_name: id}` dict used to populate the bioactivity multiselect and translate selections back to ids before sending to the API.

**Step 1** collects project name, sample name, organism, description, up to 3 bioactivities, ML models, enzyme, missed-cleavage count, and a FASTA file/pasted text (mutually exclusive). Client-side validation on "Review Submission" (required fields, file-or-text-not-both) before moving to Step 2.

**Step 2** shows a read-only summary. "Confirm and Process" POSTs the payload to `{API_BASE_URL}/jobs` with the bearer token; on success, registers the job via `create_project()` (using the `job_id`/`job_uuid` the *backend* generated and returned — the frontend no longer invents its own UUID) and moves to Job Status.

### `pages/04_Job_status.py` — post-submission tracking
- **`validate_email(value)`** — simple regex email check.
- **`format_hms(seconds)`** — formats elapsed seconds as `H:MM:SS`.
- **`status_badge(label, kind)`** — returns an HTML pill (`completed`/`running`/`queue`/`failed`, each its own color).
- **`render_job_status_table(step_current, list_step_total, step_elapsed)`** — builds the HTML table of pipeline steps with per-step status/elapsed time.

**Step 1**: collects a notification email, POSTs it to `{API_BASE_URL}/notifications`.
**Step 2**: `poll_job_status()`, wrapped in `@st.fragment(run_every="3s")` — reruns just this function on a timer instead of blocking the whole page (an earlier version used `while True: sleep(3)`, which froze the whole session). Polls `GET {API_BASE_URL}/jobs/{job_uuid}`, updates the progress bar/step table, and once `status == COMPLETED`, shows a "View your result" button to Dashboard plus the emailed results link (echoed here since this demo has no real inbox to check).

### `pages/05_Dashboard.py` — results
On load: if the URL has `?job_uuid=...` (an emailed results link) and that job isn't already tracked in this session, fetches it fresh from the backend and registers it via `create_project()`; if already tracked, just switches to it. Either way, the query param is consumed so it doesn't override the project switcher on later reruns.

- **`fetch_job_result(job_uuid)`** — the main data-fetching call for this page: `GET {API_BASE_URL}/jobs/{job_uuid}/result`, returns `{job_id, status, error_message, stat_files}` (statistics only, no peptide sequences). Deliberately **not** `@st.cache_data` — the same `job_uuid` legitimately returns different data over time as the job progresses, and caching bit the earlier implementation (a completed job kept showing "not ready" because the pre-completion response had been cached). Forces re-login on a 401.
- **`fetch_sequence_csv(job_uuid, group_name, bioactivity)`** — on-demand counterpart: `GET {API_BASE_URL}/jobs/{job_uuid}/download?group=...&bioactivity=...`, called only when the user clicks "Download CSV" for one specific bioactivity, not fetched eagerly for every row on page load. Returns raw CSV bytes, or `None` (rendered as a "No File" fallback).
- **`format_bioac_name(name)`** — same title-casing helper as Data_prep.
- **`get_group_names(file_name)`** — extracts `"Group 3a"` etc. from a result filename via regex.
- **`map_group_detail(group_name)`** — expands a group code to its meaning (`"Group 1"` → `"Exact Match"`, etc.).
- **`load_prep_data(df)`** — adds hover/percentage columns and returns `(sorted_df, total_peptides, formatted_total)` for charting.
- **`plot_bar(filter_df, formatted_total, top_n_option)`** / **`plot_pie(filtered_df, formatted_total)`** — build the interactive Plotly bar/pie charts for the Summary tab.
- **`summary_dashboard(group_dfs)`** — renders the Summary tab: chart-type selector, HTML/PDF report download buttons, one bar+pie chart pair per group, and the statistics table.
- **`build_summary_rows(group_dfs)`** — shared table builder (project parameters + per-group totals) reused by the on-screen table and both exported reports.
- **`create_sum_table(group_dfs)`** — renders the "Project Detail & Statistical Summary" table under the charts.
- **`generate_html_report(csv_paths)`** *(cached)* — builds a standalone, offline-viewable HTML report embedding interactive Plotly charts + the summary table.
- **`render_static_bar` / `render_static_pie`** — Matplotlib (non-interactive, image-based) versions of the same charts, for the PDF export.
- **`_pdf_scaled_image(png_buf, target_width)`** — scales a chart PNG to fit the PDF page width while preserving aspect ratio.
- **`generate_pdf_report(csv_paths)`** *(cached)* — builds a downloadable PDF report via ReportLab (summary table + one page per group with its bar/pie charts).
- **`render_group_tab(group_name, group_dfs)`** — renders one "Group N" tab: a ranked, paginated (10 → 20 → 50 rows) table of bioactivities with per-row CSV download for bioactivities the user originally selected, fetched on click via `fetch_sequence_csv()`. The "PARQUET Download" column is a placeholder — always renders `-`, not implemented.
- **`describe_bioactivity_model(code)`** — expands a short model code (`"NP"`) into a description (`"Neuropeptide model."`) via the `BIOACTIVITY_FULL_NAMES` lookup table.
- **`generate_mock_ml_predictions(model_key, n_rows)`** *(cached)* — placeholder ML-prediction row generator.
- **`render_ml_tab()`** — renders the "ML Prediction" tab. **Entirely mockup** — explicitly labeled as such on the page; replace once a real prediction worker exists.

Tabs rendered: Summary, Group 1, Group 2, Group 3a, Group 3b, ML Prediction.

---

## Backend (`web_api/`) — file by file

### `app.py` — FastAPI mock backend
Job state (status, progress, `output_result_path`, etc.) is persisted to MySQL via `db.py`. Email-notification bookkeeping (subscribed address, whether the completion email already fired) stays in an in-memory dict, `job_notifications`, since `schema.sql`'s `jobs` table has no columns for it — see [Known gaps](#known-gaps-not-yet-built).

- **`_format_job_id(db_id)`** — turns a job row's real MySQL auto-increment `id` into the `"JOB000001"`-style label the API has always returned.
- **`_get_or_create_demo_user()`** — looks up (or creates, on first use) a single seeded `"admin"` row in `users`, so `PROJECTS`/`JOBS` have a real `user_id` to satisfy their foreign keys. Stands in until `login()` actually authenticates against the `users` table instead of a hardcoded credential pair.
- **`_send_completion_email(email, job_uuid)`** — logs what a real email service would have sent (no SES/SendGrid wired up), returns the result URL (`{SMARTBIOPEP_APP_URL}/Dashboard?job_uuid=...`).
- **`_group_label_from_filename(stem)`** — `"RankBioactivity_G3a_2Enz"` → `"Group 3a"`.
- **`_group_label_from_result_dirname(dirname)`** — `"ResultG3a"` → `"Group 3a"`.
- **`_simulate_worker_output_path(job_uuid)`** — stands in for a real worker: every job "completes" pointing at the same shared `Result_Sequence/` sample directory rather than its own real output. The **mechanism** (job → its own `output_result_path` → its own files) is real; the data isn't.

**Endpoints** (all except `/login` require an `Authorization: Bearer <token>` header):

| Method & path | Purpose | Notes |
|---|---|---|
| `POST /login` | Authenticate | Form-encoded `username`/`password`. Only `admin`/`password` accepted — hardcoded, no user table used. |
| `POST /jobs` | Submit a new analysis job | Seeds/looks up the demo user, creates a `projects` row and a `jobs` row for it, and returns `job_id` (display label, derived from the job's real DB id) and `job_uuid` (the identifier every other call uses) — the client never invents either. |
| `POST /notifications` | Subscribe an email to a job | 404 if the `job_uuid` doesn't exist (checked via `db.get_job_by_uuid`). Stored in the in-memory `job_notifications` dict, not MySQL. |
| `GET /jobs/{job_uuid}` | Poll job progress | Reads/updates the job row in MySQL. Each call advances the mock pipeline one step (real progress would come from an actual worker). Fires the completion email exactly once, only if an email was subscribed. |
| `GET /jobs/{job_uuid}/result` | Fetch statistics for a job | Returns `stat_files` (per-group bioactivity counts) and `extra_params` (organism/enzyme_id/miss/sample_name as submitted), `stat_files` empty (`{}`) until the job reaches `COMPLETED`. Does **not** include peptide sequences — see `/download` below. |
| `GET /jobs/{job_uuid}/download` | Fetch one bioactivity's peptide sequences | Query params `group` (e.g. `"Group 1"`) and `bioactivity` (raw name, e.g. `"ACE_inhibitor"`). On-demand, one CSV at a time. 409 if the job isn't `COMPLETED` yet, 400 if the resolved path would escape the job's own result directory. |

### `db.py` — MySQL connection layer
Wired into `app.py`: `submit_analysis()` calls `create_project()`/`create_job()`, `get_status()` calls `get_job_by_uuid()`/`update_job_progress()`, and `get_job_result()`/`download_sequence_file()` both call `get_job_by_uuid()`. Job data now survives an `api` container restart — see [Known gaps](#known-gaps-not-yet-built) for what's still in-memory only.

- **`get_cursor(commit=False)`** — context manager yielding a dict-cursor from a pooled connection (`mysql.connector.pooling`, not one shared connection — FastAPI serves requests concurrently). Rolls back and re-raises on any exception; always returns the connection to the pool.
- **`create_user` / `get_user_by_username` / `get_user`** — USERS table CRUD. `create_user`/`get_user_by_username` back `_get_or_create_demo_user()` in `app.py`.
- **`create_project` / `get_project` / `list_projects_for_user`** — PROJECTS table CRUD. `create_project` is called once per job submission.
- **`create_job`** — inserts a new job row, called from `submit_analysis()`; a duplicate `job_uuid` raises a real `IntegrityError` (the in-memory dict this replaced could only silently overwrite). Also accepts `extra_params` (organism/enzyme_id/miss/sample_name), stored as one JSON blob since these have no dedicated columns.
- **`_decode_job_row(row)`** — decodes the JSON columns (`list_bioactivity_id`, `list_step_total`, `extra_params`) mysql-connector returns as strings, into Python lists/dicts.
- **`get_job_by_uuid` / `list_jobs_for_project`** — JOBS table reads. `get_job_by_uuid` is the lookup every job-related endpoint in `app.py` calls first.
- **`update_job_progress(job_uuid, ...)`** — updates only the fields actually passed in; called from `submit_analysis()` (flip a fresh job from `PENDING` to `RUNNING`) and `get_status()` (advance `step_current`/mark `COMPLETED`).
- **`init_schema()`** — applies `schema.sql` against the configured MySQL server (`python3 db.py --init-schema`); equivalent to `mysql -u ... -p ... < schema.sql`.

### `schema.sql` — database schema
Three InnoDB tables mirroring the project's ERD, with two deliberate corrections documented in the file header (`jobs.job_uuid`: `binary` → `CHAR(36)`, since the code treats it as a URL-safe string everywhere; `jobs.output_result_path`: `bigint` → `VARCHAR(500)`, since it stores a filesystem path).

- **`users`** — `id`, `username` (unique), `email` (unique), `password_hash`.
- **`projects`** — `id`, `user_id` (FK → users, cascade), `project_name`, `description`, timestamps.
- **`jobs`** — `id`, `job_uuid` (unique), `project_id` (FK → projects, cascade), `status` (`PENDING`/`RUNNING`/`COMPLETED`/`FAILED`), `input_fasta_path`, `list_bioactivity_id` (JSON), `extra_params` (JSON — organism/enzyme_id/miss/sample_name), `step_current`, `list_step_total` (JSON), `error_message`, `submitted_at`/`started_at`/`completed_at`, `output_result_path`, `updated_by_worker`, `worker_name`.

---

## Testing

A Postman collection covering every endpoint (with auto-chained auth token/job_uuid and a self-looping status-poll request) lives in `postman/`. See `postman/SmartBioPep.postman_collection.json` + `.postman_environment.json`. Matches the current API contract (no `/api` prefix, `GET /jobs/{job_uuid}` for status) — last verified with `newman run` against a live `web_api/app.py`: 24/24 assertions passing across login → submit → notify → poll-to-COMPLETED → fetch-result, plus 401/404 negative-path checks. **Note:** the collection's "05 - Get Consolidated Job Result" test script still asserts a `sequence_files` property the API no longer returns (that data now comes from the separate `GET /jobs/{job_uuid}/download` endpoint) — that one assertion is stale and will fail until updated.

Separately, `submit_analysis()`/`get_status()`/`get_job_result()`/`download_sequence_file()`'s DB-wiring logic (this file's `db.py` calls) was verified against a fake in-memory stand-in for `db.py` — same function signatures/return shapes, driven through the full login → submit → notify → poll-to-COMPLETED → result → download flow via FastAPI's `TestClient`, since no live MySQL server is available in every environment this gets checked out into. Real MySQL still needs `docker compose up` (or `python3 db.py --init-schema` against a local server) to actually exercise `schema.sql` itself.

## Known gaps (not yet built)

- **Single hardcoded demo user** — `_get_or_create_demo_user()` seeds/reuses one `"admin"` row so `PROJECTS`/`JOBS` have a real `user_id` to point at, since `login()` doesn't actually authenticate against the `users` table yet. Every submitted job (from anyone who logs in with the one hardcoded credential pair) is attached to this same user row — there's no real multi-user separation until login is wired to real accounts.
- **Email-notification bookkeeping isn't persisted** — `job_notifications` (subscribed address, whether the completion email fired) is an in-memory dict in `app.py`, not a MySQL table; `schema.sql`'s `jobs` table has no columns for it. A subscribed email is forgotten if the `api` container restarts mid-job, even though the job's own status/results now survive that restart.
- **No real worker or ML pipeline** — every job "completes" pointing at the same sample `Result_Sequence/` directory; `queue` (Redis) runs but nothing publishes or consumes from it yet.
- **ML Prediction tab is a full mockup** — random data generated client-side, explicitly labeled as such.
- **"PARQUET Download" column** on the Dashboard's group tabs is a placeholder (always renders `-`).
- **No real email service** — "sending" a completion email just logs what would have gone out.
- **Login is a single hardcoded credential pair** — no real user table/password hashing wired up, even though `schema.sql`/`db.py` already have what's needed for one.
