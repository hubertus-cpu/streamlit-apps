"""Filtering utilities for dashboard dimensions."""

from __future__ import annotations

from typing import Dict, List

import pandas as pd


def get_filter_options(dataframe: pd.DataFrame, columns: List[str]) -> Dict[str, List[str]]:
    """Build sorted non-empty options for each filterable column."""
    options: Dict[str, List[str]] = {}
    for column in columns:
        if column not in dataframe.columns:
            options[column] = []
            continue
        values = [value for value in dataframe[column].astype(str).tolist() if value.strip()]
        options[column] = sorted(set(values))
    return options


def apply_filters(dataframe: pd.DataFrame, selected_filters: Dict[str, List[str]]) -> pd.DataFrame:
    """Apply AND logic across filter dimensions with OR inside each dimension."""
    filtered = dataframe
    for column, values in selected_filters.items():
        if not values or column not in filtered.columns:
            continue
        filtered = filtered[filtered[column].isin(values)]
    return filtered


def filters_signature(selected_filters: Dict[str, List[str]]) -> tuple:
    """Build a hashable signature used to detect filter changes."""
    return tuple((key, tuple(sorted(values))) for key, values in sorted(selected_filters.items()))
