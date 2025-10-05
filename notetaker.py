import streamlit as st
import pandas as pd
import sqlite3
import uuid
from datetime import datetime, date
from typing import Optional, List, Dict, Set
from streamlit_sortables import sort_items  # drag & drop

# -------------------- App Config --------------------
st.set_page_config(page_title="Intelligent Work Management - Grid", layout="wide")
st.title("🧠 Intelligent Work Management Platform — Grid")

# Session state for jump-to-notes
if "selected_task" not in st.session_state:
    st.session_state["selected_task"] = None

# -------------------- DB Setup ----------------------
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
            start_date TEXT,
            due_date TEXT,
            sort_order INTEGER DEFAULT 0,
            created_at TEXT,
            updated_at TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS notes (
            id TEXT PRIMARY KEY,
            task_id TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
            content TEXT NOT NULL,
            created_at TEXT
        )
    """)
    # add missing columns if migrating
    cols = pd.read_sql("PRAGMA table_info(tasks)", conn)["name"].tolist()
    if "sort_order" not in cols:
        cur.execute("ALTER TABLE tasks ADD COLUMN sort_order INTEGER DEFAULT 0")
    conn.commit()

ensure_schema()

# -------------------- Helpers -----------------------
def uid() -> str:
    return str(uuid.uuid4())

STATUS_OPTS = ["todo", "doing", "done", "blocked"]
PRIORITY_OPTS = ["low", "medium", "high", "critical"]

def now() -> str:
    return datetime.utcnow().isoformat()

def fetch_tasks_df() -> pd.DataFrame:
    return pd.read_sql("""
        SELECT * FROM tasks
        ORDER BY parent_id IS NOT NULL, sort_order, created_at
    """, conn)

def fetch_notes(task_id: str) -> pd.DataFrame:
    return pd.read_sql("SELECT * FROM notes WHERE task_id=? ORDER BY created_at DESC", conn, params=(task_id,))

def add_note(task_id: str, content: str):
    conn.execute("INSERT INTO notes (id, task_id, content, created_at) VALUES (?, ?, ?, ?)",
                 (uid(), task_id, content.strip(), now()))
    conn.commit()

def next_sort_order(parent_id: Optional[str]) -> int:
    row = pd.read_sql("SELECT COALESCE(MAX(sort_order), -1) AS maxo FROM tasks WHERE parent_id IS ?", conn, params=(parent_id,)).iloc[0]
    return int(row["maxo"]) + 1

def add_item(title: str, type_: str, parent_id: Optional[str], assignee: str, status: str, priority: str,
             start_date: Optional[date], due_date: Optional[date]):
    conn.execute("""
        INSERT INTO tasks (id, parent_id, title, type, assignee, status, priority, start_date, due_date, sort_order, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        uid(), parent_id, title.strip(), type_, assignee.strip(), status, priority,
        str(start_date) if start_date else None,
        str(due_date) if due_date else None,
        next_sort_order(parent_id),
        now(), now()
    ))
    conn.commit()

def delete_item(item_id: str):
    conn.execute("DELETE FROM tasks WHERE id=?", (item_id,))
    conn.commit()

def move_item(item_id: str, new_parent_id: Optional[str]):
    conn.execute("UPDATE tasks SET parent_id=?, sort_order=?, updated_at=? WHERE id=?",
                 (new_parent_id, next_sort_order(new_parent_id), now(), item_id))
    conn.commit()

def update_children_sort(parent_id: Optional[str], ordered_ids: List[str]):
    for idx, tid in enumerate(ordered_ids):
        conn.execute("UPDATE tasks SET sort_order=?, updated_at=? WHERE id=?", (idx, now(), tid))
    conn.commit()

def update_item_fields(item_id: str, *,  # inline edit saver
                       title: Optional[str] = None,
                       assignee: Optional[str] = None,
                       status: Optional[str] = None,
                       priority: Optional[str] = None,
                       start_date: Optional[date] = None,
                       due_date: Optional[date] = None):
    sets = []
    params = {}
    if title is not None:
        sets.append("title=:title")
        params["title"] = title.strip()
    if assignee is not None:
        sets.append("assignee=:assignee")
        params["assignee"] = assignee.strip()
    if status is not None:
        sets.append("status=:status")
        params["status"] = status
    if priority is not None:
        sets.append("priority=:priority")
        params["priority"] = priority
    if start_date is not None:
        sets.append("start_date=:start_date")
        params["start_date"] = str(start_date) if start_date else None
    if due_date is not None:
        sets.append("due_date=:due_date")
        params["due_date"] = str(due_date) if due_date else None

    if sets:
        sets.append("updated_at=:ua")
        params["ua"] = now()
        sql = f"UPDATE tasks SET {', '.join(sets)} WHERE id=:id"
        params["id"] = item_id
        conn.execute(sql, params)
        conn.commit()

# ----- Tree utilities -----
def build_index(df: pd.DataFrame) -> Dict[str, List[str]]:
    df = df.copy()
    df.sort_values(["sort_order", "created_at"], inplace=True)
    idx: Dict[str, List[str]] = {}
    for _, r in df.iterrows():
        pid = r["parent_id"]
        idx.setdefault(pid, []).append(r["id"])
    return idx

def ancestors(df: pd.DataFrame, item_id: str) -> List[str]:
    out: List[str] = []
    row_map = {r["id"]: r for _, r in df.iterrows()}
    cur = item_id
    while True:
        row = row_map.get(cur)
        if row is None:
            break
        pid = row["parent_id"]
        if pd.isna(pid):
            break
        out.append(pid)
        cur = pid
    return out

def breadcrumb(df: pd.DataFrame, item_id: str) -> str:
    row_map = {r["id"]: r for _, r in df.iterrows()}
    parts = []
    cur = item_id
    while True:
        row = row_map.get(cur)
        if row is None:
            break
        parts.append(str(row["title"]))
        pid = row["parent_id"]
        if pd.isna(pid):
            break
        cur = pid
    return " / ".join(reversed(parts))

# -------------------- Dashboard ---------------------
df_all = fetch_tasks_df()

if not df_all.empty:
    critical_count = (df_all["priority"] == "critical").sum()
    medium_count = (df_all["priority"] == "medium").sum()
    done_count = (df_all["status"] == "done").sum()

    dc = df_all.dropna(subset=["due_date"]).copy()
    dc["due_date_d"] = pd.to_datetime(dc["due_date"], errors="coerce").dt.date
    overdue_critical_df = dc[(dc["priority"] == "critical") &
                             (dc["status"] != "done") &
                             (dc["due_date_d"] < date.today())]
    overdue_count = len(overdue_critical_df)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("🔥 Critical", int(critical_count))
    c2.metric("⚠️ Medium", int(medium_count))
    c3.metric("✅ Done", int(done_count))
    c4.metric("⚡ Overdue Critical", int(overdue_count))

    st.divider()

    if overdue_count > 0:
        st.subheader("⚡ Overdue Critical Tasks")
        for _, row in overdue_critical_df.iterrows():
            if st.button(f"🔴 {row['title']}  (👤 {row.get('assignee','')} • 📅 {row.get('due_date','')})",
                         key=f"jump_{row['id']}"):
                st.session_state["selected_task"] = row["id"]
                st.rerun()
    else:
        st.success("✅ No overdue critical tasks — great job!")
else:
    overdue_critical_df = pd.DataFrame()
    overdue_count = 0

st.divider()

# -------------------- Add Item ----------------------
with st.expander("➕ Add Section / Task", expanded=False):
    colA, colB, colC, colD = st.columns([3, 2, 2, 2])
    with colA:
        title_new = st.text_input("Title")
        type_new = st.radio("Type", ["section", "task"], horizontal=True)
    with colB:
        assignee_new = st.text_input("Assignee (optional)")
        status_new = st.selectbox("Status", STATUS_OPTS, index=0)
    with colC:
        priority_new = st.selectbox("Priority", PRIORITY_OPTS, index=1)
        start_new = st.date_input("Start date", value=None)
    with colD:
        due_new = st.date_input("Due date", value=None)

    df_all = fetch_tasks_df()
    parent_choices = ["(root)"]
    id_map = {}
    for _, r in df_all.iterrows():
        label = breadcrumb(df_all, r["id"])
        parent_choices.append(label)
        id_map[label] = r["id"]
    sel_parent_label = st.selectbox("Parent", parent_choices)
    sel_parent_id = None if sel_parent_label == "(root)" else id_map[sel_parent_label]

    if st.button("Add", type="primary"):
        if not title_new.strip():
            st.error("Title is required.")
        else:
            add_item(title_new, type_new, sel_parent_id, assignee_new, status_new, priority_new, start_new, due_new)
            st.success("Added")
            st.rerun()

# -------------------- Grid Filters ------------------
st.subheader("📋 Grid")
filter_choice = st.selectbox("Filter", ["All", "Critical", "Medium", "Done"], index=0)

df_all = fetch_tasks_df()

visible_ids: Set[str] = set(df_all["id"].tolist())
if filter_choice != "All":
    filtered = df_all.copy()
    if filter_choice == "Critical":
        filtered = filtered[filtered["priority"] == "critical"]
    elif filter_choice == "Medium":
        filtered = filtered[filtered["priority"] == "medium"]
    elif filter_choice == "Done":
        filtered = filtered[filtered["status"] == "done"]
    visible_ids = set(filtered["id"].tolist())
    for tid in list(visible_ids):
        for anc in ancestors(df_all, tid):
            visible_ids.add(anc)

# -------------------- Render Tree -------------------
index = build_index(df_all)
row_map = {r["id"]: r for _, r in df_all.iterrows()}

def row_label(r: pd.Series, level: int) -> str:
    indent = "&nbsp;" * (level * 6)
    icon = "📂" if r["type"] == "section" else "📝"
    highlight = ""
    if r["type"] == "task":
        try:
            if r["priority"] == "critical" and r["status"] != "done" and r["due_date"]:
                due_d = pd.to_datetime(r["due_date"], errors="coerce").date()
                if due_d and due_d < date.today():
                    highlight = "background-color:#ffebeb; border-radius:4px; padding:2px 6px;"
        except Exception:
            pass
    left = f"{indent}{icon} <b>{r['title']}</b>"
    meta = f" — 👤 {r.get('assignee','') or '-'} | ⏱ {r.get('status','-')} | 🚩 {r.get('priority','-')}"
    style = f"style='{highlight}'" if highlight else ""
    return f"<div {style}>{left}{meta}</div>"

def descendants_have_visible(section_id: str) -> bool:
    stack = [section_id]
    while stack:
        cur = stack.pop()
        for ch in index.get(cur, []):
            if ch in visible_ids:
                return True
            stack.append(ch)
    return False

def render_subtree(parent_id: Optional[str], level: int = 0):
    children = index.get(parent_id, [])
    sects = [cid for cid in children if row_map[cid]["type"] == "section"]
    tasks = [cid for cid in children if row_map[cid]["type"] == "task"]

    # --- Sections ---
    for cid in sects:
        r = row_map[cid]
        if cid not in visible_ids and not descendants_have_visible(cid):
            continue
        st.markdown(row_label(r, level), unsafe_allow_html=True)

        # Action row: Delete | Move | Edit
        ac1, ac2, ac3, ac4 = st.columns([4, 1, 2, 3])
        with ac2:
            if st.button("🗑️", key=f"del_{cid}"):
                delete_item(cid)
                st.rerun()
        with ac3:
            parent_choices = ["(root)"]
            id_map2 = {}
            for _, rr in df_all.iterrows():
                if rr["id"] == cid:
                    continue
                parent_choices.append(breadcrumb(df_all, rr["id"]))
                id_map2[parent_choices[-1]] = rr["id"]
            new_parent_label = st.selectbox("Move to", parent_choices, key=f"mvsel_{cid}")
            new_parent_id = None if new_parent_label == "(root)" else id_map2[new_parent_label]
            if st.button("Move", key=f"mvbtn_{cid}"):
                move_item(cid, new_parent_id)
                st.rerun()
        with ac4:
            with st.expander("✏️ Edit Section", expanded=False):
                new_title = st.text_input("Title", value=r["title"], key=f"edit_title_{cid}")
                if st.button("Save", key=f"edit_save_{cid}"):
                    if new_title.strip():
                        update_item_fields(cid, title=new_title)
                        st.success("Updated")
                        st.rerun()

        # Drag-drop children
        child_ids = index.get(cid, [])
        if child_ids:
            labels = []
            id_by_label = {}
            for ch in child_ids:
                rr = row_map[ch]
                label = f"{'📂' if rr['type']=='section' else '📝'} {rr['title']} [{ch[:6]}]"
                labels.append(label)
                id_by_label[label] = ch
            new_labels = sort_items(labels, direction="vertical", key=f"sort_{cid}")
            if new_labels != labels:
                new_order_ids = [id_by_label[lbl] for lbl in new_labels]
                update_children_sort(cid, new_order_ids)
                st.rerun()

        render_subtree(cid, level + 1)

    # --- Tasks ---
    for cid in tasks:
        if cid not in visible_ids:
            continue
        r = row_map[cid]
        st.markdown(row_label(r, level), unsafe_allow_html=True)

        # Action row: Notes | Delete | Move | Edit
        c1, c2, c3, c4 = st.columns([4, 1, 2, 3])

        with c1:
            with st.expander(f"🗒 Notes for {r['title']}", expanded=(st.session_state["selected_task"] == cid)):
                note_text = st.text_area("Add Note", key=f"note_{cid}")
                if st.button("Save Note", key=f"save_{cid}"):
                    if note_text.strip():
                        add_note(cid, note_text)
                        st.session_state["selected_task"] = cid
                        st.rerun()
                notes_df = fetch_notes(cid)
                if notes_df.empty:
                    st.caption("No notes yet.")
                else:
                    for _, n in notes_df.iterrows():
                        st.markdown(f"- {n['content']}  \n  <small>🕒 {n['created_at']}</small>", unsafe_allow_html=True)

        with c2:
            if st.button("🗑️", key=f"del_{cid}"):
                delete_item(cid)
                st.rerun()

        with c3:
            parent_choices = ["(root)"]
            id_map2 = {}
            for _, rr in df_all.iterrows():
                if rr["id"] == cid:
                    continue
                parent_choices.append(breadcrumb(df_all, rr["id"]))
                id_map2[parent_choices[-1]] = rr["id"]
            new_parent_label = st.selectbox("Move to", parent_choices, key=f"mvsel_{cid}")
            new_parent_id = None if new_parent_label == "(root)" else id_map2[new_parent_label]
            if st.button("Move", key=f"mvbtn_{cid}"):
                move_item(cid, new_parent_id)
                st.rerun()

        with c4:
            with st.expander("✏️ Edit Task", expanded=False):
                et_title = st.text_input("Title", value=r["title"], key=f"et_title_{cid}")
                et_assignee = st.text_input("Assignee", value=r.get("assignee") or "", key=f"et_assignee_{cid}")
                et_status = st.selectbox("Status", STATUS_OPTS,
                                         index=max(0, STATUS_OPTS.index(r.get("status") or "todo")),
                                         key=f"et_status_{cid}")
                et_priority = st.selectbox("Priority", PRIORITY_OPTS,
                                           index=max(0, PRIORITY_OPTS.index(r.get("priority") or "medium")),
                                           key=f"et_priority_{cid}")
                # Parse dates safely
                def parse_date(val):
                    if val:
                        try:
                            return pd.to_datetime(val, errors="coerce").date()
                        except Exception:
                            return None
                    return None
                et_start = st.date_input("Start date", value=parse_date(r.get("start_date")), key=f"et_start_{cid}")
                et_due = st.date_input("Due date", value=parse_date(r.get("due_date")), key=f"et_due_{cid}")

                if st.button("Save", key=f"et_save_{cid}"):
                    update_item_fields(
                        cid,
                        title=et_title,
                        assignee=et_assignee,
                        status=et_status,
                        priority=et_priority,
                        start_date=et_start,
                        due_date=et_due
                    )
                    st.success("Updated")
                    st.rerun()

# Render root
render_subtree(None, 0)
