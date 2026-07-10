import streamlit as st
st.set_page_config(page_title="Upload Sample", layout="wide")
st.markdown('Please upload your sequence')

# Security Check
if not st.session_state.get('logged_in',False):
    st.warning('Please log in to view this page.')
    st.stop()

# Upload File check
if 'uploaded_files' not in st.session_state:
    st.session_state['uploaded_files'] = []

uploaded_files = st.file_uploader("Upload Your CSV files", type=['csv'], accept_multiple_files=True)
st.divider()

if st.button('SUBMIT', type ='primary'):
    if uploaded_files:
        st.session_state['uploaded_files'] = uploaded_files
        st.success("Files uploaded successfully! {len(uploaded_files)} files! Redirecting...")
        st.switch_page('pages/Waiting.py')
    else:
        st.warning("Please upload at least one file.")