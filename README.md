# Business Case Entry App

## Overview
Streamlit app for entering business cases and persisting them to an MS SQL database.

## Setup
Set the following environment variables:

- `MSSQL_HOST`
- `MSSQL_PORT` (optional, default `1433`)
- `MSSQL_DATABASE`
- `MSSQL_USER`
- `MSSQL_PASSWORD`
- `MSSQL_DRIVER` (optional, default `ODBC Driver 18 for SQL Server`)

## Run

```bash
pip install -r requirements.txt
streamlit run app.py
```
