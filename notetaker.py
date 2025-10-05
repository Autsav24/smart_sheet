import streamlit as st
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="Smartsheet Clone", layout="wide")

# Inject custom CSS
st.markdown("""
    <style>
    .section-row {
        background-color: #f7f7f7;
        font-weight: bold;
        padding: 6px;
        border-bottom: 1px solid #ddd;
    }
    .task-row {
        padding: 4px 20px;
        border-bottom: 1px solid #eee;
    }
    .badge {
        padding: 3px 8px;
        border-radius: 12px;
        font-size: 0.8em;
        color: white;
    }
    .status-not { background-color: gray; }
    .status-prog { background-color: dodgerblue; }
    .status-done { background-color: seagreen; }
    .priority-low { background-color: green; }
    .priority-med { background-color: orange; }
    .priority-high { background-color: red; }
    </style>
""", unsafe_allow_html=True)

st.title("📊 Smartsheet-like App (Styled Grid)")

# Example Data
data = [
    {"type": "section", "name": "Frontend"},
    {"type": "task", "name": "Setup React project", "owner": "Alice", "status": "Not Started", "due": "2025-10-15", "priority": "High"},
    {"type": "task", "name": "Build login page", "owner": "Bob", "status": "In Progress", "due": "2025-10-18", "priority": "Medium"},
    {"type": "section", "name": "Backend"},
    {"type": "task", "name": "Design database schema", "owner": "Charlie", "status": "Done", "due": "2025-10-12", "priority": "High"},
]
df = pd.DataFrame(data)

# Render styled tree view
for _, row in df.iterrows():
    if row["type"] == "section":
        st.markdown(f"<div class='section-row'>📂 {row['name']}</div>", unsafe_allow_html=True)
    else:
        # Status badge
        status_class = {
            "Not Started": "status-not",
            "In Progress": "status-prog",
            "Done": "status-done"
        }.get(row["status"], "status-not")
        priority_class = {
            "Low": "priority-low",
            "Medium": "priority-med",
            "High": "priority-high"
        }.get(row["priority"], "priority-med")
        st.markdown(
            f"<div class='task-row'>"
            f"📝 {row['name']} &nbsp; | 👤 {row['owner']} &nbsp; "
            f"| <span class='badge {status_class}'>{row['status']}</span> &nbsp; "
            f"| 📅 {row['due']} &nbsp; "
            f"| <span class='badge {priority_class}'>{row['priority']}</span>"
            f"</div>",
            unsafe_allow_html=True
        )
