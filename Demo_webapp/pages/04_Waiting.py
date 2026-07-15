import streamlit as st
import time

st.set_page_config(page_title="Waiting", layout="centered")



if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False
if "uploaded_files" not in st.session_state:
    st.session_state["uploaded_files"] = []
if "raw_sequence" not in st.session_state:
    st.session_state["raw_sequence"] = None
if "processing_complete" not in st.session_state:
    st.session_state["processing_complete"] = False

# ==========================================
# 2. SECURITY CHECKS
# ==========================================
if not st.session_state["logged_in"]:
    st.warning("⚠️ Please log in to view this page.")
    st.stop()

if not st.session_state["uploaded_files"] and not st.session_state["raw_sequence"]:
    st.warning("⚠️ No files detected for processing.")
    st.switch_page("pages/03_Upload.py")

st.title('Processing Data')
st.markdown('Data Submitted Successffully')

if 'processing_complete' not in st.session_state:
    st.session_state['processing_complete'] = False

if not st.session_state['processing_complete']:
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    for i in range(100):
        time.sleep(0.05)
        progress_bar.progress(i + 1)
        status_text.text(f"Analyzing {i + 1}% Complete")

    st.session_state['processing_complete'] = True
    status_text.empty()
    progress_bar.empty()

if st.session_state['processing_complete']:
    st.success('Analysis Complete Your Data is Ready')
    if st.button('View your result',type='primary',use_container_width=True):
        st.switch_page('pages/05_Dashboard.py')
