"""Filter panel component."""

from __future__ import annotations

from typing import Dict, List

import streamlit as st


def render_filters(options: Dict[str, List[str]], columns: List[str]) -> Dict[str, List[str]]:
    """Render multi-select filters and return the active selections."""
    st.sidebar.markdown("## Filters")
    selected_filters: Dict[str, List[str]] = {}

    for column in columns:
        selected_filters[column] = st.sidebar.multiselect(
            label=column,
            options=options.get(column, []),
            key=f"filter_{column}",
            placeholder=f"Select {column}",
        )

    return selected_filters
