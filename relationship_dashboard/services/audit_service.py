"""Audit trail persistence for dashboard edits."""

from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

import pandas as pd

from config import AUDIT_COLUMNS
from utils.helpers import atomic_write_dataframe, file_lock, iso_now, read_csv_or_empty


def ensure_audit_file(audit_file: Path) -> None:
    """Create the audit file with the expected schema if missing."""
    if audit_file.exists():
        return
    empty_df = pd.DataFrame(columns=AUDIT_COLUMNS)
    atomic_write_dataframe(empty_df, audit_file)


def append_audit_entry(
    audit_file: Path,
    entry_id: str,
    client_id: str,
    changed_by: str,
    old_values: dict,
    new_values: dict,
) -> None:
    """Append one audit event with old/new payloads."""
    ensure_audit_file(audit_file)

    with file_lock(audit_file):
        audit_df = read_csv_or_empty(audit_file, AUDIT_COLUMNS)
        new_row = {
            "audit_id": str(uuid4()),
            "entry_id": entry_id,
            "client_id": str(client_id),
            "changed_by": changed_by,
            "change_timestamp": iso_now(),
            "old_values": json.dumps(old_values, ensure_ascii=True),
            "new_values": json.dumps(new_values, ensure_ascii=True),
        }
        updated_df = pd.concat([audit_df, pd.DataFrame([new_row])], ignore_index=True)
        atomic_write_dataframe(updated_df[AUDIT_COLUMNS], audit_file)
