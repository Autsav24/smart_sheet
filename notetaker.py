import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime, date

st.set_page_config(page_title="Smartsheet Clone", layout="wide")

st.title("📊 Smartsheet-like App")

# DB Setup
conn = sqlite3.connect("items.db")
c = conn.cursor()
c.execute("""
CREATE TABLE IF NOT EXISTS items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    parent_id INTEGER,
    name TEXT NOT NULL,
    owner TEXT,
    status TEXT,
    due_date TEXT,
    priority TEXT,
    updated_by TEXT,
    updated_at TEXT
)
""")
conn.commit()

# Toolbar
col1, col2, col3 = st.columns([1,1,1])
with col1:
    if st.button("➕ Add Section"):
        c.execute("INSERT INTO items (parent_id, name) VALUES (?, ?)", (None, "New Section"))
        conn.commit()
        st.rerun()
with col2:
    if st.button("⬇ Export CSV"):
        df = pd.read_sql("SELECT * FROM items", conn)
        st.download_button("Download CSV", df.to_csv(index=False), "smartsheet.csv")

# Load Data
df = pd.read_sql("SELECT * FROM items ORDER BY id", conn)

# Render Tree
for _, row in df[df["parent_id"].isna()].iterrows():
    st.markdown(f"### 📂 {row['name']}")
    tasks = df[df["parent_id"] == row["id"]]
    if not tasks.empty:
        tasks["due_date"] = pd.to_datetime(tasks["due_date"], errors="coerce").dt.date
        edited = st.data_editor(
            tasks,
            column_config={
                "id": st.column_config.NumberColumn("ID", disabled=True),
                "name": st.column_config.TextColumn("Task"),
                "owner": st.column_config.TextColumn("Owner"),
                "status": st.column_config.SelectboxColumn("Status", options=["Not Started", "In Progress", "Done"]),
                "due_date": st.column_config.DateColumn("Due Date"),
                "priority": st.column_config.SelectboxColumn("Priority", options=["Low", "Medium", "High"]),
            },
            hide_index=True,
            num_rows="dynamic",
            key=f"editor_{row['id']}"
        )
        if st.button(f"💾 Save {row['name']}", key=f"save_{row['id']}"):
            conn.execute("DELETE FROM items WHERE parent_id=?", (row["id"],))
            edited.to_sql("items", conn, if_exists="append", index=False)
            conn.commit()
            st.success("Saved")
            st.rerun()
    if st.button(f"➕ Add Task to {row['name']}", key=f"add_task_{row['id']}"):
        c.execute("INSERT INTO items (parent_id, name, status, priority) VALUES (?, ?, ?, ?)",
                  (row["id"], "New Task", "Not Started", "Medium"))
        conn.commit()
        st.rerun()
