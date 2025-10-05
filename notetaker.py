import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime, date

st.set_page_config(page_title="SmartSheet Clone", layout="wide")
st.title("📊 Smartsheet-like App")

# =================================
# DB Setup
# =================================
conn = sqlite3.connect("tasks.db")
c = conn.cursor()
c.execute("""CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task TEXT,
    owner TEXT,
    status TEXT,
    due_date TEXT,
    priority TEXT,
    updated_by TEXT,
    updated_at TEXT
)""")
conn.commit()

# =================================
# Load Data
# =================================
df = pd.read_sql("SELECT * FROM tasks", conn)

# Insert sample rows if DB is empty
if df.empty:
    sample = pd.DataFrame([
        {"task": "Setup project repo", "owner": "Alice", "status": "Not Started", "due_date": "2025-10-15", "priority": "High"},
        {"task": "Design database schema", "owner": "Bob", "status": "In Progress", "due_date": "2025-10-20", "priority": "Medium"},
    ])
    sample.to_sql("tasks", conn, if_exists="append", index=False)
    df = pd.read_sql("SELECT * FROM tasks", conn)

# =================================
# Type Conversions (Fix for st.data_editor)
# =================================
if not df.empty:
    if "id" in df.columns:
        df["id"] = pd.to_numeric(df["id"], errors="coerce").astype("Int64")
    if "due_date" in df.columns:
        df["due_date"] = pd.to_datetime(df["due_date"], errors="coerce").dt.date
    if "updated_at" in df.columns:
        df["updated_at"] = pd.to_datetime(df["updated_at"], errors="coerce")

# =================================
# Editable Grid
# =================================
edited_df = st.data_editor(
    df,
    num_rows="dynamic",
    use_container_width=True,
    column_config={
        "id": st.column_config.NumberColumn("ID", disabled=True),  # Auto-increment
        "task": st.column_config.TextColumn("Task"),
        "owner": st.column_config.TextColumn("Owner"),
        "status": st.column_config.SelectboxColumn(
            "Status", options=["Not Started", "In Progress", "Done"]
        ),
        "due_date": st.column_config.DateColumn("Due Date"),
        "priority": st.column_config.SelectboxColumn(
            "Priority", options=["Low", "Medium", "High"]
        ),
        "updated_by": st.column_config.TextColumn("Updated By", disabled=True),
        "updated_at": st.column_config.DatetimeColumn("Updated At", disabled=True),
    },
    hide_index=True,
    key="editor"
)

# =================================
# Save Changes
# =================================
if st.button("💾 Save Changes"):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    edited_df["updated_by"] = "guest"  # Later replace with logged-in user
    edited_df["updated_at"] = now

    # Save back to DB
    conn.execute("DELETE FROM tasks")  # Replace with smarter updates later
    edited_df.to_sql("tasks", conn, if_exists="append", index=False)
    conn.commit()
    st.success("Changes saved successfully!")
