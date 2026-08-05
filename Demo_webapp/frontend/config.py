"""Centralized backend API configuration.

Every page should import its endpoint URLs from here instead of hardcoding
`http://127.0.0.1:8000`, so the backend location only needs to change in one
place (e.g. when pointing the app at a real, non-mock backend).
"""
import os

API_BASE_URL = os.environ.get("SMARTBIOPEP_API_BASE_URL", "http://127.0.0.1:8000")
API_URL = f"{API_BASE_URL}/api"
