import os
from datetime import date

import pyodbc
import streamlit as st

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


def insert_business_case(payload):
    insert_sql = """
        INSERT INTO business_cases (
            title,
            description,
            responsible_person,
            department,
            expected_benefit,
            benefit_unit,
            start_date,
            end_date,
            additional_notes,
            created_at
        )
        OUTPUT INSERTED.id
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, SYSDATETIME())
    """

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            insert_sql,
            payload["title"],
            payload["description"],
            payload["responsible_person"],
            payload["department"],
            payload["expected_benefit"],
            payload["benefit_unit"],
            payload["start_date"],
            payload["end_date"],
            payload["additional_notes"],
        )
        row = cursor.fetchone()
        conn.commit()
        return int(row[0])


def is_missing_required(fields):
    return any(value is None or value == "" for value in fields)


def main():
    st.set_page_config(page_title="Business Case Entry", layout="centered")

    if "last_success_id" not in st.session_state:
        st.session_state.last_success_id = None

    if st.session_state.last_success_id is not None:
        st.success(
            f"Business case saved successfully. Your business case ID is: {st.session_state.last_success_id}."
        )

    st.title("Business Case Entry")
    st.caption("Fields marked with * are required.")

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
        st.markdown("Responsible Person *")
        responsible_person = st.text_input(
            "Responsible Person",
            help="Name of the person responsible",
            label_visibility="collapsed",
        )
        st.markdown("Department *")
        department = st.selectbox(
            "Department",
            options=DEPARTMENTS,
            help="Select the responsible department",
            label_visibility="collapsed",
        )
        st.markdown("Expected Benefit *")
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
            options=BENEFIT_UNITS,
            help="Select the unit for the expected benefit",
            label_visibility="collapsed",
        )
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

        submitted = st.form_submit_button("Save Business Case")

    if submitted:
        title_value = title.strip()
        description_value = description.strip()
        responsible_value = responsible_person.strip()
        notes_value = additional_notes.strip() if additional_notes else None

        required_fields = [
            title_value,
            description_value,
            responsible_value,
            department,
            benefit_unit,
            start_date,
            end_date,
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

        payload = {
            "title": title_value,
            "description": description_value,
            "responsible_person": responsible_value,
            "department": department,
            "expected_benefit": float(expected_benefit),
            "benefit_unit": benefit_unit,
            "start_date": start_date,
            "end_date": end_date,
            "additional_notes": notes_value,
        }

        try:
            new_id = insert_business_case(payload)
        except Exception:
            st.error(ERROR_MESSAGE)
            return

        st.session_state.last_success_id = new_id
        st.rerun()


if __name__ == "__main__":
    main()
