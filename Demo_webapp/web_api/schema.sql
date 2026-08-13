-- =============================================================================
-- SmartBioPep job-tracking database (MySQL 8.0+)
--
-- Mirrors the USERS / PROJECTS / JOBS ERD, with two deliberate corrections
-- to field types that would otherwise conflict with how the existing Python
-- code (web_api/app.py, frontend/state.py) actually uses these values:
--
--   1. jobs.job_uuid -- the ERD marks this `binary`. Every place in the app
--      that creates or reads a job_uuid treats it as a plain string:
--          job_uuid = str(uuid.uuid4())   # web_api/app.py, submit_analysis()
--      and it's sent as a URL query param (?job_uuid=...) and an HTTP path
--      segment (/jobs/{job_uuid}) -- both string contexts. Storing raw
--      BINARY(16) would require packing/unpacking on every read and write for
--      no benefit here, so this uses CHAR(36), the standard width for a
--      hyphenated UUID string.
--
--   2. jobs.output_result_path -- the ERD marks this `bigint`. The code
--      stores a filesystem path string here (e.g. the Result_Sequence/
--      directory), never a number:
--          job["output_result_path"] = _simulate_worker_output_path(job_uuid)
--      so this uses VARCHAR(500) instead.
--
-- Everything else follows the ERD's field list and nullability as drawn.
-- Two small, uncontroversial additions on top of the ERD: UNIQUE constraints
-- on users.username/email (a login system needs these to be unique even
-- though the diagram doesn't mark them so), and DEFAULT/ON UPDATE clauses on
-- the timestamp columns (required for them to populate themselves).
-- =============================================================================

CREATE DATABASE IF NOT EXISTS smartbiopep
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

USE smartbiopep;

-- -----------------------------------------------------------------------------
-- USERS
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS users (
    id              BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    username        VARCHAR(150)  NULL,
    email           VARCHAR(255)  NULL,
    password_hash   VARCHAR(255)  NULL,
    UNIQUE KEY uq_users_username (username),
    UNIQUE KEY uq_users_email (email)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- -----------------------------------------------------------------------------
-- PROJECTS  (many projects per user)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS projects (
    id              BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    user_id         BIGINT UNSIGNED NOT NULL,
    project_name    VARCHAR(255)  NULL,
    description     TEXT          NULL,
    created_at      TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP
                                   ON UPDATE CURRENT_TIMESTAMP,
    KEY idx_projects_user_id (user_id),
    CONSTRAINT fk_projects_user
        FOREIGN KEY (user_id) REFERENCES users (id)
        ON DELETE CASCADE
        ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- -----------------------------------------------------------------------------
-- JOBS  (many jobs per project)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS jobs (
    id                  BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,

    -- API-facing identifier (see header note above) -- every endpoint in
    -- web_api/app.py looks jobs up by this, not by `id`.
    job_uuid            CHAR(36)      NOT NULL,

    project_id          BIGINT UNSIGNED NOT NULL,

    status              ENUM('PENDING', 'RUNNING', 'SUCCESS', 'FAILED')
                                       NOT NULL DEFAULT 'PENDING',

    -- Path to the submitted FASTA file on disk (the app currently sends the
    -- raw sequence text over the wire; a real worker would write it to disk
    -- and this column would point at that file rather than storing the
    -- sequence text inline in the DB row).
    input_fasta_path    VARCHAR(500)  NULL,

    -- JSON array of bioactivity ids, e.g. "[1,4,7]" -- matches
    -- payload["list_bioactivities_id"] as sent by 03_Data_prep.py.
    list_bioactivity_id JSON          NULL,

    step_current        INT           NULL DEFAULT 0,

    -- JSON array of pipeline step names, e.g.
    -- ["Reading Data","In silico Digestion","Bioactivity Matching","Generating Results"]
    -- (mirrors web_api/app.py's PIPELINE_STEPS).
    list_step_total     JSON          NULL,

    error_message       TEXT          NULL,

    submitted_at        TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    started_at          TIMESTAMP     NULL,
    completed_at        TIMESTAMP     NULL,

    -- See header note above -- corrected from `bigint` to a path string.
    output_result_path  VARCHAR(500)  NULL,

    updated_by_worker    VARCHAR(255)  NULL,
    worker_name          VARCHAR(255)  NULL,

    UNIQUE KEY uq_jobs_job_uuid (job_uuid),
    KEY idx_jobs_project_id (project_id),
    CONSTRAINT fk_jobs_project
        FOREIGN KEY (project_id) REFERENCES projects (id)
        ON DELETE CASCADE
        ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
