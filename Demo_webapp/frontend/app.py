import streamlit as st

st.set_page_config(page_title="SmartBioPep", layout="wide", initial_sidebar_state="collapsed")

if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
if 'username' not in st.session_state:
    st.session_state['username'] = None

home_page = st.Page('pages/01_Home.py',title='Home')
login_page = st.Page('pages/02_Login.py',title='Login')
upload_page = st.Page('pages/03_Data_prep.py',title='Upload')
waiting_page = st.Page('pages/04_Job_status.py',title='Jobstatus')
dashboard_page = st.Page('pages/05_Dashboard.py',title='Result Dashboard')

if st.session_state['logged_in']:
    nav_pages = [home_page,upload_page,waiting_page,dashboard_page]
else:
    nav_pages = [home_page,login_page]

pg = st.navigation(nav_pages,position='hidden') # hides the default nav

st.markdown("""
<style>
/*====Global Config----------*/
:root {
    --nav-bg:        #142F14;
    --pill-bg:       rgba(255,255,255,0.12);  /*ฺButton to link to other page*/
    --pill-bg-hover: rgba(255,255,255,0.22);
    --pill-bg-active:#4CAF50;
    --pill-h:        2.1rem;
    --pill-radius:   6px;
    --nav-text:      #FFFDF9;
    --logo-bg:       rgba(0,0,0,0.35);
}
    /* Hide default Streamlit built-in toolba */
    [data-testid="stToolbar"]       { display: none !important; }
    [data-testid="stHeader"]        { display: none !important; }
    [data-testid="stDecoration"]    { display: none !important; }

    /* --- Reset the default page padding so our navbar can bleed full width --- */
    .block-container {
        padding-top:    0rem !important;
        padding-left:   2rem !important;
        padding-right:  2rem !important;
        width:          100% !important;
        max-width:      100% !important
    }
            
    /* The navbar container */
    .st-key-topnav {
        background-color: var(--nav-bg);
        border-radius: 8px;
        padding: 0.55rem 1.5rem;
        margin: 0 -2rem 1.5rem -2rem;
        box-shadow: 0 2px 10px rgba(0, 0, 0, 0.30);
        position: sticky;
        top: 0;
        z-index: 99999;
    }

.st-key-topnav > div[data-testid="stVerticalBlockBorderWrapper"],
.st-key-topnav > div[data-testid="stVerticalBlock"] {
    width: 100%;
}
  
    /* Remove default column gaps/padding inside the navbar */
    .st-key-topnav div[data-testid="stHorizontalBlock"] {
        display: flex !important;
        align-items: center;
        flex-wrap: nowrap; /*make the column fit with the content */
        gap: 0.4rem;
        width: 100% !important;
    }
            
    .st-key-topnav div[data-testid="stColumn"] {
        flex : 0 0 auto !important;
        width: auto !important;
        min-width: 0 !important;
        padding: 0 !important;
    }
    .st-key-topnav .st-key-navspacer {
        flex: 1 1 auto !important;
        width: auto !important;
    }
 
    /* Logo styling */
    .st-key-topnav .navbar-logo {
        color:  var(--nav-text);
        font-weight: 700;
        font-size: 1rem;
        background-color: var(--logo-bg);
        padding: 0 1rem;
        border-radius: var(--pill-radius);
        display: flex;
        align-items: center
        white-space: nowrap;
        height: var(--pill-h);
        display: flex;
        letter-spacing: 1px;
        user-select: none;    
    }
 
    /* Nav links (st.page_link) */
    .st-key-topnav div[data-testid="stPageLink"] {
        background-color: var(--pill-bg);
        border: none;
        border-radius: var(--pill-radius);
        height: var(--pill-h);
        display: flex !important;
        align-items: center !important;
        transition: background-color 0.15s ease;
        overflow: hidden;
    }
    .st-key-topnav div[data-testid="stPageLink"]:hover {
        background-color: var(--pill-bg-hover);

    }
    
    .st-key-topnav div[data-testid="stPageLink"] a {
        display: flex !important;
        align-items: center !important;
        padding: 0px 1rem !important;
        height: 100% !important;
        text-decoration: none !important;
        background:      transparent !important;
    }
            
    .st-key-topnav div[data-testid="stPageLink"] p {
        color: var(--nav-text) !important;
        font-weight: 500 !important;
        font-size: 0.9rem !important;
        margin: 0 !important;
        white-space: nowrap !important; 
    }
    .st-key-topnav div[data-testid="stPageLink"] svg {
        display: none !important; /* hide the little page icon for a cleaner pill look */
    }
    /*  username label */
        .navbar-username {
        color:       var(--nav-text);
        font-weight: 500;
        font-size:   0.9rem;
        white-space: nowrap;
        padding:     0 0.5rem;
        height:      var(--pill-h);
        display:     flex;
        align-items: center;
        opacity:     0.85;
    }
    /* Logout Button */
    .st-key-topnav button[kind="secondary"],
    .st-key-topnav button[kind="secondaryFormSubmit"] {
    background:    var(--pill-bg)   !important;
    color:         var(--nav-text)  !important;
    border:        none             !important;
    border-radius: var(--pill-radius) !important;
    font-weight:   500              !important;
    font-size:     0.9rem           !important;
    height:        var(--pill-h)    !important;
    padding:       0 1rem           !important;
    white-space:   nowrap           !important;
    transition:    background 0.15s ease !important;
    }
    .st-key-topnav button[kind="secondary"]:hover,
    .st-key-topnav button[kind="secondaryFormSubmit"]:hover {
        background: var(--pill-bg-hover) !important;
        color:      var(--nav-text)      !important;
        border:     none                 !important;
    }
</style>
""",unsafe_allow_html=True)

def render_navbar():
    with st.container(key="topnav"):
        if st.session_state['logged_in']:
            # logo | Home | Upload | Jobstatus | Dashboard | space | username | Logout
            cols = st.columns([1, 1, 1, 1, 1.6, 99, 1.5, 1])
    
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
            cols = st.columns([1,1,99,1])
    
            with cols[0]:
                st.markdown('<div class="navbar-logo">SmartBioPep</div>', unsafe_allow_html=True)
            with cols[1]:
                st.page_link(home_page, label="Home")
            # cols[2] spacer
            with cols[2]:
                st.container(key="navspacer")
            with cols[3]:
                st.page_link(login_page, label="Login")

render_navbar()
pg.run()