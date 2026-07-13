import streamlit as st
import pandas as pd
import json
import requests

st.set_page_config(page_title="Upload Sample", layout="wide")
st.markdown('Please upload your sequence')

# Security Check
if not st.session_state.get('logged_in',False):
    st.warning('Please log in to view this page.')
    st.stop()

st.title("Data Upload Page")

# Sample Information
project_name = st.text_input("Your Project Name")
sample_name = st.text_input("Your Sample Name")
organism = st.text_input("Your Organism")
research_name = st.text_input("Researcher Name")
institute = st.text_input("Institute/lab Name")
description = st.text_area("Description / Objective / Remark")
st.divider()

# Upload File check
if 'uploaded_files' not in st.session_state:
    st.session_state['uploaded_files'] = []

uploaded_files = st.file_uploader("Upload Your CSV files", type=['csv'], accept_multiple_files=True)
st.divider()

clevage_enz = st.selectbox('select one enzyme for insilico digestion', options=['Trypsin','Pepsin'])
miss_cle = st.selectbox('Maximum missed cleavage sites allowed per peptide (Default: 4)',options=['0','1','2','3'])

bioac_df = pd.read_csv('bioactivity.csv')
all_bioactivities = bioac_df['Bioactivity'].tolist()
bioac_search = st.multiselect(
                        "Select Bioactivities:",
                    options=all_bioactivities,
                    default=[],
)

ml_pred = st.multiselect('Applied to peptides with unknown bioactivity (Group 4)',options=['AMP','NP','ATHP'])

if st.button('SUBMIT', type ='primary'):
    if uploaded_files:
        st.session_state['uploaded_files'] = uploaded_files
        st.session_state['sample_description'] = description
        if bioac_search:
            cleaned_list = [item.lower() for item in bioac_search]
            st.session_state['Interested_Bioactivity'] = cleaned_list
        else:
            st.session_state['Interested_Bioactivity'] = []
        
    submission_load = {
        'username' : st.session_state.get('username'),
        'project_name': project_name,
        'sample_name': sample_name,
        'organism': organism,
        'research_name': research_name,
        'institute': institute,
        'description': description,
    }
    st.session_state['current_submission'] = submission_load
    json_payload = json.dump(submission_load)
    api_url = 'http://localhost:8501/api/saved_sample'
    headers = {'Content-Type': 'application/json'}

    try:
        response = requests.post(api_url, data=json_payload, headers=headers)
        if response.status_code != 200:
            st.toast("Warning: Could not save data to backend, but continuing analysis.")
    except requests.exceptions.RequestException as e:
        st.toast(f'backend connection Fail: {e}')
    
    st.session_state['processinf_complete'] = False
    st.switch_page['pages/Waiting.py']
else:
    st.error('Please Upload at least one file')

    '''if uploaded_files:
        st.session_state['uploaded_files'] = uploaded_files
        st.success("Files uploaded successfully! {len(uploaded_files)} files! Redirecting...")
        st.switch_page('pages/Waiting.py')
    else:
        st.warning("Please upload at least one file.")'''