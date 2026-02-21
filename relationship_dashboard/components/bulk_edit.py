"""Bulk edit panel component."""

from __future__ import annotations

from typing import Dict, Tuple

import streamlit as st


def render_bulk_edit_panel(selected_count: int) -> Tuple[bool, Dict[str, str]]:
    """Render bulk edit controls and return apply action with payload."""
    if selected_count <= 0:
        st.info("Select one or more rows to enable bulk edit.")
        return False, {}

    st.markdown("### Bulk Edit")
    st.caption(f"Selected clients: {selected_count}")

    st.markdown(
        '<div class="bulk-field-label">Bulk Review Date (YYYY-MM-DD)</div>',
        unsafe_allow_html=True,
    )
    review_date = st.text_input(
        "Bulk Review Date (YYYY-MM-DD)",
        key="bulk_review_date",
        label_visibility="collapsed",
    )
    st.markdown(
        '<div class="bulk-field-label">Bulk Layer Date (YYYY-MM-DD)</div>',
        unsafe_allow_html=True,
    )
    layer_date = st.text_input(
        "Bulk Layer Date (YYYY-MM-DD)",
        key="bulk_layer_date",
        label_visibility="collapsed",
    )
    st.markdown(
        '<div class="bulk-field-label">Bulk Comment</div>',
        unsafe_allow_html=True,
    )
    comment = st.text_area(
        "Bulk Comment",
        key="bulk_comment",
        height=90,
        label_visibility="collapsed",
    )

    apply_clicked = st.button("Apply", type="primary")
    payload = {
        "review_date": review_date,
        "layer_date": layer_date,
        "comment": comment,
    }
    return apply_clicked, payload
