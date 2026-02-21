"""Top navigation bar component."""

from __future__ import annotations

from datetime import datetime

import streamlit as st


def render_navbar(user_name: str) -> None:
    """Render dashboard header with user and timestamp."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    st.markdown(
        f"""
        <div class="navbar">
            <div class="navbar-title">Client Review Dashboard</div>
            <div class="navbar-meta">User: {user_name} | {timestamp}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
