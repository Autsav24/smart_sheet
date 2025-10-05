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

# Load tasks
df = pd.read_sql("SELECT * FROM tasks", conn)

# Editable grid
edited_df = st.data_editor(
    df,
    num_rows="dynamic",
    use_container_width=True,
    key="editor"
)

# Save changes
if st.button("💾 Save Changes"):
    conn.execute("DELETE FROM tasks")  # wipe
    edited_df.to_sql("tasks", conn, if_exists="append", index=False)
    conn.commit()
    st.success("Changes saved!")

# Kanban (group by status)
st.subheader("📌 Kanban View")
for status in edited_df['status'].unique():
    st.markdown(f"### {status}")
    tasks = edited_df[edited_df['status'] == status]
    for _, row in tasks.iterrows():
        st.write(f"- **{row['task']}** (Owner: {row['owner']}, Due: {row['due_date']})")

# Gantt Chart
import plotly.express as px
if not edited_df.empty:
    fig = px.timeline(
        edited_df,
        x_start="due_date",
        x_end="due_date",  # replace with start/end later
        y="task",
        color="status"
    )
    st.plotly_chart(fig, use_container_width=True)
