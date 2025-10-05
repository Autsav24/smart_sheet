import streamlit as st
import pandas as pd
import sqlite3
import uuid
from datetime import datetime, date
from typing import Optional, List, Dict
from streamlit_sortables import sort_items

# ---------------- CONFIG ----------------
st.set_page_config(page_title="IWMP - Smartsheet Style", layout="wide")
st.title("🧠 Intelligent Work Management Platform")

if "expanded_sections" not in st.session_state:
    st.session_state["expanded_sections"] = set()

# ---------------- DB ----------------
def get_conn():
    conn = sqlite3.connect("iwmp_grid.db", check_same_thread=False)
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

conn = get_conn()

def ensure_schema():
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS tasks (
        id TEXT PRIMARY KEY,
        parent_id TEXT REFERENCES tasks(id) ON DELETE CASCADE,
        title TEXT NOT NULL,
        type TEXT CHECK (type IN ('section','task')) DEFAULT 'task',
        assignee TEXT,
        status TEXT,
        priority TEXT,
        due_date TEXT,
        sort_order INTEGER DEFAULT 0,
        created_at TEXT,
        updated_at TEXT
    )""")
    cur.execute("""
    CREATE TABLE IF NOT EXISTS notes (
        id TEXT PRIMARY KEY,
        task_id TEXT REFERENCES tasks(id) ON DELETE CASCADE,
        content TEXT,
        created_at TEXT
    )""")
    conn.commit()

ensure_schema()

# ---------------- HELPERS ----------------
def uid(): return str(uuid.uuid4())
def now(): return datetime.utcnow().isoformat()

STATUS_OPTS = ["todo", "doing", "done", "blocked"]
PRIORITY_OPTS = ["low", "medium", "high", "critical"]

def fetch_tasks():
    return pd.read_sql("SELECT * FROM tasks ORDER BY parent_id, sort_order", conn)

def fetch_notes(task_id):
    return pd.read_sql("SELECT * FROM notes WHERE task_id=? ORDER BY created_at DESC", conn, params=(task_id,))

def add_task(title, type_, parent_id, assignee, status, priority, due_date):
    conn.execute("""INSERT INTO tasks (id,parent_id,title,type,assignee,status,priority,due_date,sort_order,created_at,updated_at)
                 VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                 (uid(), parent_id, title, type_, assignee, status, priority,
                  str(due_date) if due_date else None,
                  0, now(), now()))
    conn.commit()

def update_task(task_id, **fields):
    sets = []
    params = {}
    for k,v in fields.items():
        sets.append(f"{k}=?")
        params[k] = v
    if sets:
        sql = f"UPDATE tasks SET {', '.join(sets)}, updated_at=? WHERE id=?"
        vals = list(params.values())+[now(), task_id]
        conn.execute(sql, vals)
        conn.commit()

def delete_task(task_id):
    conn.execute("DELETE FROM tasks WHERE id=?", (task_id,))
    conn.commit()

def add_note(task_id, content):
    conn.execute("INSERT INTO notes (id,task_id,content,created_at) VALUES (?,?,?,?)",
                 (uid(), task_id, content, now()))
    conn.commit()

# ---------------- UI ----------------
df = fetch_tasks()
row_map = {r["id"]: r for _,r in df.iterrows()}
children = {}
for _,r in df.iterrows():
    children.setdefault(r["parent_id"], []).append(r["id"])

# Quick add bar
st.subheader("➕ Quick Add")
col1,col2,col3 = st.columns([3,1,2])
with col1: title_new = st.text_input("Title", key="newtitle")
with col2: type_new = st.selectbox("Type", ["task","section"], key="newtype")
with col3: parent = st.selectbox("Parent", ["(root)"]+[row_map[i]["title"] for i in df[df["type"]=="section"]["id"]],
                                 key="newparent")
parent_id = None if parent=="(root)" else [k for k,v in row_map.items() if v["title"]==parent][0] if df.size>0 else None
if st.button("Add"):
    if title_new.strip():
        add_task(title_new, type_new, parent_id, "", "todo", "medium", None)
        st.rerun()

st.divider()

# Render tree
def render(parent=None, level=0):
    for tid in children.get(parent, []):
        r = row_map[tid]
        indent = "&nbsp;"* (level*6)
        if r["type"]=="section":
            expanded = tid in st.session_state["expanded_sections"]
            icon = "▼" if expanded else "▶"
            if st.button(f"{icon} 📂 {r['title']}", key=f"sec_{tid}"):
                if expanded: st.session_state["expanded_sections"].remove(tid)
                else: st.session_state["expanded_sections"].add(tid)
                st.rerun()
            if expanded: render(tid, level+1)
        else:
            # Task row
            c1,c2,c3,c4,c5,c6,c7 = st.columns([3,2,2,2,2,2,2])
            with c1:
                new_title = st.text_input("Title", value=r["title"], key=f"title_{tid}")
                if new_title!=r["title"]: update_task(tid, title=new_title)
            with c2:
                assignee = st.text_input("👤", value=r.get("assignee") or "", key=f"asg_{tid}")
                if assignee!=(r.get("assignee") or ""): update_task(tid, assignee=assignee)
            with c3:
                status = st.selectbox("⏱", STATUS_OPTS, index=STATUS_OPTS.index(r.get("status") or "todo"), key=f"st_{tid}")
                if status!=(r.get("status") or "todo"): update_task(tid, status=status)
            with c4:
                priority = st.selectbox("🚩", PRIORITY_OPTS, index=PRIORITY_OPTS.index(r.get("priority") or "medium"), key=f"pr_{tid}")
                if priority!=(r.get("priority") or "medium"): update_task(tid, priority=priority)
            with c5:
                due = pd.to_datetime(r.get("due_date"), errors="coerce").date() if r.get("due_date") else None
                due_new = st.date_input("📅", value=due, key=f"due_{tid}")
                if due_new!=(due): update_task(tid, due_date=str(due_new) if due_new else None)
            with c6:
                if st.button("🗑️", key=f"del_{tid}"):
                    delete_task(tid); st.rerun()
            with c7:
                note = st.text_input("➕ Note", key=f"note_{tid}")
                if note:
                    add_note(tid, note); st.rerun()
            # show last note
            notes = fetch_notes(tid)
            if not notes.empty:
                st.caption(f"📝 Last: {notes.iloc[0]['content']} ({notes.iloc[0]['created_at']})")

render()
