import streamlit as st
import pandas as pd
import json
import requests

st.set_page_config(page_title="Upload Sample", layout="centered")

# Security Check =================================================================================
if not st.session_state.get('logged_in',False):
    st.warning('Please log in to view this page.')
    st.stop()

# Helper function
def format_bioac_name(name):
    if pd.isna(name):
        return name
    parts = str(name).replace('_', ' ').split(' ')
    formatted_parts = [p[0].upper() +p[1:] if len(p) >0 else p for p in parts]
    return ' '.join(formatted_parts)

def process_fasta_txt(raw_text:str) -> str:
    cleaned = raw_text.strip()
    if not cleaned:
        return ''
    if not cleaned.startswith('>'):
        cleaned = f'>Pasted_sequence_1\n{cleaned}'
    return cleaned


st.title("Uploading Page")
st.divider()

# Upload File check =============================================================================
if 'upload_step' not in st.session_state:
    st.session_state['upload_step'] = 1

# Sample Information =============================================================================
if st.session_state['upload_step'] == 1:
    st.markdown("Please complete your sample details and upload your FASTA sequence below.")

    st.header('Sample Information')
    col1,col2 = st.columns(2)
    with col1:
        st.text_input("Project Name*",key='project_name')
        st.text_input("Organism",key='organism')
    with col2:
        st.text_input("Sample Name*",key='sample_name')
        st.text_area("Description",key='description')
    st.divider()
    #Bioactivity Selection
    try:
        bioac_df = pd.read_csv('bioactivity.csv')
        bioac_df['Bioactivity'] = bioac_df['Bioactivity'].apply(format_bioac_name)
        all_bioactivities = bioac_df['Bioactivity'].tolist()
    except FileNotFoundError:
        all_bioactivities = ["ACE Inhibitory", "Antioxidant", "Antimicrobial", "Anti-inflammatory"]

    st.multiselect(
                    "Select Bioactivities (Max 3):*",
                    options=all_bioactivities,
                    key='bioactivities',
                    max_selections=3)
    st.multiselect('ML applied to peptides with unknown bioactivity (Group 4)',
                    options=['AMP','NP','ATHP'],
                    key='ml_pred')
    st.divider()
    
    st.markdown('*Insilico Digestion Settings*')
    col_enz, col_miss = st.columns(2)
    with col_enz:
        st.selectbox('select one enzyme for insilico digestion', options=['Trypsin','Pepsin'],key='clevage_enz')
    with col_miss:
        st.selectbox('Maximum missed cleavage sites allowed per peptide (Default: 4)',options=['0','1','2','3'],index=3,key='miss_cle')
    st.divider()

    st.header("Uploading Sequence")
    col_file, col_text = st.columns(2)
    with col_file:
        st.file_uploader("Upload Your Sequence Here", type=['fasta','txt','fa'], accept_multiple_files=False,key='fasta_file')
    st.markdown("<br>", unsafe_allow_html=True)
    with col_text:
        st.text_area("Or Upload Your Sequence Here",height=200,key='fasta_text')

    # Form Submission
    if st.button('Review Submission',type='primary',use_container_width=True):
        if not st.session_state.project_name or not st.session_state.sample_name :
            st.error('Please fill in both the Project Name and Sample Name.')
            st.stop()
        elif not st.session_state.ml_pred:
            st.error('Please select at least one ML prediction option.')
            st.stop()

        fasta_content = ''
        file_name = 'Pasted_Sequence.fasta'

        file_input = st.session_state.get('fasta_file')
        text_input = st.session_state.get('fasta_text')

        if file_input and text_input:
            st.error('Please provide either a file OR pasted text, not both. Please deselect one and try again to continue.')
            st.stop()
        elif file_input:
            fasta_content = file_input.getvalue().decode('utf-8',errors='ignore')
            file_name = file_input.name
        elif text_input:
            fasta_content = process_fasta_txt(text_input)

        if not fasta_content:
            st.error('Please provide either a valid FASTA file OR pasted text.')
            st.stop()
            
        # API PAYLOAD STRUCTURE FOR FASTAPI
        # =======================================================================================
        # Note: Use this is Pydantic model structure for the FastAPI endpoint:
        #
        # class AnalysisJobPayload(BaseModel):
        #     project_name: str
        #     sample_name: str
        #     organism: str | None = None
        #     description: str | None = None
        #     bioactivities: list[str]
        #     ml_predictions: list[str]
        #     cleavage_enz: str
        #     missed_cleavages: int
        #     fasta_content: str
        # =======================================================================================

        # Construct the standardized JSON dictionary
        api_payload = {
            "project_name": st.session_state.project_name.strip(),
            "sample_name": st.session_state.sample_name.strip(),
            "organism": st.session_state.organism.strip() or None,
            "description": st.session_state.description.strip() or None,
            "bioactivities": st.session_state.bioactivities,
            "ml_predictions": st.session_state.ml_pred,
            "clevage_enz": st.session_state.clevage_enz,
            "miss_clevages": int(st.session_state.miss_cle),
            "fasta_content": fasta_content
        }
        st.session_state['api_payload'] = api_payload
        st.session_state['display_file_name'] = file_name 
        st.session_state['upload_step'] = 2
        st.rerun()

# Review Sample Information =======================================================================================
elif st.session_state['upload_step'] == 2:
    st.title('Review and Confirm Submission')
    st.markdown('Please recheck your input before submitting for analysis.')
    payload = st.session_state['api_payload']

    with st.container(border=True):
        st.markdown('**Sample Information**')
        st.markdown(f'**Project Name:** {payload["project_name"]}')
        st.markdown(f'**Sample Name:** {payload["sample_name"]}')
        st.markdown(f'**Organism:** {payload["organism"]}')
        st.markdown(f'**Bioactivities:** {", ".join(payload["bioactivities"])if payload["bioactivities"] else "-"}')
        st.markdown(f'**ML Predictions:** {", ".join(payload["ml_predictions"])if payload["ml_predictions"] else "-"}')
        st.markdown(f'**Insilico Digestion Settings**')
        st.markdown(f'**Cleavage Enzyme:** {payload["clevage_enz"]}')
        st.markdown(f'**Missed Cleavage Sites:** {payload["miss_clevages"]}')
        st.markdown(f'**Sequence File:** {st.session_state["display_file_name"]}')        
        st.markdown('**Description**')
        st.info(payload['description'] or '-')
    
    st.markdown('<br>',unsafe_allow_html=True)

    col1,col2,col3 = st.columns([1,1,3])
    with col1:
        if st.button('edit detail'):
            st.session_state['upload_step'] = 1
            st.rerun()
    with col2:
        if st.button('Confirm and Process',type='primary'):
            st.session_state['process_complete'] = False
            st.session_state['upload_step'] = 1
            st.switch_page('pages/04_Waiting.py')
