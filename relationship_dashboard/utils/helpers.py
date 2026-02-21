"""Helper utilities for IO, date parsing, and user context."""

from __future__ import annotations

import getpass
import os
import re
import tempfile
import time
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path
from typing import Generator, Optional

import pandas as pd


def get_current_username() -> str:
    """Return the current system username with a safe fallback."""
    try:
        return os.getlogin()
    except OSError:
        return getpass.getuser() or "unknown"


def normalize_text(value: object) -> str:
    """Normalize a value into a stripped string, or empty string for nulls."""
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except TypeError:
        pass
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, pd.Timestamp):
        return value.date().isoformat()
    if isinstance(value, pd.Timedelta):
        return ""
    return str(value).strip()


def parse_date(value: object) -> Optional[date]:
    """Parse date-like values into date objects, supporting partial inputs."""
    if isinstance(value, pd.Timestamp):
        if pd.isna(value):
            return None
        return value.date()
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value

    raw_value = normalize_text(value)
    if not raw_value:
        return None

    for date_format in ("%Y-%m-%d", "%Y/%m/%d", "%m/%d/%Y", "%m-%d-%Y"):
        try:
            return datetime.strptime(raw_value, date_format).date()
        except ValueError:
            pass

    year_month_match = re.match(r"^(\d{4})-(\d{1,2})$", raw_value)
    if year_month_match:
        year = int(year_month_match.group(1))
        month = int(year_month_match.group(2))
        if 1 <= month <= 12:
            return date(year, month, 1)

    year_only_match = re.match(r"^(\d{4})$", raw_value)
    if year_only_match:
        return date(int(year_only_match.group(1)), 1, 1)

    month_only_match = re.match(r"^(\d{1,2})$", raw_value)
    if month_only_match:
        month = int(month_only_match.group(1))
        if 1 <= month <= 12:
            return date(date.today().year, month, 1)

    try:
        return datetime.fromisoformat(raw_value).date()
    except ValueError:
        return None


def iso_now() -> str:
    """Return current UTC timestamp in ISO-8601 format."""
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


@contextmanager
def file_lock(file_path: Path, timeout_seconds: float = 10.0) -> Generator[None, None, None]:
    """Acquire an exclusive lock using lockfile creation."""
    lock_path = file_path.with_suffix(file_path.suffix + ".lock")
    start_time = time.time()

    while True:
        try:
            fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_RDWR)
            break
        except FileExistsError:
            if time.time() - start_time > timeout_seconds:
                raise TimeoutError(f"Could not acquire lock for {file_path}")
            time.sleep(0.05)

    try:
        os.write(fd, str(os.getpid()).encode("utf-8"))
        yield
    finally:
        os.close(fd)
        try:
            os.remove(lock_path)
        except FileNotFoundError:
            pass


def atomic_write_dataframe(dataframe: pd.DataFrame, target_path: Path) -> None:
    """Write a dataframe atomically to CSV by replacing a temporary file."""
    target_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        newline="",
        delete=False,
        dir=target_path.parent,
        suffix=".tmp",
    ) as tmp_file:
        dataframe.to_csv(tmp_file.name, index=False)
        temp_name = tmp_file.name

    os.replace(temp_name, target_path)


def read_csv_or_empty(file_path: Path, columns: list[str]) -> pd.DataFrame:
    """Read a CSV if it exists; otherwise return an empty dataframe with columns."""
    if not file_path.exists():
        return pd.DataFrame(columns=columns)

    dataframe = pd.read_csv(file_path, dtype=str).fillna("")
    for column in columns:
        if column not in dataframe.columns:
            dataframe[column] = ""
    return dataframe[columns]
