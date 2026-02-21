"""Editable table component using Streamlit data_editor."""

from __future__ import annotations

from datetime import date, datetime
from typing import Dict, List, Set, Tuple

import pandas as pd
import streamlit as st

from config import TABLE_COLUMNS
from utils.helpers import normalize_text, parse_date


EditRequest = Dict[str, Dict[str, str]]


def _normalize_date_value(value: object) -> str:
    """Normalize date-like values to YYYY-MM-DD strings."""
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except TypeError:
        pass

    if isinstance(value, pd.Timestamp):
        return value.date().isoformat()
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, dict):
        try:
            year = int(value.get("year"))
            month = int(value.get("month"))
            day = int(value.get("day", 1))
            return date(year, month, day).isoformat()
        except (TypeError, ValueError):
            return ""

    raw_value = normalize_text(value)
    if not raw_value:
        return ""

    parsed_date = parse_date(raw_value)
    if parsed_date is not None:
        return parsed_date.isoformat()
    return raw_value


def _to_editor_date(value: object) -> date | None:
    """Convert table values to date objects for DateColumn editing."""
    parsed = parse_date(value)
    return parsed if parsed is not None else None


def render_table(page_df: pd.DataFrame, selected_client_ids: Set[str]) -> Tuple[Set[str], List[dict], List[str]]:
    """Render editable table and capture row selection plus inline cell edits."""
    if page_df.empty:
        st.info("No rows available.")
        return selected_client_ids, [], []

    original_df = page_df.copy().reset_index(drop=True)
    original_df["client_id"] = original_df["client_id"].astype(str)

    for column in ("review_date", "layer_date"):
        if column in original_df.columns:
            original_df[column] = original_df[column].apply(_normalize_date_value)
    if "test_date" in original_df.columns:
        original_df["test_date"] = original_df["test_date"].apply(normalize_text)

    working_df = original_df.copy()
    working_df["selected"] = working_df["client_id"].isin(selected_client_ids)

    for column in ("review_date", "layer_date"):
        if column in working_df.columns:
            working_df[column] = working_df[column].apply(_to_editor_date)

    display_columns = [column for column in TABLE_COLUMNS if column in working_df.columns]
    display_df = working_df[display_columns].copy()

    st.markdown(
        """
        <div class="status-legend">
            <span class="badge badge-missing">🔴 MISSING</span>
            <span class="badge badge-overdue">🟠 OVERDUE</span>
            <span class="badge badge-active">🟢 ACTIVE</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    editable_columns = ["selected", "review_date", "layer_date", "test_date", "comment"]
    disabled_columns = [column for column in display_columns if column not in editable_columns]

    edited_df = st.data_editor(
        display_df,
        key="client_table_editor",
        hide_index=True,
        width="stretch",
        num_rows="fixed",
        column_order=display_columns,
        disabled=disabled_columns,
        column_config={
            "selected": st.column_config.CheckboxColumn(label="", width="small"),
            "review_date": st.column_config.DateColumn(
                "review_date",
                format="YYYY-MM-DD",
                step=1,
            ),
            "layer_date": st.column_config.DateColumn(
                "layer_date",
                format="YYYY-MM-DD",
                step=1,
            ),
            "test_date": st.column_config.TextColumn(
                "test_date",
                help="Enter date as YYYY-MM-DD",
            ),
            "comment": st.column_config.TextColumn("comment"),
        },
    )

    if not isinstance(edited_df, pd.DataFrame):
        edited_df = pd.DataFrame(edited_df)
    if edited_df.empty:
        return set(), [], []

    edited_df["client_id"] = edited_df["client_id"].astype(str)
    updated_selected = set(
        edited_df.loc[edited_df["selected"].astype(bool), "client_id"].astype(str).tolist()
    )

    original_by_client = original_df.set_index("client_id").to_dict(orient="index")
    edit_requests: List[dict] = []
    blocked_changes: List[str] = []

    for _, row in edited_df.iterrows():
        client_id = str(row.get("client_id", ""))
        if client_id not in original_by_client:
            continue

        original_row = original_by_client[client_id]
        old_values = {
            "review_date": _normalize_date_value(original_row.get("review_date", "")),
            "layer_date": _normalize_date_value(original_row.get("layer_date", "")),
            "test_date": normalize_text(original_row.get("test_date", "")),
            "comment": normalize_text(original_row.get("comment", "")),
        }
        new_values = {
            "review_date": _normalize_date_value(row.get("review_date", "")),
            "layer_date": _normalize_date_value(row.get("layer_date", "")),
            "test_date": normalize_text(row.get("test_date", "")),
            "comment": normalize_text(row.get("comment", "")),
        }

        if old_values == new_values:
            continue

        edit_requests.append({"client_id": client_id, "old_values": old_values, "new_values": new_values})

    return updated_selected, edit_requests, blocked_changes
