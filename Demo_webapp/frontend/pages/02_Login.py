import streamlit as st
import requests
import time
st.set_page_config(page_title="Login", layout="centered")

if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False
if "username" not in st.session_state:
    st.session_state["username"] = None
# Security token get from API
if 'access_token' not in st.session_state:
    st.session_state['access_token'] = None


st.title('User Login')
st.markdown("Please Enter your Username and Password to Using this tool")

with st.form("login_form"):
    st.text_input("Username",key='login_username')
    st.text_input("Password", type="password", key='login_password')

    submitted_login = st.form_submit_button("Login", type="primary")

    if submitted_login:
        username_input = st.session_state,login_username.strip()
        password_input = st.session_state.login_password

        if not username_input or password_input:
            st.error('Please Enter Both Username and Password.')
        else:
            with st.spinner('Authenticating...'):
                try:
                    api_url = "http://127.0.0.1:8000/api/login"
                    login_payload = {"username": username_input, "password": password_input}

                    response = requests.post(api_url, json=login_payload)

                    if response.status_code == 200:
                        data = response.json()
                        # Save credentials and token to session state
                        st.session_state['logged_in'] = True
                        st.session_state['username'] = username_input
                        # Save the JWT Token so other pages can use it in their headers!
                        st.session_state['access_token'] = data.get('access_token')
                        st.success('Login Successful Redirecting...')
                        time.sleep(1)
                        st.switch_page('pages/01_Home.py')
                        
                    elif response.status_code in [401,403]:
                        st.error('Incorrect username or password')
                    else:
                        st.error(f'Backend Error {response.status_code}: {response.text}')
                except requests.exceptions.RequestException as e:
                    st.error(f'Connection Error: {e}')
