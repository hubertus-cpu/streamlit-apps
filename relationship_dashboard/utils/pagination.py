"""Pagination helpers for server-side table slicing."""

from __future__ import annotations

import math
from typing import Tuple


def compute_total_pages(total_rows: int, page_size: int) -> int:
    """Compute the total number of pages for the provided page size."""
    if page_size <= 0:
        return 1
    return max(1, math.ceil(total_rows / page_size))


def clamp_page_number(page_number: int, total_pages: int) -> int:
    """Clamp page number to valid bounds."""
    return min(max(page_number, 1), max(total_pages, 1))


def page_slice(page_number: int, page_size: int) -> Tuple[int, int]:
    """Return start/end row offsets for the selected page."""
    start = (page_number - 1) * page_size
    end = start + page_size
    return start, end
