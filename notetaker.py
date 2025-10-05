import streamlit as st
import pandas as pd
import sqlite3
import uuid
from datetime import datetime

st.set_page_config(page_title="Work Management Grid", layout="wide")

# DB
conn = sqlite3.connect("grid.db")
c = conn.cursor()
c.execute("""
CREATE TABLE IF NOT EXISTS items (
  id TEXT PRIMARY KEY,
  parent_id TEXT REFERENCES items(id) ON DELETE CASCADE,
  title TEXT NOT NULL,
  type TEXT CHECK (type IN ('section','task')) DEFAULT 'task',
  status TEXT,
  priority TEXT,
  assignee TEXT,
  start_date TEXT,
  due_date TEXT,
  created_at TEXT,
  updated_at TEXT
)
""")
conn.commit()

def uid(): return str(uuid.uuid4())

# Add row
def add_item(title, parent_id=None, type="task"):
    now = datetime.utcnow().isoformat()
    conn.execute("INSERT INTO items (id, parent_id, title, type, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
                 (uid(), parent_id, title, type, now, now))
    conn.commit()

# Delete row
def delete_item(item_id):
    conn.execute("DELETE FROM items WHERE id=?", (item_id,))
    conn.commit()

# Fetch all
def fetch_items():
    df = pd.read_sql("SELECT * FROM items ORDER BY created_at", conn)
    return df

# Recursive render
def render_tree(df, parent_id=None, level=0):
    children = df[df["parent_id"].isna()] if parent_id is None else df[df["parent_id"] == parent_id]
    for _, row in children.iterrows():
        indent = "&nbsp;" * (level * 6)
        if row["type"] == "section":
            st.markdown(f"{indent}📂 **{row['title']}**", unsafe_allow_html=True)
        else:
            st.markdown(f"{indent}📝 {row['title']}", unsafe_allow_html=True)

        col1, col2 = st.columns([6,1])
        with col1:
            st.text_input("Edit", row["title"], key=f"edit_{row['id']}")
        with col2:
            if st.button("🗑️", key=f"del_{row['id']}"):
                delete_item(row["id"])
                st.rerun()

        # recurse into children
        render_tree(df, row["id"], level+1)

# -----------------------------
st.title("📋 Work Management Grid")

# Add section or task
with st.expander("➕ Add Item"):
    title = st.text_input("Title")
    type_choice = st.radio("Type", ["section","task"], horizontal=True)
    df = fetch_items()
    parent_options = ["None"] + df["title"].tolist()
    parent_title = st.selectbox("Parent", parent_options)
    parent_id = None if parent_title=="None" else df[df["title"]==parent_title]["id"].iloc[0] 
    if st.button("Add"):
        if title.strip():
            add_item(title, parent_id, type_choice)
            st.rerun()

# Show hierarchy
df = fetch_items()
if df.empty:
    st.info("No items yet. Add one above.")
else:
    render_tree(df)
