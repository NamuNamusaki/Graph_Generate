import streamlit as st
import pandas as pd
import json
import requests
import re
from datetime import datetime
import os
from config import API_URL

st.set_page_config(page_title="Upload Sample", layout="centered")

# Re direct to login if not logged in =========================================
if not st.session_state.get('logged_in',False):
    st.warning('Please log in to view this page.')
    st.switch_page('pages/02_Login.py')
    st.stop()


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
        st.text_input("Project Name*",  key='project_name')
        st.text_input("Organism",       key='organism')
    with col2:
        st.text_input("Sample Name*",   key='sample_name')
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
                    "Select Bioactivities (Max 3):*",
                    options=all_bioactivities,
                    key='bioactivities',
                    max_selections=3)
    st.multiselect('ML applied to peptides with unknown bioactivity (Group 4)',
                    options=['AMP','NP','ATHP'],
                    key='ml_pred')
    st.divider()

    # -------- 1.3 In-silico Digestion Settings -----------
    st.markdown('*In-silico Digestion Settings*')
    col_enz, col_miss = st.columns(2)
    with col_enz:
        st.selectbox('select one enzyme for insilico digestion', options=['Trypsin','Pepsin'],key='clevage_enz')
    with col_miss:
        st.selectbox('Maximum missed cleavage sites allowed per peptide (Default: 4)',options=['0','1','2','3'],index=3,key='miss_clevages')
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
        if not st.session_state.get('sample_name').strip():
            st.error('Please fill in the Sample Name.')
            st.stop()
        if not st.session_state.get('bioactivities'):
            st.error('Please select at least one Bioactivity.')
            st.stop()
        if not st.session_state.get('clevage_enz'):
            st.error('Please select a Cleavage Enzyme.')
            st.stop()
        if not st.session_state.get('ml_pred'):
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
            "sample_name":  st.session_state.get('sample_name', '').strip(),
            "organism":     st.session_state.get('organism', '').strip() or None,
            "description":  st.session_state.get('description', '').strip() or None,
            "list_bioactivity_id":   selected_ids,
            "bioactivities_display": st.session_state['bioactivities'],
            "ml_predictions":        st.session_state['ml_pred'],
            "clevage_enz":           st.session_state['clevage_enz'],
            "miss_clevages":         int(st.session_state.get('miss_clevages')),
            "fasta_content":         fasta_content,
            "input_fasta_path":      fasta_name
        }
        st.session_state['api_payload'] = api_payload
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
        st.markdown(f'**Sample Name:**  {payload["sample_name"]}')
        st.markdown(f'**Organism:**     {payload["organism"] or "-"}')
        st.divider()
        st.markdown('**Analysis Parameters**')
        st.markdown(f'**Bioactivities:** {", ".join(payload["bioactivities_display"]) if payload["bioactivities_display"] else "-"}')
        st.markdown(f'**ML Predictions:** {", ".join(payload["ml_predictions"]) if payload["ml_predictions"] else "-"}')
        st.divider()
        st.markdown(f'**Insilico Digestion Settings**')
        st.markdown(f'**Cleavage Enzyme:**       {payload["clevage_enz"]}')
        st.markdown(f'**Missed Cleavage Sites:** {payload["miss_clevages"]}')
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
                current_user    = st.session_state.get('username', 'user')
                project_name    = re.sub(r'\W+', ' ', payload['project_name'])
                submitted_at    = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                job_uuid        = f'{current_user}_{project_name}_{submitted_at}'
                payload['job_uuid'] = job_uuid

                # 2. Attach JWT security token
                headers = {
                    "Authorization": f"Bearer {st.session_state.get('access_token', '')}"
                }
                # 3. Send Request
                api_url = f'{API_URL}/jobs'
                response = requests.post(api_url, json=payload,headers=headers)
                
                if response.status_code in [200, 201, 202]:
                    # Keep the data
                    st.session_state['job_id'] = response.json().get('job_id',job_uuid)
                    st.session_state['processing_complete'] = False
                    st.session_state['waiting_step'] = 1
                    st.session_state['list_step_total'] = []
                    st.switch_page('pages/04_Job_status.py')
                else:
                    st.error(f'Backend Error {response.status_code}: {response.text}"')

                        
                    
