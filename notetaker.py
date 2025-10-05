import streamlit as st
import pandas as pd
import sqlite3
import uuid
from datetime import datetime

st.set_page_config(page_title="Smartsheet-like Grid", layout="wide")

# DB
conn = sqlite3.connect("smartsheet.db")
c = conn.cursor()
c.execute("""
CREATE TABLE IF NOT EXISTS items (
  id TEXT PRIMARY KEY,
  parent_id TEXT REFERENCES items(id) ON DELETE CASCADE,
  title TEXT NOT NULL,
  type TEXT CHECK (type IN ('section','task')) DEFAULT 'task',
  assignee TEXT,
  status TEXT,
  priority TEXT,
  start_date TEXT,
  due_date TEXT,
  level INT DEFAULT 0,
  created_at TEXT,
  updated_at TEXT
)
""")
conn.commit()

def uid(): return str(uuid.uuid4())

def add_item(title, type="task", parent_id=None, level=0):
    now = datetime.utcnow().isoformat()
    conn.execute("""
        INSERT INTO items (id, parent_id, title, type, level, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (uid(), parent_id, title, type, level, now, now))
    conn.commit()

def delete_item(item_id):
    conn.execute("DELETE FROM items WHERE id=?", (item_id,))
    conn.commit()

def fetch_items():
    return pd.read_sql("SELECT * FROM items ORDER BY created_at", conn)

def render_for_editor(df):
    # Indent task titles
    df = df.copy()
    df["display_title"] = df.apply(
        lambda r: ("    " * r["level"] + ("📂 " if r["type"]=="section" else "📝 ") + r["title"]),
        axis=1
    )
    return df

# ---------------- UI -------------------
st.title("📋 Smartsheet-like Grid")

with st.expander("➕ Add Item"):
    title = st.text_input("Title")
    type_choice = st.radio("Type", ["section","task"], horizontal=True)
    df_all = fetch_items()
    parent_options = ["None"] + df_all["title"].tolist()
    parent_title = st.selectbox("Parent", parent_options)
    parent_id = None if parent_title=="None" else df_all[df_all["title"]==parent_title]["id"].iloc[0]
    parent_level = 0 if parent_id is None else int(df_all[df_all["id"]==parent_id]["level"].iloc[0]) + 1
    if st.button("Add"):
        if title.strip():
            add_item(title, type_choice, parent_id, parent_level)
            st.rerun()

df = fetch_items()
if df.empty:
    st.info("No items yet. Add one above.")
else:
    df_view = render_for_editor(df)

    edited = st.data_editor(
        df_view,
        column_config={
            "display_title": st.column_config.TextColumn("Title"),
            "assignee": st.column_config.TextColumn("Assignee"),
            "status": st.column_config.SelectboxColumn("Status", options=["todo","doing","done","blocked"]),
            "priority": st.column_config.SelectboxColumn("Priority", options=["low","medium","high","critical"]),
            "start_date": st.column_config.DateColumn("Start"),
            "due_date": st.column_config.DateColumn("Due")
        },
        hide_index=True,
        disabled=["display_title"], # title shown with indent, not directly editable
        use_container_width=True
    )

    # Delete row buttons
    for _, row in df.iterrows():
        if st.button("🗑️", key=f"del_{row['id']}"):
            delete_item(row["id"])
            st.rerun()
