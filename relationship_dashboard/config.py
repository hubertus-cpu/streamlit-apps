"""Application configuration constants."""

from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
DATA_DIR = ROOT_DIR / "data"
SERVICES_DIR = ROOT_DIR / "services"
COMPONENTS_DIR = ROOT_DIR / "components"
ASSETS_DIR = ROOT_DIR / "assets"

CLIENTS_FILE = DATA_DIR / "clients.csv"
USER_INPUTS_FILE = DATA_DIR / "user_inputs.csv"
AUDIT_LOG_FILE = DATA_DIR / "audit_log.csv"

DATE_FORMAT = "%Y-%m-%d"
REVIEW_OVERDUE_MONTHS = 12
DEFAULT_PAGE_SIZE = 50
PAGE_SIZE_OPTIONS = [25, 50, 100, 200]

ALLOWED_TAGS = {"G", "U", "P"}

REQUIRED_CLIENT_COLUMNS = [
    "client_id",
    "tag",
    "region",
    "region1",
    "region2",
    "pod",
    "CA",
    "RM",
    "review_cawb",
    "SG",
    "layer",
]

USER_INPUT_COLUMNS = [
    "entry_id",
    "client_id",
    "review_date",
    "layer_date",
    "comment",
    "changed_by",
    "change_timestamp",
    "is_active",
    "previous_entry_id",
]

AUDIT_COLUMNS = [
    "audit_id",
    "entry_id",
    "client_id",
    "changed_by",
    "change_timestamp",
    "old_values",
    "new_values",
]

FILTER_COLUMNS = ["region", "region1", "region2", "pod", "CA", "RM", "SG", "status"]

EDITABLE_COLUMNS = ["review_date", "layer_date", "comment"]

TABLE_COLUMNS = [
    "selected",
    "status",
    "SG",
    "client_id",
    "tag",
    "region",
    "region1",
    "region2",
    "pod",
    "CA",
    "RM",
    "review_cawb",
    "review_date",
    "layer_date",
    "comment",
]
