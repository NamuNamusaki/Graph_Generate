import streamlit as st
import pandas as pd
import json
import requests

st.set_page_config(page_title="Upload Sample", layout="centered")

# Security Check =================================================================================
if not st.session_state.get('logged_in',False):
    st.warning('Please log in to view this page.')
    st.stop()

st.title("Data Upload Page")

# Upload File check =============================================================================
if 'upload_step' not in st.session_state:
    st.session_state['upload_step'] = 1

# Sample Information =============================================================================
if st.session_state['upload_step'] == 1:
    st.markdown("Please complete your sample details and upload your FASTA sequence below.")

    st.header('Sample Information')
    col1,col2 = st.columns(2)
    with col1:
        project_name = st.text_input("Project Name*",value=st.session_state.get('project_name',''))
        organism = st.text_input("Your Organism",value=st.session_state.get('organism',''))
        researcher_name = st.text_input("Researcher Name",value=st.session_state.get('researcher_name',''))
    with col2:
        sample_name = st.text_input("Sample Name*",value=st.session_state.get('sample_name',''))
        institute = st.text_input("Institute/lab Name",value=st.session_state.get('institute',''))
    st.divider()
    description = st.text_area("Description / Objective / Remark",value=st.session_state.get('description',''))
    st.divider()
    #Bioactivity Selection
    try:
        bioac_df = pd.read_csv('bioactivity.csv')
        all_bioactivities = bioac_df['Bioactivity'].tolist()
    except FileNotFoundError:
        all_bioactivities = ["ACE Inhibitory", "Antioxidant", "Antimicrobial", "Anti-inflammatory"]
    bioac_search = st.multiselect(
                    "Select Bioactivities (Max 3):*",
                    options=all_bioactivities,
                    default=st.session_state.get('bioac_search',[]),
                    max_selections=3)
    ml_pred = st.multiselect('ML applied to peptides with unknown bioactivity (Group 4)',
                            options=['AMP','NP','ATHP'],
                            default=st.session_state.get('ml_pred', []))
    
    st.markdown('**Insilico Digestion Settings**')
    col_enz, col_miss = st.columns(2)
    with col_enz:
        clevage_enz = st.selectbox('select one enzyme for insilico digestion', options=['Trypsin','Pepsin'])
    with col_miss:
        miss_cle = st.selectbox('Maximum missed cleavage sites allowed per peptide (Default: 4)',options=['0','1','2','3'],index=3)
    st.divider()

    st.header("Uploading Sequence")
    col_file, col_text = st.columns(2)
    with col_file:
        uploaded_files = st.file_uploader("Upload Your Sequence Here", type=['fasta','txt','fa'], accept_multiple_files=False)
    st.markdown("<br>", unsafe_allow_html=True)
    with col_text:
        raw_sequence = st.text_area("or Upload Your Sequence Here",height=200)
        sequence = raw_sequence.strip().replace('\n', '')
    
    if st.button('Review Submission',type='primary',use_container_width=True):
        if not project_name or not sample_name:
            st.error('Please fill in both the Project Name and Sample Name.')
        elif not ml_pred:
            st.error('Please select at least one ML prediction option.')
        elif not uploaded_files and not raw_sequence:
            st.error('Please upload FASTA file.')
        else:
            st.session_state['project_name'] = project_name
            st.session_state['sample_name'] = sample_name
            st.session_state['organism'] = organism
            st.session_state['research_name'] = researcher_name
            st.session_state['institute'] = institute
            st.session_state['description'] = description
            st.session_state['bioac_search'] = bioac_search
            st.session_state['ml_pred'] = ml_pred
            st.session_state['clevage_enz'] = clevage_enz
            st.session_state['miss_cle'] = miss_cle
            st.session_state['Interested_Bioactivity'] = [item.lower() for item in bioac_search] if bioac_search else []
            # Save the sample file
            st.session_state['uploaded_files'] = [uploaded_files] if uploaded_files else []
            st.session_state['filen_name'] = uploaded_files.name if uploaded_files else 'Pasted Sequence'
            st.session_state['raw_sequence'] = raw_sequence
            
            st.session_state['upload_step'] = 2
            st.rerun()
# Review Sample Information =======================================================================================
elif st.session_state['upload_step'] == 2:
    st.title('Review and Confirm Submission')
    st.markdown('Please recheck your input before submitting for analysis.')

    with st.container(border=True):
        st.header('Sample Information')
        summary_data ={
            'Project Name': st.session_state.get('project_name','-'),
            'Sample Name': st.session_state.get('sample_name','-'),
            'Organism': st.session_state.get('organism','-'),
            'Researcher Name': st.session_state.get('research_name','-'),
            'Institute': st.session_state.get('institute','-'),
            'Bioactivities': ', '.join(st.session_state.get('bioac_search',[])) if st.session_state.get('bioac_search') else 'None',
            'ML Prediction': ', '.join(st.session_state.get('ml_pred',[])) if st.session_state.get('ml_pred') else 'None',
            'Cleavage Enzyme': st.session_state.get('clevage_enz','-'),
            'Missed Cleavages': st.session_state.get('miss_cle','-'),
            'Uploaded File': st.session_state.get('filen_name','Error: No file')
        }
        for key,value in summary_data.items():
            st.markdown(f'**{key}:** {value}')
        
        st.markdown('**Description**')
        st.info(st.session_state.get('description','-'))
    
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
