import streamlit as st
import pandas as pd
import json
import requests
import os
from config import API_BASE_URL
from auth import require_login, get_auth_headers
from state import ensure_projects_store, create_project, reset_upload_form

st.set_page_config(page_title="Upload Sample", layout="centered")

require_login()
ensure_projects_store()

# Helper function
def format_bioac_name(name):
    """Title-cases a bioactivity name, replacing underscores with spaces."""
    if pd.isna(name):
        return name
    parts = str(name).replace('_', ' ').split(' ')
    formatted_parts = [p[0].upper() +p[1:] if len(p) >0 else p for p in parts]
    return ' '.join(formatted_parts)

def process_fasta_txt(raw_text:str) -> str:
    """Wraps bare sequences in a FASTA header if one is missing."""
    cleaned = raw_text.strip()
    if not cleaned:
        return ''
    if not cleaned.startswith('>'):
        cleaned = f'>Pasted_sequence_1\n{cleaned}'
    return cleaned

@st.cache_data
def load_bioactivity_map():
    """Reads the CSV and creates a Dictionary mapping Names to IDs."""
    try:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        root_dir    = os.path.dirname(current_dir)
        csv_path    = os.path.join(root_dir, 'bioactivity.csv')
        df = pd.read_csv(csv_path)
        df['Bioactivity'] = df['Bioactivity'].apply(format_bioac_name)
        return dict(zip(df['Bioactivity'], df['id']))
    except FileNotFoundError:
        st.error("⚠️ Database file 'bioactivity.csv' is missing! Please ensure it exists in the root directory.")
        return {}
    except pd.errors.EmptyDataError:
        st.error("⚠️ Database file 'bioactivity.csv' is empty.")
        return {}
    except KeyError as e:
        st.error(f"⚠️ 'bioactivity.csv' is missing an expected column: {e}")
        return {}

# ── Page header ───────────────────────────────────────────────────────────────
st.title("Uploading Page")
st.divider()

# ======== Upload File check =======================
if 'upload_step' not in st.session_state:
    st.session_state['upload_step'] = 1

# ══════════════════════════════════════════════════════════════════════════════
#  STEP 1 — Input form
# ══════════════════════════════════════════════════════════════════════════════
if st.session_state['upload_step'] == 1:
    st.markdown("Please complete your sample details and upload your FASTA sequence below.")
    # -------- 1.1 Sample Information -----------
    st.header('Sample Information')
    col1,col2 = st.columns(2)
    with col1:
        st.text_input("Project Name :red[*]",  key='project_name')
        st.text_input("Organism",       key='organism')
    with col2:
        st.text_input("Sample Name",   key='sample_name')
        st.text_area("Description",     key='description')
    st.divider()
    # -------- 1.2 Analysis Parameters -----------
    st.subheader("Analysis Parameters")
    name_to_id = load_bioactivity_map()
    if name_to_id:
        all_bioactivities = list(name_to_id.keys())
    else:
        fallback = ["ACE Inhibitory", "Antioxidant", "Antimicrobial", "Anti-inflammatory"]
        all_bioactivities = [format_bioac_name(name) for name in fallback]
    
    st.multiselect(
                    "Select Bioactivities (Max 3): :red[*]",
                    options=all_bioactivities,
                    key='bioactivities',
                    max_selections=3)
    st.multiselect('ML applied to peptides with unknown bioactivity (Group 4) red[*]',
                    options=['AMP','NP','ATHP'],
                    key='ml_models_id')
    st.divider()

    # -------- 1.3 In-silico Digestion Settings -----------
    st.markdown('*In-silico Digestion Settings*')
    col_enz, col_miss = st.columns(2)
    with col_enz:
        st.selectbox('select one enzyme for insilico digestion red[*]', options=['Trypsin','Pepsin'],key='enzyme_id')
    with col_miss:
        st.selectbox('Maximum missed cleavage sites allowed per peptide (Default: 4)',options=['0','1','2','3'],index=3,key='miss')
    st.divider()

    # -------- 1.4 Sequence Upload -----------
    st.header("Uploading Sequence")
    col_file, col_text = st.columns(2)
    with col_file:
        st.file_uploader("Upload Your Sequence Here", type=['fasta','txt','fa'], accept_multiple_files=False,key='fasta_file')
    st.markdown("<br>", unsafe_allow_html=True)
    with col_text:
        st.text_area("Or Upload Your Sequence Here",height=200,key='fasta_text')

    st.markdown("<br>", unsafe_allow_html=True)

    # ======== 1.5 Review Submission Button =======================
    if st.button('Review Submission',type='primary',use_container_width=True):
        if not st.session_state.get('project_name').strip():
            st.error('Please fill in the Project Name.')
            st.stop()
        if not st.session_state.get('sample_name'):
            st.error('Please fill in the Sample Name.')
            st.stop()
        if not st.session_state.get('bioactivities'):
            st.error('Please select at least one Bioactivity.')
            st.stop()
        if not st.session_state.get('enzyme_id'):
            st.error('Please select a Cleavage Enzyme.')
            st.stop()
        if not st.session_state.get('ml_models_id'):
            st.error('Please select at least one ML prediction.')
            st.stop()

        file_input = st.session_state.get('fasta_file')
        text_input = st.session_state.get('fasta_text', '').strip()

        if file_input and text_input:
            st.error('Please provide either a file OR pasted text, not both.')
            st.stop()
        fasta_content = ''
        fasta_name = 'Pasted_sequence.fasta'

        if file_input:
            fasta_content = file_input.getvalue().decode('utf-8',errors='ignore')
            fasta_name = file_input.name
        elif text_input:
            fasta_content = process_fasta_txt(text_input)

        if not fasta_content:
            st.error('Please provide either a valid FASTA file OR pasted text.')
            st.stop()

        selected_ids =[name_to_id[name] for name in st.session_state['bioactivities'] if name in name_to_id]

        # Construct the standardized JSON dictionary
        api_payload = {
            "project_name": st.session_state['project_name'].strip(),
            "sample_name":  st.session_state.get('sample_name', '').strip() or None,
            "organism":     st.session_state.get('organism', '').strip() or None,
            "description":  st.session_state.get('description', '').strip() or None,
            "list_bioactivities_id":   selected_ids,
            "ml_models_id":        st.session_state['ml_models_id'],
            "enzyme_id":           st.session_state['enzyme_id'],
            "miss":         int(st.session_state.get('miss')),
            "fasta_content":         fasta_content,
        }
        st.session_state['api_payload'] = api_payload
        # Bioactivity display names are frontend-only and never sent to the
        # backend, but they're snapshotted here (not just read later from the
        # 'bioactivities' widget key) because Streamlit clears a widget's
        # session_state entry once a rerun happens where that widget isn't
        # instantiated -- Step 2 never renders the multiselect again, so by
        # the time "Confirm and Process" triggers its own rerun, 'bioactivities'
        # would already be gone.
        st.session_state['bioactivities_display'] = list(st.session_state['bioactivities'])
        st.session_state['display_file_name'] = fasta_name
        st.session_state['upload_step'] = 2
        st.rerun()

# ══════════════════════════════════════════════════════════════════════════════
#  STEP 2 — Review & submit
# ══════════════════════════════════════════════════════════════════════════════
elif st.session_state['upload_step'] == 2:
    st.title('Review and Confirm Submission')
    st.markdown('Please recheck your input before submitting for analysis.')
    payload = st.session_state['api_payload']

    with st.container(border=True):
        st.markdown('**Sample Information**')
        st.markdown(f'**Project Name:** {payload["project_name"]}')
        st.markdown(f'**Sample Name:**  {payload["sample_name"] or "-"}')
        st.markdown(f'**Organism:**     {payload["organism"] or "-"}')
        st.divider()
        st.markdown('**Analysis Parameters**')
        # Bioactivity display names are frontend-only (never sent to the backend),
        # so they're read from the stable 'bioactivities_display' snapshot taken
        # in Step 1, not from api_payload (which only carries list_bioactivities_id)
        # and not from the 'bioactivities' widget key (which Streamlit clears
        # once this page stops rendering that widget).
        bioactivities_display = st.session_state.get('bioactivities_display', [])
        st.markdown(f'**Bioactivities:** {", ".join(bioactivities_display) if bioactivities_display else "-"}')
        st.markdown(f'**ML Predictions:** {", ".join(payload["ml_models_id"]) if payload["ml_models_id"] else "-"}')
        st.divider()
        st.markdown(f'**Insilico Digestion Settings**')
        st.markdown(f'**Cleavage Enzyme:**       {payload["enzyme_id"]}')
        st.markdown(f'**Missed Cleavage Sites:** {payload["miss"]}')
        st.markdown(f'**Sequence File:**         {st.session_state["display_file_name"]}')        
        st.markdown('**Description**')
        st.info(payload['description'] or '-')
    
    st.markdown('<br>',unsafe_allow_html=True)

    col_back,col2,col_submit = st.columns([1,1.5,3])
    with col_back:
        if st.button('Edit Detail'):
            st.session_state['upload_step'] = 1
            st.rerun()
    with col_submit:
        if st.button('Confirm and Process',type='primary'):
            with st.spinner('Sending data to Backend...'):
                # job_uuid is no longer generated here -- the backend now
                # generates it (see web_api/app.py's submit_analysis()) and
                # hands it back in the response below, the same way a real
                # database generates its own primary/unique key on INSERT
                # rather than accepting a client-picked one. So `payload`
                # goes out exactly as built in Step 1, with no job_uuid field
                # in it at all.

                # 2. Attach security token
                headers = get_auth_headers()
                # 3. Send Request
                api_url = f'{API_BASE_URL}/jobs'
                try:
                    response = requests.post(api_url, json=payload, headers=headers, timeout=10)
                    if response.status_code in [200, 201, 202]:
                        response_data = response.json()
                        new_job_id = response_data.get('job_id')
                        new_job_uuid = response_data.get('job_uuid')
                        if not new_job_id or not new_job_uuid:
                            st.error('Backend accepted the job but did not return a job_id/job_uuid for it.')
                            st.stop()
                        # Register this submission as its own tracked project
                        # (keyed by the backend-assigned job_id, an internal
                        # identifier distinct from job_uuid) instead of
                        # overwriting flat session_state keys, so an in-flight
                        # project isn't lost if the user comes back here to
                        # start another one. job_uuid is stored alongside it
                        # so later pages can address the API with the right
                        # identifier instead of job_id.
                        # Stored separately from api_payload since bioactivities_display
                        # is frontend-only and was never part of the POSTed payload.
                        create_project(
                            new_job_id, payload,
                            st.session_state.get('bioactivities_display', []),
                            job_uuid=new_job_uuid,
                        )
                        reset_upload_form()
                        st.switch_page('pages/04_Job_status.py')
                    else:
                        st.error(f'Backend Error {response.status_code}: {response.text}')
                except requests.exceptions.ConnectionError:
                    st.error("⚠️ Cannot reach the server. Is the backend running?")
                except requests.exceptions.Timeout:
                    st.error("⚠️ The server took too long to respond. Please try again.")
                except requests.exceptions.RequestException as e:
                    st.error(f'Connection Error: {e}')

