import streamlit as st

st.set_page_config(page_title="Home | Peptide Bioactivity", layout="centered")

if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False

with st.sidebar:
    if st.session_state["logged_in"]:
        st.success("Logged in as {}".format(st.session_state["username"]))
        if st.button("Logout", type="primary"):
            st.session_state["logged_in"] = False
            st.session_state["username"] = None
            st.rerun()
    else:
        st.warning('You are not Logging in')
        if st.button('Go to Login',type='primary',use_container_width=True):
            st.switch_page('pages/Login.py')
            

# Main Page Content
st.title('Welcome to SmartBioPep Version2.0 Web application')
st.markdown('''
This platform is designed to help you analyze and visualize peptide sequence bioactivities efficiently. 

**Features include:**
* **Automated Data Processing:** Quickly group and filter matching sequences.
* **Interactive Visualizations:** Explore your data through dynamic bar and pie charts.
* **ML Predictions:** (Coming Soon) Evaluate new sequences using trained models.

To get started, please proceed to the upload page to submit your CSV files.
''')

st.divider()

col1, col2, col3 = st.columns([1,2,1])
with col2:
    if st.button('Go to Upload',type='primary',use_container_width=True):
        if st.session_state['logged_in']:
            st.switch_page('pages/Upload.py')
        else:
            st.info('Please Login First')
            st.switch_page('pages/Login.py')