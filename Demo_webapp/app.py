import streamlit as st

st.set_page_config(page_title="SmartBioPep", layout="wide", initial_sidebar_state="collapsed")

if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
if 'username' not in st.session_state:
    st.session_state['username'] = None

home_page = st.Page('pages/01_Home.py',title='Home')
login_page = st.Page('pages/02_Login.py',title='Login')
upload_page = st.Page('pages/03_Upload.py',title='Upload')
waiting_page = st.Page('pages/04_Waiting.py',title='Jobstatus')
dashboard_page = st.Page('pages/05_Dashboard.py',title='Result Dashboard')

if st.session_state['logged_in']:
    nav_pages = [home_page,upload_page,waiting_page,dashboard_page]
else:
    nav_pages = [home_page,login_page]

pg = st.navigation(nav_pages,position='hidden')

st.markdown("""
<style>
    /* Hide default Streamlit chrome */
    [data-testid="stToolbar"] { display: none !important; }
    header[data-testid="stHeader"] [role="tablist"] { display: none !important; }
    /* --- Reset the default page padding so our navbar can bleed full width --- */
    .block-container {
        padding-top: 1rem !important;
        padding-left: 1.5rem !important;
        padding-right: 1.5rem !important;
        max-width: 100% !important;
    }
            
    /* The navbar container itself */
    .st-key-topnav {
        background-color: #3f3f3f;
        border-radius: 8px;
        padding: 10px 20px;
        margin-bottom: 20px;
        box-sizing: border-box;
    }
 
    /* Remove default column gaps/padding inside the navbar */
    .st-key-topnav div[data-testid="stHorizontalBlock"] {
        align-items: center;
        flex-wrap: nowrap; /*make the column fit with the content */
        gap: 0.4rem;
    }
            
    .st-key-topnav div[data-testid="stColumn"] {
        flex : 0 0 auto !important;
        width: auto !important;
        min-width: 0 !important;
    }
    .st-key-topnav .st-key-navspacer {
        flex: 1 1 auto !important;
    }
 
    /* Logo styling */
    .st-key-topnav .navbar-logo {
        color: #ffffff;
        font-weight: 700;
        font-size: 1rem;
        background-color: #2e2e2e;
        padding: 8px 14px;
        border-radius: 6px;
        white-space: nowrap;
        display: inline-block;
    }
 
    /* Nav links (st.page_link) */
    .st-key-topnav div[data-testid="stPageLink"] {
        background-color: #6b6b6b;
        border-radius: 6px;
        padding: 6px 16px;
        width: auto !important;
        whitespace: nowrap;
        text-align: center;
        transition: background-color 0.15s ease-in-out;
    }
    .st-key-topnav div[data-testid="stPageLink"]:hover {
        background-color: #808080;
    }
    .st-key-topnav div[data-testid="stPageLink"] p {
        color: #ffffff !important;
        font-weight: 500;
        margin: 0;
        white-space: nowrap;
    }
    .st-key-topnav div[data-testid="stPageLink"] svg {
        display: none; /* hide the little page icon for a cleaner pill look */
    }
 
    /* Logout button + username */
    .st-key-topnav .navbar-username {
        color: #ffffff;
        font-weight: 500;
        /*text-align: right;*/
        white-space: nowrap;
    }
    .st-key-topnav button[kind="secondary"] {
        background-color: #6b6b6b;
        color: #ffffff;
        border: none;
        border-radius: 6px;
        font-weight: 500;
        padding: 0.4rem 1rem;
        width: auto;
    }
    .st-key-topnav button[kind="secondary"]:hover {
        background-color: #808080;
        color: #ffffff;
        border: none;
    }
</style>    
""",unsafe_allow_html=True)

with st.container(key="topnav"):
    if st.session_state['logged_in']:
        # logo | Home | Upload | Jobstatus | Dashboard | space | username | Logout
        cols = st.columns(8)
 
        with cols[0]:
            st.markdown('<div class="navbar-logo"> SmartBioPep</div>', unsafe_allow_html=True)
        with cols[1]:
            st.page_link(home_page, label="Home")
        with cols[2]:
            st.page_link(upload_page, label="Upload")
        with cols[3]:
            st.page_link(waiting_page, label="Jobstatus")
        with cols[4]:
            st.page_link(dashboard_page, label="Result Dashboard")
        # cols[5] is an empty space that pushes the rest to the right
        with cols[5]:
            st.container(key="navspacer")
        with cols[6]:
            st.markdown(
                f'<div class="navbar-username">{st.session_state["username"]}</div>',
                unsafe_allow_html=True,
            )
        with cols[7]:
            if st.button("Logout", key="logout_btn"):
                st.session_state['logged_in'] = False
                st.session_state['username'] = None
                st.rerun()
 
    else:
        # logo | Home | spacer | Login
        cols = st.columns([4])
 
        with cols[0]:
            st.markdown('<div class="navbar-logo">SmartBioPep</div>', unsafe_allow_html=True)
        with cols[1]:
            st.page_link(home_page, label="Home")
        # cols[2] spacer
        with cols[2]:
            st.container(key="navspacer")
        with cols[3]:
            st.page_link(login_page, label="Login")

pg.run()