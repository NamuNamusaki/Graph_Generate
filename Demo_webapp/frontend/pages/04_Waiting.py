import streamlit as st
import time
import re
import requests

st.set_page_config(page_title="Job Status", layout="centered")

# SECURITY CHECKS
if not st.session_state.get('logged_in', False):
    st.warning("⚠️ Please log in to view this page.")
    st.stop()

if 'job_id' not in st.session_state:
    st.error("⚠️ No active analysis job found in memory.")
    st.info("Please return to the Upload page to submit a new sequence.")
    if st.button("Go to Upload Page", type="primary"):
        st.switch_page("pages/03_Upload.py")
    st.stop()
# Initialize session state variables safely    
if 'waiting_step' not in st.session_state:
    st.session_state['waiting_step'] = 1
if 'noti_email' not in st.session_state:
    st.session_state['noti_email'] = ''
if 'processing_complete' not in st.session_state:
    st.session_state['processing_complete'] = False
if 'list_step_total' not in st.session_state:
    st.session_state['list_step_total'] = [] # Corrected typo from 'list_stepm_total'
if 'step_elapsed' not in st.session_state:
    st.session_state['step_elapsed'] = []
if 'start_time' not in st.session_state:
    st.session_state['start_time'] = 0.0


job_uuid = st.session_state['job_id']
api_url = f"http://127.0.0.1:8000/api/status/{job_uuid}"
auth_headers = {"Authorization": f"Bearer {st.session_state.get('access_token', '')}"}

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
    bg,fg = colors.get(kind_key, colors['queue'])
    return (
        f'<span style="background:{bg}; color:{fg}; padding: 4px 12px;'
        f'border-radius:14px; font-size:0.85rem; font-weight:600; '
        f'display:inline-block;">{label}</span>'
    )

def render_job_status_table(step_current:int,list_step_total:list) -> str:
    rows_html = ""
    for i,step in enumerate(list_step_total):
        # Ensure step_elapsed is initialized and has enough elements
        if 'step_elapsed' not in st.session_state or len(st.session_state['step_elapsed']) != len(list_step_total):
            st.session_state['step_elapsed'] = [0.0] * len(list_step_total)

        elapsed = st.session_state['step_elapsed'][i]
        if i < step_current:
            status_html =status_badge('Completed','completed')
            time_text = format_hms(elapsed)
        elif i == step_current:
            status_html = status_badge('Running','running')
            time_text = format_hms(elapsed)
        else: # i > step_current (queued steps)
            status_html = status_badge('Queue','queue')
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

#=== Step 1 : Email Notification=====================
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
            ''', unsafe_allow_html=True,
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
            with st.spinner('Sending notification...'):
                try :
                    email_payload = {
                        'job_uuid': job_uuid,
                        'email': email.strip()
                    }
                    email_api_url = "http://127.0.0.1:8000/api/notifications/subscribe"
                    email_response = requests.post(email_api_url, json=email_payload)
                    if email_response.status_code == 200:
                        st.session_state['noti_email'] = email.strip()
                        st.session_state['waiting_step'] = 2
                        st.rerun()
                    else :
                        st.error(f'Backend failed to register email, Error {email_response.status_code}: {email_response.text}')
                except requests.exceptions.RequestException as e:
                    st.error(f'Connection Error: {e}')
                    
        if back_home_clicked:
            st.switch_page('pages/01_Home.py')

# ===== Step2 : Job Progress tracker(API Polling)======
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

                current_step = data.get('status','UNKNOWN').upper()
                step_current = data.get('step_current',0)
                api_steps = data.get('list_step_total',[])
                
                if not st.session_state['list_step_total'] and api_steps :
                    st.session_state['list_step_total'] = api_steps
                    # Initialize step_elapsed when list_step_total is first populated
                    st.session_state['step_elapsed'] = [0.0] * len(api_steps)
                    st.session_state['start_time'] = time.time() # Initialize start time

                total_steps = len(st.session_state['list_step_total'])


                if total_steps > 0:
                    if current_step == 'COMPLETED':
                        pct = 100
                    else :
                        pct = int((step_current / total_steps)*100)
                else:
                    pct = 0

                # Update elapsed time for the current step if it's still processing
                if step_current < total_steps: # Use step_current directly as it's the index of the running step
                    st.session_state['step_elapsed'][step_current] += 3 # Add the sleep duration
                # UI Updates
                progress_pct_placeholder.markdown(f"### {pct}%")
                progress_bar_placeholder.progress(pct)
                table_placeholder.markdown(
                    render_job_status_table(step_current,st.session_state['list_step_total']), unsafe_allow_html=True
                )
                if current_step == 'COMPLETED':
                    st.session_state['processing_complete'] = True
                    break
                elif current_step == 'FAILED':
                    error_placeholder.markdown(status_badge('● Failed', 'failed'), unsafe_allow_html=True)
                    error_msg = data.get("message", "An unknown error occurred on the server.")
                    error_placeholder.error(f"❌ **Analysis Failed:** {error_msg}")
                    if st.button("Return to Upload Page"):
                        del st.session_state['job_id']
                        st.switch_page("pages/03_Upload.py")
                    st.stop() # Halt the script
            except requests.exceptions.RequestException as e:
                st.error(f'Connection Error, Retrying... : {e}')
            time.sleep(3)
            error_placeholder.empty()
            
    # Complete 100%           
    if st.session_state['processing_complete']:
        status_placeholder.markdown(status_badge('● Completed','completed'),unsafe_allow_html=True)
        progress_pct_placeholder.markdown("### 100%")
        progress_bar_placeholder.progress(100)
        total_steps = len(st.session_state['list_step_total'])
        table_placeholder.markdown(
            render_job_status_table(total_steps,st.session_state['list_step_total']), unsafe_allow_html=True
        )
        st.success('Analysis Complete Your Data is Ready')
        if st.button('View your result',type='primary',use_container_width=True):
            st.switch_page('pages/05_Dashboard.py')
