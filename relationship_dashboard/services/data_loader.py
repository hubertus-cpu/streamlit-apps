"""Data loading and persistence services for the dashboard."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Tuple
from uuid import uuid4

import pandas as pd
from dateutil.relativedelta import relativedelta

from config import ALLOWED_TAGS, AUDIT_COLUMNS, REQUIRED_CLIENT_COLUMNS, USER_INPUT_COLUMNS
from services import validation_service
from utils.helpers import atomic_write_dataframe, file_lock, iso_now, parse_date, read_csv_or_empty

STATUS_LABELS = {
    "MISSING": "🔴 MISSING",
    "OVERDUE": "🟠 OVERDUE",
    "ACTIVE": "🟢 ACTIVE",
}


def ensure_data_files(data_dir: Path, user_inputs_file: Path, audit_file: Path) -> None:
    """Ensure data directory and writable CSV files exist."""
    data_dir.mkdir(parents=True, exist_ok=True)

    if not user_inputs_file.exists():
        atomic_write_dataframe(pd.DataFrame(columns=USER_INPUT_COLUMNS), user_inputs_file)

    if not audit_file.exists():
        atomic_write_dataframe(pd.DataFrame(columns=AUDIT_COLUMNS), audit_file)


def load_clients(clients_file: Path) -> pd.DataFrame:
    """Load and normalize clients source data from CSV."""
    if not clients_file.exists():
        raise FileNotFoundError(f"Missing required file: {clients_file}")

    dataframe = pd.read_csv(clients_file, dtype=str).fillna("")
    for column in REQUIRED_CLIENT_COLUMNS:
        if column not in dataframe.columns:
            dataframe[column] = ""

    dataframe = dataframe[REQUIRED_CLIENT_COLUMNS].copy()
    dataframe["_row_order"] = range(len(dataframe))
    dataframe["tag"] = dataframe["tag"].astype(str).str.strip()

    # Keep only exact tag matches from the business whitelist.
    dataframe = dataframe[dataframe["tag"].isin(ALLOWED_TAGS)].copy()
    return dataframe


def deduplicate_latest_clients(dataframe: pd.DataFrame) -> pd.DataFrame:
    """Deduplicate by client using latest CAW-date rule with row-order fallback."""
    if dataframe.empty:
        return dataframe.copy()

    working_df = dataframe.copy()
    working_df["_review_caw_dt"] = pd.to_datetime(working_df["review_cawb"], errors="coerce")

    def pick_latest_row(group: pd.DataFrame) -> int:
        dated_rows = group[group["_review_caw_dt"].notna()]
        if not dated_rows.empty:
            max_date = dated_rows["_review_caw_dt"].max()
            max_rows = dated_rows[dated_rows["_review_caw_dt"] == max_date]
            return int(max_rows["_row_order"].idxmax())
        return int(group["_row_order"].idxmax())

    latest_indexes = working_df.groupby("client_id", sort=False).apply(pick_latest_row)
    latest_df = working_df.loc[latest_indexes.tolist()].copy()

    # Always display CAW and region fields from the last occurrence in the file.
    last_occurrence = (
        working_df.sort_values("_row_order")
        .groupby("client_id", as_index=False)
        .tail(1)
        [["client_id", "review_cawb", "region", "region1", "region2"]]
    )

    latest_df = latest_df.drop(columns=["review_cawb", "region", "region1", "region2"], errors="ignore")
    latest_df = latest_df.merge(last_occurrence, on="client_id", how="left")

    latest_df = latest_df.drop(columns=["_review_caw_dt"], errors="ignore")
    latest_df = latest_df.sort_values("client_id").reset_index(drop=True)
    return latest_df


def load_user_inputs(user_inputs_file: Path) -> pd.DataFrame:
    """Load user inputs file and normalize expected schema."""
    dataframe = read_csv_or_empty(user_inputs_file, USER_INPUT_COLUMNS)
    dataframe["is_active"] = dataframe["is_active"].astype(str).str.lower().isin(["true", "1", "yes"])
    return dataframe


def get_active_user_inputs(user_inputs_df: pd.DataFrame) -> pd.DataFrame:
    """Return one active entry per client, preferring the latest timestamp."""
    if user_inputs_df.empty:
        return pd.DataFrame(
            columns=["client_id", "entry_id", "review_date", "layer_date", "test_date", "comment"]
        )

    active_df = user_inputs_df[user_inputs_df["is_active"]].copy()
    if active_df.empty:
        return pd.DataFrame(
            columns=["client_id", "entry_id", "review_date", "layer_date", "test_date", "comment"]
        )

    active_df = (
        active_df.sort_values(["client_id", "change_timestamp"])  # ISO timestamps sort lexicographically.
        .groupby("client_id", as_index=False)
        .tail(1)
    )
    return active_df[["client_id", "entry_id", "review_date", "layer_date", "test_date", "comment"]]


def _compute_status(review_date: str) -> str:
    """Compute status based only on review_date."""
    parsed_review = parse_date(review_date)
    if parsed_review is None:
        return "MISSING"

    overdue_cutoff = pd.Timestamp.today().date() - relativedelta(months=12)
    if parsed_review <= overdue_cutoff:
        return "OVERDUE"

    return "ACTIVE"


def compute_status_label(review_date: object) -> str:
    """Return the display label for a status derived from review-date rules."""
    return STATUS_LABELS[_compute_status(str(review_date))]


def merge_clients_with_user_inputs(clients_df: pd.DataFrame, active_inputs_df: pd.DataFrame) -> pd.DataFrame:
    """Merge latest clients view with active user input rows."""
    merged_df = clients_df.merge(active_inputs_df, on="client_id", how="left")
    merged_df = merged_df.rename(columns={"entry_id": "active_entry_id"})

    for column in ["review_date", "layer_date", "test_date", "comment", "active_entry_id"]:
        merged_df[column] = merged_df[column].fillna("")

    merged_df["status"] = merged_df.apply(
        lambda row: STATUS_LABELS[_compute_status(str(row["review_date"]))],
        axis=1,
    )

    merged_df["selected"] = False
    return merged_df


def persist_user_edit(
    user_inputs_file: Path,
    client_id: str,
    changed_by: str,
    new_values: Dict[str, str],
) -> Tuple[str, Dict[str, str], Dict[str, str]]:
    """Deactivate prior active row and append a new active user input entry."""
    valid, error_message, normalized_values = validation_service.validate_edit_payload(
        new_values.get("review_date", ""),
        new_values.get("layer_date", ""),
        new_values.get("test_date", ""),
        new_values.get("comment", ""),
    )
    if not valid:
        raise ValueError(error_message or "Invalid edit payload.")

    with file_lock(user_inputs_file):
        user_inputs_df = read_csv_or_empty(user_inputs_file, USER_INPUT_COLUMNS)
        user_inputs_df["is_active"] = user_inputs_df["is_active"].astype(str).str.lower().isin(["true", "1", "yes"])

        client_mask = user_inputs_df["client_id"] == str(client_id)
        active_mask = client_mask & user_inputs_df["is_active"]

        old_values = {"review_date": "", "layer_date": "", "test_date": "", "comment": ""}
        previous_entry_id = ""

        if active_mask.any():
            active_rows = user_inputs_df[active_mask].copy()
            active_rows = active_rows.sort_values("change_timestamp")
            previous_active = active_rows.iloc[-1]
            previous_entry_id = str(previous_active.get("entry_id", ""))
            old_values = {
                "review_date": str(previous_active.get("review_date", "")),
                "layer_date": str(previous_active.get("layer_date", "")),
                "test_date": str(previous_active.get("test_date", "")),
                "comment": str(previous_active.get("comment", "")),
            }

        user_inputs_df.loc[active_mask, "is_active"] = False

        entry_id = str(uuid4())
        timestamp = iso_now()
        new_row = {
            "entry_id": entry_id,
            "client_id": str(client_id),
            "review_date": normalized_values.get("review_date", ""),
            "layer_date": normalized_values.get("layer_date", ""),
            "test_date": normalized_values.get("test_date", ""),
            "comment": normalized_values.get("comment", ""),
            "changed_by": changed_by,
            "change_timestamp": timestamp,
            "is_active": True,
            "previous_entry_id": previous_entry_id,
        }

        updated_df = pd.concat([user_inputs_df, pd.DataFrame([new_row])], ignore_index=True)
        atomic_write_dataframe(updated_df[USER_INPUT_COLUMNS], user_inputs_file)

    return entry_id, old_values, normalized_values
