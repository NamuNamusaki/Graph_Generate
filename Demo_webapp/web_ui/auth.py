"""Shared authentication helpers for pages that require a logged-in session.

Pages that need a user to be logged in (Data prep, Job status, Dashboard)
should call `require_login()` as their first statement, and use
`get_auth_headers()` wherever they need to attach the session's bearer
token to a backend request.
"""
import streamlit as st


def require_login(redirect_to: str = "pages/02_Login.py", *, next_page: str = None) -> None:
    """Stop rendering the page and send the user to Login if not authenticated.

    next_page: this page's own path (e.g. 'pages/05_Dashboard.py'). When
    given, it's carried through the Login redirect as a `next` query param --
    together with `job_uuid`, if the URL already has one (e.g. from a
    "results are ready" email link) -- so Login can send the user back to
    the right place, with the right job still addressable, once they sign
    in. st.switch_page() clears all query params by default, so anything
    that needs to survive the redirect has to be passed explicitly via
    `query_params=`.
    """
    if not st.session_state.get('logged_in', False):
        st.warning('Please log in to view this page.')
        carry = {}
        if next_page:
            carry['next'] = next_page
        job_uuid = st.query_params.get('job_uuid')
        if job_uuid:
            carry['job_uuid'] = job_uuid
        st.switch_page(redirect_to, query_params=carry or None)
        st.stop()


def get_auth_headers() -> dict:
    """Bearer-token header built from the session's access token."""
    return {"Authorization": f"Bearer {st.session_state.get('access_token', '')}"}
