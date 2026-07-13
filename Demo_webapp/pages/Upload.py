import streamlit as st
st.set_page_config(page_title="Upload Sample", layout="wide")
st.markdown('Please upload your sequence')

# Security Check
if not st.session_state.get('logged_in',False):
    st.warning('Please log in to view this page.')
    st.stop()
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
miss_cle = st.selectbox('Maximum missed cleavage sites allowed per peptide (Default: 4)',option=['0','1','2','3'])

all_bioactivities = uploaded_files['Bioactivity'].tolist()
bioac_search = st.multiselect(
                        "Select Bioactivities:",
                    options=all_bioactivities,
                    default=[],
)

ml_pred = st.multiselect('Applied to peptides with unknown bioactivity (Group 4)')

if st.button('SUBMIT', type ='primary'):
    if uploaded_files:
        st.session_state['uploaded_files'] = uploaded_files
        st.success("Files uploaded successfully! {len(uploaded_files)} files! Redirecting...")
        st.switch_page('pages/Waiting.py')
    else:
        st.warning("Please upload at least one file.")