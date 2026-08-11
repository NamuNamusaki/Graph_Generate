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
- **api** — FastAPI mock backend. Currently keeps all job state in an in-memory dict (`mock_jobs_db`), not MySQL — `db.py`/`schema.sql` exist and work standalone, but aren't called from `app.py` yet.
- **db** — MySQL 8, schema for `users` / `projects` / `jobs`. Running via Docker, but currently idle (nothing writes to it — see [Known gaps](#known-gaps-not-yet-built)).
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
**Step 2**: `poll_job_status()`, wrapped in `@st.fragment(run_every="3s")` — reruns just this function on a timer instead of blocking the whole page (an earlier version used `while True: sleep(3)`, which froze the whole session). Polls `GET {API_BASE_URL}/status/{job_uuid}`, updates the progress bar/step table, and once `status == SUCCESS`, shows a "View your result" button to Dashboard plus the emailed results link (echoed here since this demo has no real inbox to check).

### `pages/05_Dashboard.py` — results
On load: if the URL has `?job_uuid=...` (an emailed results link) and that job isn't already tracked in this session, fetches it fresh from the backend and registers it via `create_project()`; if already tracked, just switches to it. Either way, the query param is consumed so it doesn't override the project switcher on later reruns.

- **`fetch_job_result(job_uuid)`** — the single data-fetching call for this whole page: `GET {API_BASE_URL}/jobs/{job_uuid}/result`, returns `{job_id, status, error_message, stat_files, sequence_files}`. Deliberately **not** `@st.cache_data` — the same `job_uuid` legitimately returns different data over time as the job progresses, and caching bit the earlier implementation (a completed job kept showing "not ready" because the pre-completion response had been cached). Forces re-login on a 401.
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
- **`render_group_tab(group_name, group_dfs)`** — renders one "Group N" tab: a ranked, paginated (10 → 20 → 50 rows) table of bioactivities with per-row CSV download for bioactivities the user originally selected (matched against `sequence_files` returned by the API). The "PARQUET Download" column is a placeholder — always renders `-`, not implemented.
- **`describe_bioactivity_model(code)`** — expands a short model code (`"NP"`) into a description (`"Neuropeptide model."`) via the `BIOACTIVITY_FULL_NAMES` lookup table.
- **`generate_mock_ml_predictions(model_key, n_rows)`** *(cached)* — placeholder ML-prediction row generator.
- **`render_ml_tab()`** — renders the "ML Prediction" tab. **Entirely mockup** — explicitly labeled as such on the page; replace once a real prediction worker exists.

Tabs rendered: Summary, Group 1, Group 2, Group 3a, Group 3b, ML Prediction.

---

## Backend (`web_api/`) — file by file

### `app.py` — FastAPI mock backend
All job state lives in `mock_jobs_db` (plain dict, keyed by `job_uuid`, wiped on every restart) — see [Known gaps](#known-gaps-not-yet-built) for what real persistence would need.

- **`_next_job_id()`** — stands in for a real DB auto-increment primary key (`JOB000001`, `JOB000002`, ...).
- **`_send_completion_email(email, job_uuid)`** — logs what a real email service would have sent (no SES/SendGrid wired up), returns the result URL (`{SMARTBIOPEP_APP_URL}/Dashboard?job_uuid=...`).
- **`_group_label_from_filename(stem)`** — `"RankBioactivity_G3a_2Enz"` → `"Group 3a"`.
- **`_group_label_from_result_dirname(dirname)`** — `"ResultG3a"` → `"Group 3a"`.
- **`_simulate_worker_output_path(job_uuid)`** — stands in for a real worker: every job "completes" pointing at the same shared `Result_Sequence/` sample directory rather than its own real output. The **mechanism** (job → its own `output_result_path` → its own files) is real; the data isn't.

**Endpoints** (all except `/login` require an `Authorization: Bearer <token>` header):

| Method & path | Purpose | Notes |
|---|---|---|
| `POST /login` | Authenticate | Form-encoded `username`/`password`. Only `admin`/`password` accepted — hardcoded, no user table used. |
| `POST /jobs` | Submit a new analysis job | Backend generates and returns both `job_id` (internal tracking) and `job_uuid` (the identifier every other call uses) — the client never invents these. |
| `POST /notifications` | Subscribe an email to a job | 404 if the `job_uuid` doesn't exist. |
| `GET /status/{job_uuid}` | Poll job progress | Each call advances the mock pipeline one step (real progress would come from an actual worker). Fires the completion email exactly once, only if an email was subscribed. |
| `GET /jobs/{job_uuid}/result` | Fetch all results for a job in one call | Returns `stat_files` (per-group bioactivity counts) and `sequence_files` (per-group, per-bioactivity peptide sequences), both empty (`{}`) until the job reaches `SUCCESS`. Replaces what used to be two separate summary/download endpoints. |

### `db.py` — MySQL connection layer
**Not called from `app.py` yet** — this is a complete, working, standalone module ready to swap in for `mock_jobs_db` once you're ready (see [Known gaps](#known-gaps-not-yet-built)).

- **`get_cursor(commit=False)`** — context manager yielding a dict-cursor from a pooled connection (`mysql.connector.pooling`, not one shared connection — FastAPI serves requests concurrently). Rolls back and re-raises on any exception; always returns the connection to the pool.
- **`create_user` / `get_user_by_username` / `get_user`** — USERS table CRUD.
- **`create_project` / `get_project` / `list_projects_for_user`** — PROJECTS table CRUD.
- **`create_job`** — inserts a new job row; equivalent to `mock_jobs_db[job_uuid] = {...}`, except a duplicate `job_uuid` raises a real `IntegrityError` instead of silently overwriting.
- **`_decode_job_row(row)`** — decodes the JSON columns (`list_bioactivity_id`, `list_step_total`) mysql-connector returns as strings, into Python lists.
- **`get_job_by_uuid` / `list_jobs_for_project`** — JOBS table reads.
- **`update_job_progress(job_uuid, ...)`** — updates only the fields actually passed in; collapses the handful of `job["..."] = ...` lines `app.py`'s `get_status()` currently does in-memory into one call.
- **`init_schema()`** — applies `schema.sql` against the configured MySQL server (`python3 db.py --init-schema`); equivalent to `mysql -u ... -p ... < schema.sql`.

### `schema.sql` — database schema
Three InnoDB tables mirroring the project's ERD, with two deliberate corrections documented in the file header (`jobs.job_uuid`: `binary` → `CHAR(36)`, since the code treats it as a URL-safe string everywhere; `jobs.output_result_path`: `bigint` → `VARCHAR(500)`, since it stores a filesystem path).

- **`users`** — `id`, `username` (unique), `email` (unique), `password_hash`.
- **`projects`** — `id`, `user_id` (FK → users, cascade), `project_name`, `description`, timestamps.
- **`jobs`** — `id`, `job_uuid` (unique), `project_id` (FK → projects, cascade), `status` (`PENDING`/`RUNNING`/`SUCCESS`/`FAILED`), `input_fasta_path`, `list_bioactivity_id` (JSON), `step_current`, `list_step_total` (JSON), `error_message`, `submitted_at`/`started_at`/`completed_at`, `output_result_path`, `updated_by_worker`, `worker_name`.

---

## Testing

A Postman collection covering every endpoint (with auto-chained auth token/job_uuid and a self-looping status-poll request) lives in `postman/`. See `postman/SmartBioPep.postman_collection.json` + `.postman_environment.json`.

> **Heads up:** that collection was built against an earlier version of the API (`/api/login`, `/api/results/{job_uuid}/summary`, `/api/results/{job_uuid}/download`). The API has since dropped the `/api` prefix and consolidated results into `GET /jobs/{job_uuid}/result` (see the endpoint table above) — the collection needs a matching update before it'll pass again.

## Known gaps (not yet built)

- **`db.py` isn't wired into `app.py`** — `db`/MySQL run in Docker Compose but sit idle; job state still lives in the in-memory `mock_jobs_db` dict and is lost on every restart.
- **No real worker or ML pipeline** — every job "completes" pointing at the same sample `Result_Sequence/` directory; `queue` (Redis) runs but nothing publishes or consumes from it yet.
- **ML Prediction tab is a full mockup** — random data generated client-side, explicitly labeled as such.
- **"PARQUET Download" column** on the Dashboard's group tabs is a placeholder (always renders `-`).
- **No real email service** — "sending" a completion email just logs what would have gone out.
- **Login is a single hardcoded credential pair** — no real user table/password hashing wired up, even though `schema.sql`/`db.py` already have what's needed for one.
