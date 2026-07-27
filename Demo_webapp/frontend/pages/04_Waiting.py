import streamlit as st
import time
import re
import requests

st.set_page_config(page_title="Job Status", layout="centered")

# SECURITY CHECKS
if not st.session_state["logged_in"]:
    st.warning("⚠️ Please log in to view this page.")
    st.stop()

if 'job_id' not in st.session_state:
    st.error("⚠️ No active analysis job found in memory.")
    st.info("Please return to the Upload page to submit a new sequence.")
    if st.button("Go to Upload Page", type="primary"):
        st.switch_page("pages/03_Upload.py")
    st.stop()
if 'waiting_step' not in st.session_state:
    st.session_state['waiting_step'] = 1
if 'noti_email' not in st.session_state:
    st.session_state['noti_email'] = ''
if 'processing_complete' not in st.session_state:
    st.session_state['processing_complete'] = False

job_uuid = st.session_state['job_id']
api_url = f"http://127.0.0.1:8000/api/status/{job_uuid}"

# Helper Function ============================
Email_patern = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

def validate_email(value:str) -> bool:
    return bool(value) and bool(Email_patern.match(value.strip()))

# To format the time from second to minute
def format_hms(second:int) -> str:
    second = int(second)
    hours, remainder = divmod(second, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f'{hours}:{minutes:02d}:{seconds:02d}'

# Job status
def status_badge(label: str,kind:str) ->str:
    colors ={
        'completed': ("#8DB080", "#ffffff"),
        'running': ("#6b95ea", "#ffffff"),
        'queue' : ("#e9ecef", "#6c757d"),
        'failed' : ("#dc3545", "#ffffff")
    }
    kind_key = kind.lower().strip()
    bg,fg = colors.get(kind_key, colors['pending'])
    return (
        f'<span style="background:{bg}; color:{fg}; padding: 4px 12px;'
        f'border-radius:14px; font-size:0.85rem; font-weight:600; '
        f'display:inline-block;">{label}</span>'
    )

def render_job_status_table(current_step_index:int) -> str:
    rows_html = ""
    for i,step in enumerate(pipeline_step):
        elapsed = st.session_state['step_elapsed'][i]
        if i < current_step_index:
            status_html =status_badge('Completed','completed')
            time_text = format_hms(elapsed)
        elif i == current_step_index:
            status_html = status_badge('Running','running')
            time_text = format_hms(elapsed)
        else:
            status_html = status_badge('Pending','pending')
            time_text = '-'
        rows_html += f'''
        <tr style="border-top:1px solid #e5e7eb;">
            <td style="padding:10px 14px;">{i + 1} · {step['name']}</td>
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
# PIPELINE DEFINITION
pipeline_step = [
    {'name': 'Reading FASTA/Sequence'},
    {'name': 'In silico Digstion'},
    {'name': 'Peptide Generation'},
    {'name': 'Bioactivity Matching'},
    {'name': 'Result Preparation'}
]

if 'step_elapsed' not in st.session_state:
    st.session_state['step_elapsed'] = [0.0 for _ in pipeline_step]

# Create a routing for waiting page
# the first page is for confirm data uploaded succession the second page is the job status
if st.session_state['waiting_step'] == 1:
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
            ''',
            unsafe_allow_html=True,
        )
    
    with st.container(border=True):
        col1,col2 = st.columns([1,6])
        with col1:
            st.markdown(
                '<div style="width:48px; height:48px; background:#ced4da; border-radius:8px; display:flex; align-items:center; '
                'justify-content:center; font-size:1.4rem;">✉️</div>'
                ,unsafe_allow_html=True
            )
        with col2:
            st.caption('Notification Email')
            email =st.text_input(
                'Notification Email',
                value  = st.session_state['noti_email'],
                placeholder='research@university.ac.th',
                label_visibility='collapsed')

    st.markdown(
            """
            <p style="color:#6c757d; text-align:center; font-size:0.9rem; margin-top:16px;">
                The email will include a link to track your job status in real time.<br>
                You will receive another notification once your results are ready.
            </p>
            """,
            unsafe_allow_html=True,
        )

    process_col,home_col = st.columns(2)
    with process_col:
        process_clicked = st.button('Track Your Job Status',type='primary',use_container_width=True)
    with home_col:
        back_home_clicked = st.button('Back to Home',type='primary',use_container_width=True)

    if process_clicked:
        if not validate_email(email):
            st.error("⚠️ Please enter a valid email address before continuing.")
        else:
            st.session_state['noti_email'] = email.strip()
            # Send to backend using request.post()
            st.session_state['waiting_step'] = 2
            st.rerun()
        if back_home_clicked:
            st.switch_page('pages/01_Home.py')

# Step2 Job Progress tracker(APO Polling)      
elif st.session_state['waiting_step'] == 2:
    st.title('Job Status')
    st.markdown(f'**Job ID:** `{job_uuid}`')

    header_left, header_right = st.columns([3,2])
    status_placeholder = header_left.empty()
    results_placeholder = header_right.empty()

    st.markdown('### Overall Progress')
    progress_pct_placeholder = st.empty()
    progress_bar_placeholder = st.empty()

    st.markdown("#### Pipeline Steps")
    table_placeholder = st.empty()
    error_placeholder = st.empty()

    if not st.session_state['processing_complete']:
        status_placeholder.markdown(status_badge('● Running','running'),unsafe_allow_html=True)

        # API Polling Loop        
        while True:
            try:
                response = requests.get(api_url)
                response.raise_for_status()
                data = response.json()
                step_current = data.get('status','UNKNOWN').upper()
                pct = data.get('progress',0)
                current_step_index = data.get('step_current',0)
                # Update frontend Time
                if 0 <= current_step_index < len(pipeline_step) and step_current in ['RUNNING','QUEUE']:
                    st.session_state['step_elapsed'][current_step_index] += 3.0

                progress_pct_placeholder.markdown(f"### {pct:.0f}%")
                progress_bar_placeholder.progress(pct)
                table_placeholder.markdown(
                    render_job_status_table(current_step_index, st.session_state['step_elapsed']), unsafe_allow_html=True
                )
                if step_current == 'COMPLETED':
                    st.session_state['processing_complete'] = True
                    break
                elif step_current == 'FAILED':
                    status_placeholder.markdown(status_badge('● Failed', 'failed'), unsafe_allow_html=True)
                    error_msg = data.get("message", "An unknown error occurred on the server.")
                    error_placeholder.error(f"❌ **Analysis Failed:** {error_msg}")
                    if st.button("Return to Upload Page"):
                        del st.session_state['job_id']
                        st.switch_page("pages/03_Upload.py")
                    st.stop()
            except requests.exceptions.RequestException as e:
                error_placeholder.warning(f"⚠️ Connection interrupted. Retrying... (Details: {e})")
                time.sleep(5)
                error_placeholder.empty()
                    
    if st.session_state['processing_complete']:
        status_placeholder.markdown(status_badge('● Completed','completed'),unsafe_allow_html=True)
        results_placeholder.empty()
        progress_pct_placeholder.markdown("### 100%")
        progress_bar_placeholder.progress(100)
        table_placeholder.markdown(
            render_job_status_table(len(pipeline_step)), unsafe_allow_html=True
        )
        st.success('Analysis Complete Your Data is Ready')
        if st.button('View your result',type='primary',use_container_width=True):
            st.switch_page('pages/05_Dashboard.py')
