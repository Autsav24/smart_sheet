import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime

st.set_page_config(page_title="SmartSheet Clone", layout="wide")
st.title("📊 Smartsheet-like App")

# Ensure DB
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

# Load data
df = pd.read_sql("SELECT * FROM tasks", conn)

# If empty, insert some sample rows
if df.empty:
    sample = pd.DataFrame([
        {"task": "Setup project repo", "owner": "Alice", "status": "Not Started", "due_date": "2025-10-15", "priority": "High"},
        {"task": "Design database schema", "owner": "Bob", "status": "In Progress", "due_date": "2025-10-20", "priority": "Medium"},
    ])
    sample.to_sql("tasks", conn, if_exists="append", index=False)
    df = pd.read_sql("SELECT * FROM tasks", conn)

# Editable grid
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

# Save changes
if st.button("💾 Save Changes"):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    edited_df["updated_by"] = st.session_state.auth["username"] if "auth" in st.session_state else "guest"
    edited_df["updated_at"] = now

    conn.execute("DELETE FROM tasks")  # Replace with update logic if needed
    edited_df.to_sql("tasks", conn, if_exists="append", index=False)
    conn.commit()
    st.success("Changes saved successfully!")
