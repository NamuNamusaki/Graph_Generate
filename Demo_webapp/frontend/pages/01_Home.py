import streamlit as st

st.set_page_config(page_title="Home | Peptide Bioactivity", layout="centered")

# Main Page Content
st.title('Welcome to SmartBioPep Version2.0 Web application')
st.markdown('''
This platform is designed to help you analyze and visualize peptide sequence bioactivities efficiently. 

**Features include:**
* **Insilico Digestion:** Process your Data insilico Digestion.
* **Interactive Visualizations:** Explore your data through dynamic bar and pie charts.
* **ML Predictions:** (Coming Soon) Predict the Bioactivity group of the peptides using trained models.

To get started, please proceed to the upload page to submit your CSV files.
''')

st.divider()

col1, col2, col3 = st.columns([1,2,1])
with col2:
    if st.button('Go to Upload Protein Sequence',type='primary',use_container_width=True):
        if st.session_state['logged_in']:
            st.switch_page('pages/03_Data_prep.py')
        else:
            st.info('Please Login First')
            st.switch_page('pages/02_Login.py')