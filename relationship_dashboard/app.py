"""Streamlit app entrypoint for the Client Review Dashboard."""

from __future__ import annotations

from pathlib import Path
from typing import List, Tuple

import streamlit as st

from components.bulk_edit import render_bulk_edit_panel
from components.navbar import render_navbar
from components.table import render_table
from config import (
    ASSETS_DIR,
    AUDIT_LOG_FILE,
    CLIENTS_FILE,
    DATA_DIR,
    FILTER_COLUMNS,
    USER_INPUTS_FILE,
)
from services import audit_service, data_loader, filter_service, validation_service
from utils.helpers import get_current_username


st.set_page_config(page_title="Client Review Dashboard", layout="wide")


def load_css() -> None:
    """Load app-level CSS styling from the assets directory."""
    css_path = ASSETS_DIR / "styles.css"
    if css_path.exists():
        with css_path.open("r", encoding="utf-8") as css_file:
            st.markdown(f"<style>{css_file.read()}</style>", unsafe_allow_html=True)


def init_session_state() -> None:
    """Initialize required session-state variables."""
    st.session_state.setdefault("selected_rows", set())
    st.session_state.setdefault("filtered_data", None)
    st.session_state.setdefault("user_name", get_current_username())
    st.session_state.setdefault("notifications", [])
    st.session_state.setdefault("validation_messages", [])
    st.session_state.setdefault("last_filter_signature", tuple())
    st.session_state.setdefault("status_overrides", {})


def render_top_filters(filter_options: dict[str, list[str]]) -> dict[str, list[str]]:
    """Render searchable dropdown filters above the table."""
    st.markdown("#### Filters")
    filter_order = ["region", "region1", "region2", "pod", "CA", "RM", "SG", "status"]
    filter_labels = {
        "region": "Region",
        "region1": "Region1",
        "region2": "Region2",
        "pod": "Pod",
        "CA": "CA",
        "RM": "RM",
        "SG": "SG",
        "status": "Status",
    }

    row_one_cols = st.columns(4)
    row_two_cols = st.columns(4)
    slots = [*row_one_cols, *row_two_cols]

    selected_filters: dict[str, list[str]] = {}
    for index, column in enumerate(filter_order):
        with slots[index]:
            selected_filters[column] = st.multiselect(
                filter_labels[column],
                options=filter_options.get(column, []),
                key=f"top_filter_{column}",
                placeholder=f"Filter {filter_labels[column]}",
            )
    return selected_filters


def queue_notification(level: str, message: str) -> None:
    """Queue a UI notification for display on the next render pass."""
    st.session_state["notifications"].append((level, message))


def queue_validation_message(message: str) -> None:
    """Queue validation feedback to be shown under the Client Table header."""
    st.session_state["validation_messages"].append(message)


def show_validation_messages() -> None:
    """Render validation messages under the table header without a title."""
    messages: List[str] = st.session_state.get("validation_messages", [])
    if not messages:
        return

    for message in messages:
        safe_message = message.replace("<", "&lt;").replace(">", "&gt;")
        st.markdown(
            f'<div class="validation-message">{safe_message}</div>',
            unsafe_allow_html=True,
        )

    st.session_state["validation_messages"] = []


def show_notifications() -> None:
    """Render queued status messages then clear the queue."""
    notifications: List[Tuple[str, str]] = st.session_state.get("notifications", [])
    if not notifications:
        return

    with st.container(border=True):
        st.markdown("### Status")
        for level, message in notifications:
            if level == "success":
                st.success(message)
            elif level == "warning":
                st.warning(message)
            else:
                st.info(message)

    st.session_state["notifications"] = []


@st.cache_data(show_spinner=False)
def get_latest_clients(clients_path: str, file_mtime: float):
    """Load and deduplicate clients with cache invalidation by mtime."""
    del file_mtime
    raw_clients = data_loader.load_clients(Path(clients_path))
    return data_loader.deduplicate_latest_clients(raw_clients)


def process_inline_edits(edit_requests: List[dict]) -> Tuple[bool, bool]:
    """Persist inline edit events and report whether any failed validation/save."""
    if not edit_requests:
        return False, False

    changed = False
    had_failures = False
    for request in edit_requests:
        client_id = request["client_id"]
        valid, error_message, normalized_values = validation_service.validate_edit_payload(
            request["new_values"].get("review_date", ""),
            request["new_values"].get("layer_date", ""),
            request["new_values"].get("test_date", ""),
            request["new_values"].get("comment", ""),
        )
        if not valid:
            queue_validation_message(f"Client {client_id}: {error_message}")
            had_failures = True
            continue

        try:
            entry_id, old_values, new_values = data_loader.persist_user_edit(
                USER_INPUTS_FILE,
                client_id,
                st.session_state["user_name"],
                normalized_values,
            )
            st.session_state["status_overrides"][str(client_id)] = data_loader.compute_status_label(
                normalized_values.get("review_date", ""),
            )
            audit_service.append_audit_entry(
                AUDIT_LOG_FILE,
                entry_id,
                client_id,
                st.session_state["user_name"],
                old_values,
                new_values,
            )
            changed = True
        except Exception as exc:  # pragma: no cover - streamlit runtime guard
            queue_notification("warning", f"Client {client_id}: Save failed ({exc}).")
            had_failures = True

    if changed:
        queue_notification("success", "Inline changes saved.")

    return changed, had_failures


def process_bulk_edit(selected_client_ids: set[str], payload: dict, current_data) -> bool:
    """Persist a bulk edit payload for selected clients."""
    valid, error_message, normalized_values = validation_service.validate_edit_payload(
        payload.get("review_date", ""),
        payload.get("layer_date", ""),
        payload.get("test_date", ""),
        payload.get("comment", ""),
    )
    if not valid:
        queue_validation_message(error_message or "Bulk payload is invalid.")
        return False

    changed_count = 0
    skipped_count = 0
    for client_id in selected_client_ids:
        row = current_data[current_data["client_id"].astype(str) == str(client_id)]
        if row.empty:
            skipped_count += 1
            continue

        try:
            entry_id, old_values, new_values = data_loader.persist_user_edit(
                USER_INPUTS_FILE,
                str(client_id),
                st.session_state["user_name"],
                normalized_values,
            )
            audit_service.append_audit_entry(
                AUDIT_LOG_FILE,
                entry_id,
                str(client_id),
                st.session_state["user_name"],
                old_values,
                new_values,
            )
            changed_count += 1
        except Exception as exc:  # pragma: no cover - streamlit runtime guard
            queue_notification("warning", f"Client {client_id}: Save failed ({exc}).")

    if changed_count:
        queue_notification("success", f"Bulk edit applied to {changed_count} clients.")
    if skipped_count:
        queue_notification(
            "warning",
            f"Skipped {skipped_count} client(s) due to missing data or non-editable rows.",
        )

    return changed_count > 0


def main() -> None:
    """Render and run the Client Review Dashboard."""
    load_css()
    init_session_state()

    try:
        data_loader.ensure_data_files(DATA_DIR, USER_INPUTS_FILE, AUDIT_LOG_FILE)

        if not CLIENTS_FILE.exists():
            st.error(f"CSV not found: {CLIENTS_FILE}")
            st.stop()

        clients_df = get_latest_clients(str(CLIENTS_FILE), CLIENTS_FILE.stat().st_mtime)
        user_inputs_df = data_loader.load_user_inputs(USER_INPUTS_FILE)
        active_inputs_df = data_loader.get_active_user_inputs(user_inputs_df)
        merged_df = data_loader.merge_clients_with_user_inputs(clients_df, active_inputs_df)

        valid_statuses = set(data_loader.STATUS_LABELS.values())
        overrides = {
            client_id: status
            for client_id, status in st.session_state.get("status_overrides", {}).items()
            if status in valid_statuses
        }
        st.session_state["status_overrides"] = overrides
        if overrides:
            persisted_status = merged_df.set_index("client_id")["status"].astype(str).to_dict()
            pending_overrides = {
                client_id: status
                for client_id, status in overrides.items()
                if persisted_status.get(str(client_id)) != status
            }
            st.session_state["status_overrides"] = pending_overrides
            if pending_overrides:
                merged_df["status"] = merged_df.apply(
                    lambda row: pending_overrides.get(str(row["client_id"]), row["status"]),
                    axis=1,
                )
    except FileNotFoundError as exc:
        st.error(str(exc))
        st.stop()
    except Exception as exc:  # pragma: no cover - streamlit runtime guard
        st.error(f"Application initialization failed: {exc}")
        st.stop()

    render_navbar(st.session_state["user_name"])
    filter_options = filter_service.get_filter_options(merged_df, FILTER_COLUMNS)
    selected_filters = render_top_filters(filter_options)
    filter_signature = filter_service.filters_signature(selected_filters)

    if filter_signature != st.session_state["last_filter_signature"]:
        st.session_state["last_filter_signature"] = filter_signature

    filtered_df = filter_service.apply_filters(merged_df, selected_filters)
    st.session_state["filtered_data"] = filtered_df

    st.markdown("### Client Table")
    st.caption(f"Total Rows: {len(filtered_df)}/{len(merged_df)}")
    show_validation_messages()

    if "client_id" in filtered_df.columns:
        sorted_df = filtered_df.sort_values(
            by="client_id",
            ascending=True,
            kind="mergesort",
            na_position="last",
        )
    else:
        sorted_df = filtered_df

    selected_rows, edit_requests, blocked_changes = render_table(
        sorted_df.copy(),
        set(st.session_state["selected_rows"]),
    )
    st.session_state["selected_rows"] = selected_rows

    for warning in blocked_changes:
        queue_notification("warning", warning)

    has_inline_changes, has_inline_failures = process_inline_edits(edit_requests)

    st.markdown("---")
    apply_bulk, bulk_payload = render_bulk_edit_panel(len(st.session_state["selected_rows"]))

    has_bulk_changes = False
    if apply_bulk:
        has_bulk_changes = process_bulk_edit(set(st.session_state["selected_rows"]), bulk_payload, merged_df)

    needs_refresh = bool(blocked_changes) or has_inline_changes or has_inline_failures or has_bulk_changes
    if needs_refresh:
        # Reset editor widget state to avoid replaying stale edits after rerun.
        st.session_state.pop("client_table_editor", None)
        st.rerun()

    show_notifications()


if __name__ == "__main__":
    main()
