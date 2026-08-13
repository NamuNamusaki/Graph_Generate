import streamlit as st

st.set_page_config(page_title="SmartBioPep", layout="wide", initial_sidebar_state="collapsed")

if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
if 'username' not in st.session_state:
    st.session_state['username'] = None

home_page      = st.Page('pages/01_Home.py',      title='Home')
login_page     = st.Page('pages/02_Login.py',      title='Login')
upload_page    = st.Page('pages/03_Data_prep.py',  title='Upload')
waiting_page   = st.Page('pages/04_Job_status.py', title='Jobstatus')
dashboard_page = st.Page('pages/05_Dashboard.py',  title='Result Dashboard')

nav_pages = [home_page, login_page, upload_page, waiting_page, dashboard_page]

pg = st.navigation(nav_pages, position='hidden')   # hides the default nav

st.markdown("""
<style>
/*----------Global Config----------*/
:root {
    --nav-bg:        #284928;
    --pill-bg:       rgba(255,255,255,0.12);
    --pill-bg-hover: rgba(255,255,255,0.22);
    --pill-bg-active:#6aca6df5;
    --pill-h:        2.1rem;
    --pill-radius:   6px;
    --nav-text:      #FFFDF9;
    --logo-bg:       rgba(0,0,0,0.35);
}
.st-key-topnav {
    --text-color:              var(--nav-text) !important;
    --body-text-color:         var(--nav-text) !important;
    --default-text-color:      var(--nav-text) !important;
}
.st-key-topnav *,
.st-key-topnav p,
.st-key-topnav span,
.st-key-topnav label,
.st-key-topnav div,
.st-key-topnav [data-testid="stMarkdownContainer"],
.st-key-topnav [data-testid="stMarkdownContainer"] p,
.st-key-topnav [data-testid="stMarkdownContainer"] span {
    color: #F0F4F0 !important;
    font-weight: 500 !important;
}
.stButton button,
.stButton button *,
.stButton button p,
.stButton button span {
    color: #FFFFFF !important;
    font-weight: 500 !important;
}

.navbar-username,
.navbar-username p,
.navbar-username span {
    color:       var(--nav-text) !important;
    font-weight: 500;
    font-size:   0.9rem;
    white-space: nowrap;
    padding:     0 0.5rem;
    height:      var(--pill-h);
    display:     flex;
    align-items: center;
    opacity:     0.85;
}
.stTextInput input,
.stTextArea textarea,
.stSelectbox [data-baseweb="select"] div,
.stMultiSelect [data-baseweb="select"] div {
    background-color: #F0F4F0 !important;
    color:            #1A1A1A !important;
    border-color:     #D9E8D9 !important;
}
[data-baseweb="input"],
[data-baseweb="textarea"],
[data-baseweb="base-input"] {
    background-color: #FFFFFF !important;
    color:            #1A1A1A !important;
}
/* Input container background (the outer wrapper div) */
.stTextInput > div[data-baseweb="form-control"],
.stTextInput > div > div,
.stTextArea  > div[data-baseweb="form-control"],
.stTextArea  > div > div {
    background-color: #FFFFFF !important;
}
/* Placeholder text colour */
.stTextInput input::placeholder,
.stTextArea textarea::placeholder {
    color: #9E9E9E !important;
    opacity: 1 !important;
}
/* Input focus border — use brand green */
.stTextInput input:focus,
.stTextArea textarea:focus {
    border-color:  #2E7D32 !important;
    box-shadow:    0 0 0 1px #2E7D32 !important;
    outline:       none !important;
}

/*-------Light Mode Page Colours----------*/

/* Main page background */
.stApp {
    background-color: #FFFFFF !important;
}

/* Secondary background areas */
[data-testid="stSidebar"],
[data-testid="stForm"] {
    background-color: #FFFFFF !important;
}

/* Page content text — scoped to .block-container so the
   navbar (which sits outside it) is never affected */
.block-container,
.block-container p,
.block-container label,
.block-container span {
    color: #1A1A1A !important;
}

/* Streamlit bordered container */
[data-testid="stVerticalBlockBorderWrapper"] {
    background-color: #FAFAFA !important;
    border-color:     #D9E8D9 !important;
}

/* Alert boxes */
[data-testid="stAlert"] {
    background-color: #F8FAF8 !important;
}

/* Dataframe table header */
[data-testid="stDataFrame"] thead {
    background-color: #E8F0E8 !important;
}

/* Primary (submit) buttons — brand green */
button[kind="primary"],
button[kind="primaryFormSubmit"] {
    background-color: #4d7e50 !important;
    color:            #FFFFFF !important;
    font-weight: 700 !important;
    border:           none    !important;
    border-radius:    var(--pill-radius) !important;
    transition:       background-color 0.15s ease !important;
}
button[kind="primary"]:hover,
button[kind="primaryFormSubmit"]:hover {
    background-color: #4d7e50 !important;
    color:            #FFFFFF !important;
    font-weight: 700 !important;
    border:           none    !important;
}

/* Multiselect selected-item pill */
[data-testid="stMultiSelect"] [data-baseweb="tag"] {
    background-color: #2E7D32 !important;
    color:            #FFFFFF !important;
}

/* Progress bar fill */
[data-testid="stProgressBar"] > div > div {
    background-color: #2E7D32 !important;
}

/*----------Hide Streamlit chrome----------*/
[data-testid="stToolbar"]    { display: none !important; }
[data-testid="stHeader"]     { display: none !important; }
[data-testid="stDecoration"] { display: none !important; }

/* Page padding reset */
.block-container {
    padding-top:   0rem !important;
    padding-left:  2rem !important;
    padding-right: 2rem !important;
    width:         100% !important;
    max-width:     100% !important;
}

/*----------Navbar Container----------*/
.st-key-topnav {
    background-color: var(--nav-bg);
    border-radius:    8px;
    padding:          0.55rem 1.5rem;
    margin:           0 -2rem 1.5rem -2rem;
    box-shadow:       0 2px 10px rgba(0,0,0,0.30);
    position:         sticky;
    top:              0;
    z-index:          99999;
}

.st-key-topnav > div[data-testid="stVerticalBlockBorderWrapper"],
.st-key-topnav > div[data-testid="stVerticalBlock"] {
    width: 100%;
}

.st-key-topnav div[data-testid="stHorizontalBlock"] {
    display:     flex !important;
    align-items: center !important;
    flex-wrap:   nowrap !important;
    gap:         0.4rem !important;
    width:       100% !important;
}

.st-key-topnav div[data-testid="stColumn"] {
    flex:            0 0 auto !important;
    width:           auto     !important;
    min-width:       0        !important;
    padding:         0        !important;
    display:         flex     !important;
    align-items:     center   !important;
    justify-content: center   !important;
}

.st-key-topnav .st-key-navspacer {
    flex:  1 1 auto !important;
    width: auto     !important;
}

/*----------Logo----------*/
.st-key-topnav .navbar-logo {
    color:            var(--nav-text) !important;
    font-weight:      700;
    font-size:        1rem;
    background-color: var(--logo-bg);
    padding:          0 1rem;
    border-radius:    var(--pill-radius);
    height:           var(--pill-h);
    display:          flex;
    align-items:      center;
    justify-content:  center;
    white-space:      nowrap;
    letter-spacing:   1px;
    user-select:      none;
    box-sizing:       border-box;
}

/*----------Nav pill links----------*/
.st-key-topnav div[data-testid="stPageLink"] {
    background-color: var(--pill-bg);
    border:           none;
    border-radius:    var(--pill-radius);
    height:           var(--pill-h);
    display:          flex !important;
    align-items:      center !important;
    transition:       background-color 0.15s ease;
    overflow:         hidden;
}
.st-key-topnav div[data-testid="stPageLink"]:hover {
    background-color: var(--pill-bg-hover);
}
.st-key-topnav div[data-testid="stPageLink"] a {
    display:         flex !important;
    align-items:     center !important;
    padding:         0 1rem !important;
    height:          100% !important;
    text-decoration: none !important;
    background:      transparent !important;
}
.st-key-topnav div[data-testid="stPageLink"] p {
    color:       var(--nav-text) !important;
    font-weight: 500 !important;
    font-size:   0.9rem !important;
    margin:      0 !important;
    white-space: nowrap !important;
}
.st-key-topnav div[data-testid="stPageLink"] svg {
    display: none !important;
}

/*----------Logout button----------*/
.st-key-topnav button[kind="secondary"],
.st-key-topnav button[kind="secondaryFormSubmit"] {
    background:    var(--pill-bg)     !important;
    color:         var(--nav-text)    !important;
    border:        none               !important;
    border-radius: var(--pill-radius) !important;
    font-weight:   500                !important;
    font-size:     0.9rem             !important;
    height:        var(--pill-h)      !important;
    padding:       0 1rem             !important;
    white-space:   nowrap             !important;
    transition:    background 0.15s ease !important;
}
.st-key-topnav button[kind="secondary"] *,
.st-key-topnav button[kind="secondaryFormSubmit"] * {
    color: var(--nav-text) !important;
}
.st-key-topnav button[kind="secondary"]:hover,
.st-key-topnav button[kind="secondaryFormSubmit"]:hover {
    background: var(--pill-bg-hover) !important;
    color:      var(--nav-text)      !important;
    border:     none                 !important;
}

</style>
""", unsafe_allow_html=True)


def render_navbar():
    with st.container(key="topnav"):
        if st.session_state['logged_in']:
            # logo | Home | Upload | Jobstatus | Dashboard | spacer | username | Logout
            cols = st.columns([1, 1, 1, 1, 1.6, 99, 1.5, 1])

            with cols[0]:
                st.markdown('<div class="navbar-logo">SmartBioPep</div>', unsafe_allow_html=True)
            with cols[1]:
                st.page_link(home_page,      label="Home")
            with cols[2]:
                st.page_link(upload_page,    label="Upload")
            with cols[3]:
                st.page_link(waiting_page,   label="Jobstatus")
            with cols[4]:
                st.page_link(dashboard_page, label="Result Dashboard")
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
                    st.session_state['username']  = None
                    st.rerun()

        else:
            # logo | Home | spacer | Login
            cols = st.columns([1, 1, 99, 1])

            with cols[0]:
                st.markdown('<div class="navbar-logo">SmartBioPep</div>', unsafe_allow_html=True)
            with cols[1]:
                st.page_link(home_page,  label="Home")
            with cols[2]:
                st.container(key="navspacer")
            with cols[3]:
                st.page_link(login_page, label="Login")


render_navbar()
pg.run()
