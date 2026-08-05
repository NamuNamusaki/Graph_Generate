"""Shared authentication helpers for pages that require a logged-in session.

Pages that need a user to be logged in (Data prep, Job status, Dashboard)
should call `require_login()` as their first statement, and use
`get_auth_headers()` wherever they need to attach the session's bearer
token to a backend request.
"""
import streamlit as st


def require_login(redirect_to: str = "pages/02_Login.py") -> None:
    """Stop rendering the page and send the user to Login if not authenticated."""
    if not st.session_state.get('logged_in', False):
        st.warning('Please log in to view this page.')
        st.switch_page(redirect_to)
        st.stop()


def get_auth_headers() -> dict:
    """Bearer-token header built from the session's access token."""
    return {"Authorization": f"Bearer {st.session_state.get('access_token', '')}"}
