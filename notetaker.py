import streamlit as st
import pandas as pd
import sqlite3
import uuid
from datetime import datetime

# ---------------- CONFIG ----------------
st.set_page_config(page_title="IWMP - Smartsheet Style", layout="wide")
st.title("🧠 Intelligent Work Management Platform")

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
    return pd.read_sql("SELECT * FROM notes WHERE task_id=? ORDER BY created_at ASC", conn, params=(task_id,))

def add_task(title, type_, parent_id, assignee, status, priority, due_date):
    conn.execute("""INSERT INTO tasks (id,parent_id,title,type,assignee,status,priority,due_date,sort_order,created_at,updated_at)
                 VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                 (uid(), parent_id, title, type_, assignee, status, priority,
                  str(due_date) if due_date else None,
                  0, now(), now()))
    conn.commit()

def update_task(task_id, **fields):
    sets, vals = [], []
    for k,v in fields.items():
        sets.append(f"{k}=?")
        vals.append(v)
    if sets:
        vals.extend([now(), task_id])
        sql = f"UPDATE tasks SET {', '.join(sets)}, updated_at=? WHERE id=?"
        conn.execute(sql, vals)
        conn.commit()

def delete_task(task_id):
    conn.execute("DELETE FROM tasks WHERE id=?", (task_id,))
    conn.commit()

def add_note(task_id, content):
    conn.execute("INSERT INTO notes (id,task_id,content,created_at) VALUES (?,?,?,?)",
                 (uid(), task_id, content, now()))
    conn.commit()

# ---------------- DATA ----------------
df = fetch_tasks()
row_map = {r["id"]: r for _,r in df.iterrows()}

children = {}
for _,r in df.iterrows():
    children.setdefault(r["parent_id"], []).append(r["id"])

# ---------------- Quick Add ----------------
st.subheader("➕ Quick Add")
col1,col2,col3 = st.columns([3,1,3])
with col1: title_new = st.text_input("Title", key="newtitle")
with col2: type_new = st.selectbox("Type", ["task","section"], key="newtype")
with col3:
    parent_opts = {"(root)": None}
    for _, r in df[df["type"]=="section"].iterrows():
        parent_opts[f"{r['title']} ({r['id'][:4]})"] = r["id"]
    parent_choice = st.selectbox("Parent", list(parent_opts.keys()), key="newparent")
parent_id = parent_opts[parent_choice]
if st.button("Add"):
    if title_new.strip():
        add_task(title_new, type_new, parent_id, "", "todo", "medium", None)
        st.rerun()

st.divider()

# ---------------- Grid Header ----------------
st.markdown("### 📋 Work Grid")
h1,h2,h3,h4,h5,h6,h7,h8 = st.columns([3,2,2,2,2,1,3,1])
with h1: st.markdown("**Title**")
with h2: st.markdown("**👤 Assignee**")
with h3: st.markdown("**⏱ Status**")
with h4: st.markdown("**🚩 Priority**")
with h5: st.markdown("**📅 Due**")
with h6: st.markdown("**🗑️**")
with h7: st.markdown("**💬 Notes**")
with h8: st.markdown("**✏️ Edit**")

# ---------------- Render Tree ----------------
def render(parent=None, level=0):
    for tid in children.get(parent, []):
        r = row_map[tid]

        if r["type"]=="section":
            cols = st.columns([7,1])
            with cols[0]:
                expanded = st.toggle(f"📂 {r['title']}", key=f"toggle_{tid}", value=False)
            with cols[1]:
                if st.button("🗑️", key=f"del_sec_{tid}"):
                    delete_task(tid)
                    st.rerun()

            if expanded:
                render(tid, level+1)

                # Inline Add
                with st.expander(f"➕ Add inside {r['title']}", expanded=False):
                    title_child = st.text_input("Title", key=f"addtitle_{tid}")
                    type_child = st.radio("Type", ["task", "section"], key=f"addtype_{tid}", horizontal=True)
                    if st.button("Add", key=f"addbtn_{tid}"):
                        if title_child.strip():
                            add_task(title_child, type_child, r["id"], "", "todo", "medium", None)
                            st.rerun()

        else:  # Task row
            c1,c2,c3,c4,c5,c6,c7,c8 = st.columns([3,2,2,2,2,1,3,1])
            edit_key = f"edit_{tid}"

            if edit_key not in st.session_state:
                st.session_state[edit_key] = {"mode": "view"}

            mode = st.session_state[edit_key]["mode"]

            if mode == "edit":
                # Editable fields
                new_title = c1.text_input("", value=r["title"], key=f"title_{tid}")
                assignee = c2.text_input("", value=r.get("assignee") or "", key=f"asg_{tid}")
                status = c3.selectbox("", STATUS_OPTS, index=STATUS_OPTS.index(r.get("status") or "todo"), key=f"st_{tid}")
                priority = c4.selectbox("", PRIORITY_OPTS, index=PRIORITY_OPTS.index(r.get("priority") or "medium"), key=f"pr_{tid}")
                due = pd.to_datetime(r.get("due_date"), errors="coerce").date() if r.get("due_date") else None
                due_new = c5.date_input("", value=due, key=f"due_{tid}")

                if c6.button("🗑️", key=f"del_{tid}"):
                    delete_task(tid); st.rerun()

                # Notes
                with c7.expander("💬 Notes", expanded=False):
                    notes = fetch_notes(tid)
                    if notes.empty:
                        st.caption("No notes yet.")
                    else:
                        for _, n in notes.iterrows():
                            st.markdown(f"**{r.get('assignee') or 'User'}:** {n['content']}  \n<small>🕒 {n['created_at']}</small>", unsafe_allow_html=True)

                    input_key = f"convnote_{tid}"
                    note_val = st.text_input("Type a note...", key=input_key, placeholder="Write a message...")
                    if st.button("Send", key=f"sendnote_{tid}"):
                        if note_val.strip():
                            add_note(tid, note_val.strip())
                            st.session_state.pop(input_key, None)
                            st.rerun()

                # Save / Cancel
                colsave, colcancel = c8.columns(2)
                with colsave:
                    if st.button("💾", key=f"save_{tid}"):
                        update_task(tid, title=new_title, assignee=assignee, status=status,
                                    priority=priority, due_date=str(due_new) if due_new else None)
                        st.session_state[edit_key]["mode"] = "view"
                        st.rerun()
                with colcancel:
                    if st.button("❌", key=f"cancel_{tid}"):
                        st.session_state[edit_key]["mode"] = "view"
                        st.rerun()

            else:
                # View mode
                c1.markdown(r["title"])
                c2.markdown(r.get("assignee") or "")
                c3.markdown(r.get("status") or "")
                c4.markdown(r.get("priority") or "")
                c5.markdown(r.get("due_date") or "")
                if c6.button("🗑️", key=f"delv_{tid}"):
                    delete_task(tid); st.rerun()

                with c7.expander("💬 Notes", expanded=False):
                    notes = fetch_notes(tid)
                    if notes.empty:
                        st.caption("No notes yet.")
                    else:
                        for _, n in notes.iterrows():
                            st.markdown(f"**{r.get('assignee') or 'User'}:** {n['content']}  \n<small>🕒 {n['created_at']}</small>", unsafe_allow_html=True)

                    input_key = f"convnote_{tid}"
                    note_val = st.text_input("Type a note...", key=input_key, placeholder="Write a message...")
                    if st.button("Send", key=f"sendnotev_{tid}"):
                        if note_val.strip():
                            add_note(tid, note_val.strip())
                            st.session_state.pop(input_key, None)
                            st.rerun()

                if c8.button("✏️", key=f"editbtn_{tid}"):
                    st.session_state[edit_key]["mode"] = "edit"
                    st.rerun()

render()
