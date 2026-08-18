import streamlit as st
from pathlib import Path

st.set_page_config(page_title="SmartBioPep", layout="wide", initial_sidebar_state="collapsed")

# Resolved from this file's own location, not the process working directory,
# so the stylesheet is found whether Streamlit is launched from web_ui/, from
# the repo root, or from / inside the container.
CSS_PATH = Path(__file__).parent / "assets" / "style.css"


def load_css(path: Path = CSS_PATH) -> None:
    """Inject the app-wide stylesheet.

    Deliberately not @st.cache_data: the file is a few KB, so re-reading it
    on each rerun costs nothing measurable, and caching would mean edits to
    style.css don't show up until the cache is cleared.

    A missing stylesheet degrades to unstyled rather than crashing the whole
    app -- every page renders through this entry point, so raising here would
    take the entire UI down over a cosmetic asset.
    """
    try:
        css = path.read_text(encoding="utf-8")
    except OSError as e:
        st.warning(f"Could not load stylesheet ({path.name}): {e}")
        return
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)

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

load_css()


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
