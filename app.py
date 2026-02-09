import os
from datetime import date

import pyodbc
import streamlit as st
from streamlit_searchbox import st_searchbox

ERROR_MESSAGE = (
    "An unexpected error occurred while saving the business case. Please try again later."
)

REQUIRED_MESSAGE = "Please fill in all required fields before saving."
DATE_MESSAGE = "The end date cannot be earlier than the start date."
BENEFIT_MESSAGE = "Expected benefit must be a positive number."

DEPARTMENTS = [
    "Finance",
    "Operations",
    "Sales",
    "Marketing",
    "Engineering",
    "HR",
]

BENEFIT_UNITS = [
    "USD",
    "EUR",
    "Hours",
    "Units",
]

SELECT_PLACEHOLDER = "Select..."
TEST_ID_REF = [
    {"id": "A1023", "name": "Jordan Lee", "email": "jordan.lee@example.com"},
    {"id": "B2044", "name": "Priya Patel", "email": "priya.patel@example.com"},
    {"id": "C3189", "name": "Alex Rivera", "email": "alex.rivera@example.com"},
    {"id": "D4120", "name": "Morgan Chen", "email": "morgan.chen@example.com"},
    {"id": "E5097", "name": "Riley Kim", "email": "riley.kim@example.com"},
]


def get_connection():
    host = os.getenv("MSSQL_HOST")
    port = os.getenv("MSSQL_PORT", "1433")
    database = os.getenv("MSSQL_DATABASE")
    user = os.getenv("MSSQL_USER")
    password = os.getenv("MSSQL_PASSWORD")
    driver = os.getenv("MSSQL_DRIVER", "ODBC Driver 18 for SQL Server")

    if not all([host, database, user, password]):
        raise RuntimeError("Missing database connection configuration")

    conn_str = (
        "DRIVER={" + driver + "};"
        f"SERVER={host},{port};"
        f"DATABASE={database};"
        f"UID={user};"
        f"PWD={password};"
        "TrustServerCertificate=yes;"
    )
    return pyodbc.connect(conn_str)


def search_id_ref(term, limit=20):
    if not term:
        return []
    search_sql = """
        SELECT TOP (?)
            ID,
            NAME,
            EMAIL
        FROM ID_REF
        WHERE ID LIKE ? OR NAME LIKE ?
        ORDER BY NAME
    """
    like_term = f"%{term}%"
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(search_sql, limit, like_term, like_term)
            rows = cursor.fetchall()
    except Exception:
        rows = []

    return [
        {"id": row[0], "name": row[1], "email": row[2]}
        for row in rows
    ]


def search_test_id_ref(term, limit=20):
    lowered = term.lower()
    matches = [
        entry
        for entry in TEST_ID_REF
        if lowered in entry["id"].lower() or lowered in entry["name"].lower()
    ]
    return matches[:limit]


def search_responsible_person(searchterm, limit=20):
    if not searchterm or len(searchterm.strip()) < 2:
        return []
    results = search_id_ref(searchterm.strip(), limit=limit)
    if not results:
        results = search_test_id_ref(searchterm.strip(), limit=limit)
    return [
        (
            f'{entry["id"]} — {entry["name"]} ({entry["email"]})',
            entry,
        )
        for entry in results
    ]


def draft_column_available(cursor):
    cursor.execute(
        """
        SELECT 1
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_NAME = ? AND COLUMN_NAME = ?
        """,
        "business_cases",
        "is_draft",
    )
    return cursor.fetchone() is not None


def insert_business_case(payload):
    base_columns = [
        "title",
        "description",
        "responsible_person",
        "department",
        "expected_benefit",
        "benefit_unit",
        "start_date",
        "end_date",
        "additional_notes",
        "created_at",
    ]

    with get_connection() as conn:
        cursor = conn.cursor()
        columns = list(base_columns)
        values = [
            payload["title"],
            payload["description"],
            payload["responsible_person"],
            payload["department"],
            payload["expected_benefit"],
            payload["benefit_unit"],
            payload["start_date"],
            payload["end_date"],
            payload["additional_notes"],
        ]

        include_draft = draft_column_available(cursor)
        if include_draft:
            columns.insert(-1, "is_draft")
            values.append(1 if payload["is_draft"] else 0)

        placeholders = ", ".join("?" for _ in values) + ", SYSDATETIME()"
        insert_sql = f"""
            INSERT INTO business_cases (
                {", ".join(columns)}
            )
            OUTPUT INSERTED.id
            VALUES ({placeholders})
        """

        cursor.execute(insert_sql, *values)
        row = cursor.fetchone()
        conn.commit()
        return int(row[0]), include_draft


def is_missing_required(fields):
    return any(
        value is None or value == "" or value == SELECT_PLACEHOLDER for value in fields
    )


def main():
    st.set_page_config(page_title="Business Case Entry", layout="centered")

    if "last_success_id" not in st.session_state:
        st.session_state.last_success_id = None
    if "last_success_is_draft" not in st.session_state:
        st.session_state.last_success_is_draft = False

    if st.session_state.last_success_id is not None:
        if st.session_state.last_success_is_draft:
            st.success(
                f"Draft saved successfully. Your draft ID is: {st.session_state.last_success_id}."
            )
        else:
            st.success(
                f"Business case saved successfully. Your business case ID is: {st.session_state.last_success_id}."
            )

    st.title("Business Case Entry")
    st.caption("Fields marked with * are required.")

    st.markdown("Responsible Person *")
    responsible_person = st_searchbox(
        search_responsible_person,
        placeholder="Search ID or name",
        key="responsible_person_search",
        default=None,
        debounce=200,
    )

    with st.form("business_case_form", clear_on_submit=False):
        st.markdown("Business Case Title *")
        title = st.text_input(
            "Business Case Title",
            help="Enter a short, descriptive title",
            label_visibility="collapsed",
        )
        st.markdown("Business Case Description *")
        description = st.text_area(
            "Business Case Description",
            help="Describe the business case in detail",
            label_visibility="collapsed",
        )
        st.markdown("Department *")
        department = st.selectbox(
            "Department",
            options=[SELECT_PLACEHOLDER, *DEPARTMENTS],
            help="Select the responsible department",
            label_visibility="collapsed",
        )
        st.markdown("Expected Benefit *")
        include_benefit = st.checkbox("Add expected benefit now", value=True)
        expected_benefit = None
        if include_benefit:
            expected_benefit = st.number_input(
                "Expected Benefit",
                min_value=0.0,
                value=0.0,
                step=0.01,
                help="Enter a positive numeric value",
                label_visibility="collapsed",
            )
        st.markdown("Benefit Unit *")
        benefit_unit = st.selectbox(
            "Benefit Unit",
            options=[SELECT_PLACEHOLDER, *BENEFIT_UNITS],
            help="Select the unit for the expected benefit",
            label_visibility="collapsed",
        )
        include_dates = st.checkbox("Add dates now", value=True)
        start_date = None
        end_date = None
        if include_dates:
            st.markdown("Start Date *")
            start_date = st.date_input(
                "Start Date",
                value=date.today(),
                help="Planned start date",
                label_visibility="collapsed",
            )
            st.markdown("End Date *")
            end_date = st.date_input(
                "End Date",
                value=date.today(),
                help="Planned end date",
                label_visibility="collapsed",
            )
        additional_notes = st.text_area(
            "Additional Notes (optional)",
            help="Optional comments or context",
        )

        save_draft = st.form_submit_button("Save Draft")
        submitted = st.form_submit_button("Save Business Case")

    if save_draft or submitted:
        title_value = title.strip()
        description_value = description.strip()
        responsible_value = (
            None
            if not isinstance(responsible_person, dict)
            else str(responsible_person.get("id", "")).strip()
        )
        notes_value = additional_notes.strip() if additional_notes else None

        if submitted:
            required_fields = [
                title_value,
                description_value,
                responsible_value,
                department,
                benefit_unit,
                start_date,
                end_date,
                expected_benefit,
            ]

            if is_missing_required(required_fields):
                st.error(REQUIRED_MESSAGE)
                return

            if end_date < start_date:
                st.error(DATE_MESSAGE)
                return

            if expected_benefit <= 0:
                st.error(BENEFIT_MESSAGE)
                return

        if save_draft:
            if title_value == "":
                title_value = None
            if description_value == "":
                description_value = None
            if responsible_value == "":
                responsible_value = None
            if department == SELECT_PLACEHOLDER:
                department = None
            if benefit_unit == SELECT_PLACEHOLDER:
                benefit_unit = None
            if expected_benefit == 0:
                expected_benefit = None

        payload = {
            "title": title_value,
            "description": description_value,
            "responsible_person": responsible_value,
            "department": department,
            "expected_benefit": (
                float(expected_benefit) if expected_benefit is not None else None
            ),
            "benefit_unit": benefit_unit,
            "start_date": start_date,
            "end_date": end_date,
            "additional_notes": notes_value,
            "is_draft": bool(save_draft),
        }

        try:
            new_id, draft_supported = insert_business_case(payload)
        except Exception:
            st.error(ERROR_MESSAGE)
            return

        if save_draft and not draft_supported:
            st.info(
                "Draft saved. Add an `is_draft` column to `business_cases` to track draft status."
            )

        st.session_state.last_success_id = new_id
        st.session_state.last_success_is_draft = bool(save_draft)
        st.rerun()


if __name__ == "__main__":
    main()
