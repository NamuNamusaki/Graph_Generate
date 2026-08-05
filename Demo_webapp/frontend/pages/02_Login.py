import streamlit as st
import requests
import time
from config import API_URL
st.set_page_config(page_title="Login", layout="centered")

# ── Session-state defaults ────────────────────────────────────────────────────
if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False
if "username" not in st.session_state:
    st.session_state["username"] = None
# Security token get from API
if 'access_token' not in st.session_state:
    st.session_state['access_token'] = None

# ── Constants ─────────────────────────────────────────────────────────────────
LOGIN_URL = f"{API_URL}/login"
# ── Page guard: redirect already-logged-in users away ────────────────────────
if st.session_state["logged_in"]:
    st.switch_page("pages/01_Home.py")

# ──── UI ─────────────────────────────────────────────────────
st.title('User Login')
st.markdown("Please Enter your Username and Password to Using this tool")

# LOGIN FORM & API AUTHENTICATION
with st.form("login_form"):
    username_input = st.text_input("Username",key='login_username')
    password_input = st.text_input("Password", type="password", key='login_password')

    submitted_login = st.form_submit_button("Login", type="primary")
    # ── Client-side validation (fast, no network call needed) ─────────────
    if submitted_login:
        if not username_input.strip() or not password_input:
            st.error('Please Enter Both Username and Password.')
        else:
            with st.spinner('Authenticating...'):
                try:
                    response = requests.post(
                        LOGIN_URL,
                        data ={"username": username_input.strip(), "password": password_input}, timeout=10)

                    # ──── Granular HTTP error handling ───────────────────
                    if response.status_code == 200:
                        data = response.json()
                        token = data.get('access_token')
                        if not token:
                            st.error('Authentication failed: No token received, Please contact support')
                            st.stop()

                        # Save credentials and token to session state
                        st.session_state['logged_in'] = True
                        st.session_state['username'] = username_input.strip()
                        st.session_state['access_token'] = token
                        st.success('Login Successful Redirecting...')
                        st.switch_page('pages/01_Home.py')
                        
                    elif response.status_code == 401:                        
                        st.error('Incorrect username or password')
                    elif response.status_code == 422:
                        st.error('Invalid input format. Please check your username and password.')
                    elif response.status_code == 500:
                        st.error(f'Server error. ({response.status_code}).')
                    else:
                        st.error(f'Backend Error {response.status_code}: {response.text}')
                except requests.exceptions.ConnectionError:
                    st.error("⚠️ Cannot reach the server. Is the backend running on port 8000?")
                except requests.exceptions.Timeout:
                    st.error("⚠️ The server took too long to respond. Please try again.")
                except requests.exceptions.RequestException as e:
                    st.error(f'Connection Error: {e}')
