import streamlit as st
st.set_page_config(page_title="Login", layout="centered")

if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False
if "username" not in st.session_state:
    st.session_state["username"] = None

st.title('User Login')
st.markdown("Please Enter your Username and Password to Using the tool")

USER_CREDENTIALS = {
    "admin": "password123",
    "user": "password888"
}

with st.form("login_form"):
    username = st.text_input("Username",key='login_username')
    password = st.text_input("Password", type="password", key='login_password')
    submitted_login = st.form_submit_button("Login", type="primary")

    if submitted_login:
        login_payload = {
            "username": st.session_state.login_username,
            "password": st.session_state.login_password
        }
        # response = requests.post("http://api/login", json=login_payload)
        if login_payload["username"] and login_payload["password"]:
            st.session_state["logged_in"] = True
            st.session_state["username"] = login_payload["username"]
            st.success("Login successful! Redirecting...")
            st.switch_page("pages/01_Home.py")
        else:
            st.error(" Incorrect username or password. Please try again.")