"""Multi-project session-state helpers.

`st.session_state` is a single flat namespace per browser tab. Without this
layer, a user who submits project A and then goes back to Upload to start
project B overwrites 'job_id' / 'waiting_step' / 'api_payload' / etc.
outright — project A's tracking data is gone from the UI even though the
mock backend may still "have" that job. These helpers store each submitted
project under its own job_id inside st.session_state['projects'], and track
which one is currently being viewed via 'active_job_id', so a user can
submit project A, start project B, and switch back to check on A.
"""
import streamlit as st

# Draft fields used while filling out the Upload form (step 1) for a project
# that hasn't been submitted yet. These are cleared after a successful
# submission so the form starts blank the next time the page is visited,
# instead of showing the just-submitted project's leftover values/step.
UPLOAD_DRAFT_KEYS = [
    'project_name', 'sample_name', 'organism', 'description',
    'bioactivities', 'bioactivities_display', 'ml_models_id', 'enzyme_id', 'miss',
    'fasta_file', 'fasta_text', 'api_payload', 'display_file_name',
]


def ensure_projects_store() -> None:
    if 'projects' not in st.session_state:
        st.session_state['projects'] = {}
    if 'active_job_id' not in st.session_state:
        st.session_state['active_job_id'] = None


def create_project(job_id: str, api_payload: dict, bioactivities_display: list = None, job_uuid: str = None) -> None:
    """Register a newly submitted job as its own isolated project and make it active.

    `job_id` (the dict key here, and the `active_job_id` value) is the
    backend-assigned internal identifier -- used for project tracking in the
    UI (this store's key, the project switcher, "Job ID:" labels). It is
    kept separate from `job_uuid`, which every subsequent API call
    (status polling, results, notifications) actually addresses the job by.
    Storing `job_uuid` as a sibling field here means pages only ever look up
    the API identifier through the active project, never by (mis)using
    `job_id` as if it were the same thing.

    `bioactivities_display` is the human-readable bioactivity names shown in
    the UI (e.g. "ACE Inhibitory"). It's kept as a sibling field, separate
    from `api_payload`, because `api_payload` is exactly what gets POSTed to
    the backend (list_bioactivity_id only) — the display names never go over
    the wire.
    """
    ensure_projects_store()
    st.session_state['projects'][job_id] = {
        'job_uuid': job_uuid,
        'api_payload': api_payload,
        'bioactivities_display': bioactivities_display or [],
        'waiting_step': 1,
        'noti_email': '',
        'processing_complete': False,
        'list_step_total': [],
        'step_elapsed': [],
        'start_time': 0.0,
    }
    st.session_state['active_job_id'] = job_id


def get_active_project():
    """Returns (job_id, project_dict) for the currently active project, or (None, None)."""
    ensure_projects_store()
    job_id = st.session_state.get('active_job_id')
    if job_id is None or job_id not in st.session_state['projects']:
        return None, None
    return job_id, st.session_state['projects'][job_id]


def set_active_project(job_id: str) -> None:
    ensure_projects_store()
    if job_id in st.session_state['projects']:
        st.session_state['active_job_id'] = job_id


def reset_upload_form() -> None:
    """Clear the Upload page's draft fields so the form starts blank on the
    next visit, instead of re-showing the project that was just submitted."""
    for key in UPLOAD_DRAFT_KEYS:
        st.session_state.pop(key, None)
    st.session_state['upload_step'] = 1


def project_switcher(label: str = "Viewing project") -> None:
    """Renders a selectbox letting the user switch which submitted project
    they're looking at. No-ops (renders nothing) when there's 0-1 projects,
    so it's safe to call unconditionally from Job Status / Dashboard."""
    ensure_projects_store()
    projects = st.session_state['projects']
    if len(projects) <= 1:
        return
    job_ids = list(projects.keys())

    def _label(jid):
        name = projects[jid].get('api_payload', {}).get('project_name', jid)
        return f"{name}  ({jid})"

    current = st.session_state.get('active_job_id')
    idx = job_ids.index(current) if current in job_ids else 0
    chosen = st.selectbox(
        label, options=job_ids, index=idx, format_func=_label, key='project_switcher_select'
    )
    if chosen != current:
        set_active_project(chosen)
        st.rerun()
