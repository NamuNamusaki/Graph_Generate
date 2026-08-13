import streamlit as st
import time
import re
import requests
from config import API_BASE_URL
from auth import require_login, get_auth_headers
from state import ensure_projects_store, get_active_project, project_switcher

st.set_page_config(page_title="Job Status", layout="centered")

require_login()
ensure_projects_store()

job_id, project = get_active_project()
if job_id is None:
    st.error("⚠️ No active analysis job found in memory.")
    st.info("Please return to the Upload page to submit a new sequence.")
    if st.button("Go to Upload Page", type="primary"):
        st.switch_page("pages/03_Data_prep.py")
    st.stop()

# Lets the user flip between concurrently submitted projects (renders
# nothing if there's only one project in this session).
project_switcher("Viewing project")

# Helper Function ============================
Email_patern = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

def validate_email(value: str) -> bool:
    return bool(value) and bool(Email_patern.match(value.strip()))

# To format the time from second to minute
def format_hms(second: int) -> str:
    second = int(second)
    hours, remainder = divmod(second, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f'{hours}:{minutes:02d}:{seconds:02d}'

# Job status
def status_badge(label: str, kind: str) -> str:
    colors = {
        'completed': ("#8DB080", "#ffffff"),
        'running': ("#6b95ea", "#ffffff"),
        'queue': ("#e9ecef", "#6c757d"),
        'failed': ("#dc3545", "#ffffff")
    }
    kind_key = kind.lower().strip()
    bg, fg = colors.get(kind_key, colors['queue'])
    return (
        f'<span style="background:{bg}; color:{fg}; padding: 4px 12px;'
        f'border-radius:14px; font-size:0.85rem; font-weight:600; '
        f'display:inline-block;">{label}</span>'
    )

def render_job_status_table(step_current: int, list_step_total: list, step_elapsed: list) -> str:
    rows_html = ""
    for i, step in enumerate(list_step_total):
        elapsed = step_elapsed[i] if i < len(step_elapsed) else 0.0
        if i < step_current:
            status_html = status_badge('Completed', 'completed')
            time_text = format_hms(elapsed)
        elif i == step_current:
            status_html = status_badge('Running', 'running')
            time_text = format_hms(elapsed)
        else:  # i > step_current (queued steps)
            status_html = status_badge('Queue', 'queue')
            time_text = '-'
        rows_html += f'''
        <tr style="border-top:1px solid #e5e7eb;">
            <td style="padding:10px 14px;">{i + 1} · {step}</td>
            <td>{status_html}</td>
            <td>{time_text}</td></tr>'''
    return f"""
    <div style="border:1px solid #e5e7eb; border-radius:10px; overflow:hidden;">
        <table style="width:100%; border-collapse:collapse; font-size:0.95rem;">
            <thead>
                <tr style="background:#f1f3f5; text-align:left; color:#6c757d;">
                    <th style="padding:10px 14px;">Pipeline Step</th>
                    <th style="padding:10px 14px;">Status</th>
                    <th style="padding:10px 14px;">Running time</th>
                </tr>
            </thead>
            <tbody>{rows_html}</tbody>
        </table>
    </div>
    """

#=== Step 1 : Email Notification=====================
# Create a routing for waiting page
# the first page is for confirm data uploaded succession the second page is the job status
if project['waiting_step'] == 1:
    # upload success -> confirm text +email input
    with st.container(border=True):
        st.markdown(
            '''
            <div style="text-align:center; padding: 8px 0 20px 0;">
                <div style="
                    width:70px; height:70px; border-radius:50%;
                    background:#6c757d; color:white;
                    display:flex; align-items:center; justify-content:center;
                    font-size:2rem; margin:0 auto 16px auto;">
                    ✓
                </div>
                <h2 style="margin-bottom:8px;">Analysis Submitted Successfully</h2>
                <p style="color:#6c757d; max-width:480px; margin:0 auto;">
                    Your request has been received and the analysis pipeline has started.
                    A notification will be sent to your email address.
                </p>
            </div>
            ''', unsafe_allow_html=True,
        )

    with st.container(border=True):
        col1, col2 = st.columns([1, 6])
        with col1:
            st.markdown(
                '<div style="width:48px; height:48px; background:#ced4da; border-radius:8px; display:flex; align-items:center; '
                'justify-content:center; font-size:1.4rem;">✉️</div>'
                , unsafe_allow_html=True
            )
        with col2:
            st.caption('Notification Email')
            email = st.text_input(
                'Notification Email',
                value=project['noti_email'],
                placeholder='research@university.ac.th',
                label_visibility='collapsed',
                key=f'noti_email_input_{job_id}')

    st.markdown(
            """
            <p style="color:#6c757d; text-align:center; font-size:0.9rem; margin-top:16px;">
                The email will include a link to track your job status in real time.<br>
                You will receive another notification once your results are ready.
            </p>
            """,
            unsafe_allow_html=True,
        )

    process_col, home_col = st.columns(2)
    with process_col:
        process_clicked = st.button('Track Your Job Status', type='primary', use_container_width=True, key=f'track_{job_id}')
    with home_col:
        back_home_clicked = st.button('Back to Home', type='primary', use_container_width=True, key=f'home_{job_id}')

    if process_clicked:
        if not validate_email(email):
            st.error("⚠️ Please enter a valid email address before continuing.")
        else:
            with st.spinner('Sending notification...'):
                try:
                    email_payload = {
                        'job_uuid': project['job_uuid'],
                        'email': email.strip()
                    }
                    email_api_url = f"{API_BASE_URL}/notifications"
                    email_response = requests.post(
                        email_api_url, json=email_payload, headers=get_auth_headers(), timeout=10
                    )
                    if email_response.status_code == 200:
                        project['noti_email'] = email.strip()
                        project['waiting_step'] = 2
                        st.rerun()
                    else:
                        st.error(f'Backend failed to register email, Error {email_response.status_code}: {email_response.text}')
                except requests.exceptions.ConnectionError:
                    st.error("⚠️ Cannot reach the server. Is the backend running?")
                except requests.exceptions.Timeout:
                    st.error("⚠️ The server took too long to respond. Please try again.")
                except requests.exceptions.RequestException as e:
                    st.error(f'Connection Error: {e}')

    if back_home_clicked:
        st.switch_page('pages/01_Home.py')

# ===== Step2 : Job Progress tracker (non-blocking, auto-refreshing) ======
elif project['waiting_step'] == 2:
    st.title('Job Status')
    st.markdown(f'**Job ID:** `{job_id}`')
    
    @st.fragment(run_every="3s")
    def poll_job_status(job_id=job_id):
        proj = st.session_state['projects'].get(job_id)
        if proj is None:
            return  # project was removed (e.g. from another tab/switch) — nothing to show

        if proj['processing_complete']:
            pct = 100
            step_current = len(proj['list_step_total'])
            status_html = status_badge('● Completed', 'completed')
        else:
            try:
                response = requests.get(f"{API_BASE_URL}/jobs/{proj['job_uuid']}", headers=get_auth_headers(), timeout=10)
                response.raise_for_status()
                data = response.json()

                current_status = data.get('status', 'UNKNOWN').upper()
                step_current = data.get('step_current', 0)
                api_steps = data.get('list_step_total', [])

                if not proj['list_step_total'] and api_steps:
                    proj['list_step_total'] = api_steps
                    proj['step_elapsed'] = [0.0] * len(api_steps)
                    proj['start_time'] = time.time()

                total_steps = len(proj['list_step_total'])
                if total_steps > 0 and step_current < total_steps:
                    proj['step_elapsed'][step_current] += 3  # matches the ~3s refresh cadence

                if current_status == 'COMPLETED' or (total_steps > 0 and step_current >= total_steps):
                    proj['processing_complete'] = True
                    proj['result_url'] = data.get('result_url')
                    pct = 100
                    status_html = status_badge('● Completed', 'completed')
                elif current_status == 'FAILED':
                    st.markdown(status_badge('● Failed', 'failed'), unsafe_allow_html=True)
                    error_msg = data.get("message", "An unknown error occurred on the server.")
                    st.error(f"❌ **Analysis Failed:** {error_msg}")
                    if st.button("Return to Upload Page", key=f'ret_failed_{job_id}'):
                        st.session_state['projects'].pop(job_id, None)
                        st.session_state['active_job_id'] = None
                        st.switch_page("pages/03_Data_prep.py")
                    return
                else:
                    pct = int((step_current / total_steps) * 100) if total_steps else 0
                    status_html = status_badge('● Running', 'running')
            except requests.exceptions.HTTPError:
                st.markdown(status_badge('● Failed', 'failed'), unsafe_allow_html=True)
                if response.status_code == 404:
                    st.error("❌ Job not found. It may have expired, or the backend was restarted.")
                else:
                    st.error(f"❌ Server error ({response.status_code}) while checking job status.")
                if st.button("Return to Upload Page", key=f'ret_404_{job_id}'):
                    st.session_state['projects'].pop(job_id, None)
                    st.session_state['active_job_id'] = None
                    st.switch_page("pages/03_Data_prep.py")
                return
            except requests.exceptions.RequestException as e:
                st.error(f'Connection Error, Retrying... : {e}')
                return

        status_placeholder_col, _ = st.columns([3, 2])
        status_placeholder_col.markdown(status_html, unsafe_allow_html=True)

        st.markdown('### Overall Progress')
        st.markdown(f"### {pct}%")
        st.progress(pct)

        st.markdown("#### Pipeline Steps")
        st.markdown(
            render_job_status_table(step_current, proj['list_step_total'], proj['step_elapsed']),
            unsafe_allow_html=True
        )

        if proj['processing_complete']:
            st.success('Analysis Complete — Your Data is Ready')
            result_url = proj.get('result_url')
            if result_url:
                # In a real deployment this link only ever arrives by email;
                # it's echoed here too since this demo has no real inbox to
                # check. Opening it (in this same browser, or after signing
                # back in) re-verifies login before showing any results.
                st.info(f"📧 We emailed a results link to **{proj['noti_email']}**: {result_url}")
            if st.button('View your result', type='primary', use_container_width=True, key=f'view_result_{job_id}'):
                st.switch_page('pages/05_Dashboard.py')

    poll_job_status()
