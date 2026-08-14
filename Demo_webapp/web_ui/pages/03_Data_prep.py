import streamlit as st
import pandas as pd
import json
import requests
import os
from typing import Optional
from config import API_BASE_URL
from auth import require_login, get_auth_headers
from state import ensure_projects_store, create_project, reset_upload_form

# -------- Sequence validation limits -----------
# Applies to BOTH the uploaded file and pasted text, so the two input
# methods behave identically.
MAX_FASTA_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB
MAX_SEQUENCE_COUNT = 500                       # max FASTA records (">" entries) per submission

st.set_page_config(page_title="Upload Sample", layout="centered")

require_login()
ensure_projects_store()

# ------------ Helper function -----------------
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

def _format_size(num_bytes: int) -> str:
    """Human-readable byte size for error messages, e.g. 10485760 -> '10.0 MB'."""
    size = float(num_bytes)
    for unit in ('B', 'KB', 'MB', 'GB'):
        if unit == 'B':
            if size < 1024:
                return f"{int(size)} B"
        elif size < 1024 or unit == 'GB':
            return f"{size:.1f} {unit}"
        size /= 1024

# Standard 20 canonical amino acids + common IUPAC ambiguity codes:
# B=Asp/Asn, Z=Glu/Gln, X=any, J=Leu/Ile, U=selenocysteine, O=pyrrolysine.
_VALID_AA_CHARS = set("ACDEFGHIKLMNPQRSTVWYBZXJUO")

def validate_fasta_format(content: str) -> Optional[str]:
    """
    Structural + alphabet FASTA validation, run on content that's already
    been auto-wrapped with a header if it was a bare sequence (see process_fasta_txt()).
    """
    lines = [ln for ln in content.splitlines() if ln.strip() != '']
    if not lines:
        return 'No sequence data found.'

    def _check_sequence(record_num: int, header: str, seq_chars: str) -> Optional[str]:
        if not seq_chars:
            return f"Invalid FASTA format: record #{record_num} ('{header}') has no sequence data."
        bad_chars = sorted(set(seq_chars.upper()) - _VALID_AA_CHARS)
        if bad_chars:
            return (
                f"Record #{record_num} ('{header}') has invalid character(s) for a protein "
                f"sequence: {', '.join(bad_chars)}"
            )
        return None

    record_count = 0
    current_header = ''
    current_seq_chars = ''
    for line in lines:
        if line.startswith('>'):
            if record_count > 0:
                err = _check_sequence(record_count, current_header, current_seq_chars)
                if err:
                    return err
            record_count += 1
            current_header = line[1:].strip() or f'record {record_count}'
            current_seq_chars = ''
        else:
            current_seq_chars += line.strip()

    err = _check_sequence(record_count, current_header, current_seq_chars)
    if err:
        return err

    if record_count > MAX_SEQUENCE_COUNT:
        return (
            f"Too many sequences: this submission has {record_count} FASTA records, "
            f"but the maximum allowed is {MAX_SEQUENCE_COUNT}."
        )

    return None

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
                    "Select Bioactivities (Max 3) :red[*]",
                    options=all_bioactivities,
                    key='bioactivities',
                    max_selections=3)
    st.multiselect('ML applied to peptides with unknown bioactivity (Group 4) :red[*]',
                    options=['AMP','NP','ATHP'],
                    key='ml_models_id')
    st.divider()

    # -------- 1.3 In-silico Digestion Settings -----------
    st.markdown('*In-silico Digestion Settings*')
    col_enz, col_miss = st.columns(2)
    with col_enz:
        st.selectbox('select one enzyme for insilico digestion :red[*]', options=['Trypsin','Pepsin'],key='enzyme_id')
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
        raw_size_bytes = 0

        if file_input:
            raw_size_bytes = file_input.size
            fasta_content = file_input.getvalue().decode('utf-8', errors='ignore')
            fasta_name = file_input.name
        elif text_input:
            raw_size_bytes = len(text_input.encode('utf-8'))
            fasta_content = text_input

        if not fasta_content:
            st.error('Please provide either a valid FASTA file OR pasted text.')
            st.stop()

        # -------- Size check (uploaded file OR pasted text) ----------------------
        if raw_size_bytes > MAX_FASTA_FILE_SIZE_BYTES:
            st.error(
                f"⚠️ Your sequence data is {_format_size(raw_size_bytes)}, which is over the "
                f"{_format_size(MAX_FASTA_FILE_SIZE_BYTES)} limit. Please provide a smaller file."
            )
            st.stop()

        # -------- Auto-wrap a bare (headerless) sequence with a placeholder ------
        # -------- FASTA header -- same normalization for both input methods. -----
        fasta_content = process_fasta_txt(fasta_content)

        if not fasta_content:
            st.error('No sequence data found. Please check your file.')
            st.stop()

        # -------- Structural FASTA validation + sequence-count cap ---------------
        format_error = validate_fasta_format(fasta_content)
        if format_error:
            st.error(f'⚠️ {format_error}')
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

