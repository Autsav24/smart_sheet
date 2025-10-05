import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime, date

# -------------------------------
# App Config & Constants
# -------------------------------
st.set_page_config(page_title="SmartSheet-like (Tree View)", layout="wide")

STATUS_OPTIONS = ["Not Started", "In Progress", "Done"]
PRIORITY_OPTIONS = ["Low", "Medium", "High"]

# -------------------------------
# DB Helpers
# -------------------------------
def get_conn():
    conn = sqlite3.connect("tasks.db", check_same_thread=False)
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def ensure_db():
    conn = get_conn()
    c = conn.cursor()
    # Sections table
    c.execute("""
        CREATE TABLE IF NOT EXISTS sections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            sort_order INTEGER NOT NULL DEFAULT 0
        )
    """)
    # Tasks table with FK to sections
    c.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            section_id INTEGER NOT NULL,
            task TEXT NOT NULL,
            owner TEXT,
            status TEXT,
            due_date TEXT,
            priority TEXT,
            updated_by TEXT,
            updated_at TEXT,
            FOREIGN KEY(section_id) REFERENCES sections(id) ON DELETE CASCADE
        )
    """)
    conn.commit()
    conn.close()

def fetch_sections():
    conn = get_conn()
    df = pd.read_sql_query("SELECT id, name, sort_order FROM sections ORDER BY sort_order, name", conn)
    conn.close()
    return df

def fetch_tasks(section_id: int | None = None):
    conn = get_conn()
    if section_id is None:
        q = """
            SELECT t.id, s.name AS section, t.section_id, t.task, t.owner, t.status,
                   t.due_date, t.priority, t.updated_by, t.updated_at
            FROM tasks t
            JOIN sections s ON s.id = t.section_id
            ORDER BY s.sort_order, s.name, t.id DESC
        """
        df = pd.read_sql_query(q, conn)
    else:
        q = """
            SELECT id, section_id, task, owner, status, due_date, priority, updated_by, updated_at
            FROM tasks
            WHERE section_id = ?
            ORDER BY id DESC
        """
        df = pd.read_sql_query(q, conn, params=(section_id,))
    conn.close()
    return df

def add_section(name: str):
    conn = get_conn()
    c = conn.cursor()
    # place newly added section at the end
    c.execute("SELECT COALESCE(MAX(sort_order), 0) + 1 FROM sections")
    next_order = c.fetchone()[0]
    c.execute("INSERT INTO sections (name, sort_order) VALUES (?, ?)", (name.strip(), next_order))
    conn.commit()
    conn.close()

def update_section(section_id: int, new_name: str | None = None, new_order: int | None = None):
    conn = get_conn()
    c = conn.cursor()
    if new_name is not None:
        c.execute("UPDATE sections SET name = ? WHERE id = ?", (new_name.strip(), section_id))
    if new_order is not None:
        c.execute("UPDATE sections SET sort_order = ? WHERE id = ?", (new_order, section_id))
    conn.commit()
    conn.close()

def delete_section(section_id: int):
    conn = get_conn()
    c = conn.cursor()
    c.execute("DELETE FROM sections WHERE id = ?", (section_id,))
    conn.commit()
    conn.close()

def add_task(section_id: int, task: str, owner: str, status: str, due_date_obj: date, priority: str, user="guest"):
    conn = get_conn()
    c = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute(
        """INSERT INTO tasks (section_id, task, owner, status, due_date, priority, updated_by, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (section_id, task.strip(), owner.strip(), status, str(due_date_obj), priority, user, now)
    )
    conn.commit()
    conn.close()

def update_task_row(row: dict):
    # row keys: id, section_id, task, owner, status, due_date (as date), priority
    conn = get_conn()
    c = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    # Convert date to text if needed
    due_txt = str(row.get("due_date")) if row.get("due_date") else None
    c.execute(
        """UPDATE tasks
           SET task = ?, owner = ?, status = ?, due_date = ?, priority = ?, updated_by = ?, updated_at = ?
           WHERE id = ?""",
        (
            row.get("task", "").strip(),
            (row.get("owner") or "").strip(),
            row.get("status"),
            due_txt,
            row.get("priority"),
            "guest",
            now,
            int(row["id"]),
        ),
    )
    conn.commit()
    conn.close()

def delete_task(task_id: int):
    conn = get_conn()
    c = conn.cursor()
    c.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    conn.commit()
    conn.close()

# -------------------------------
# One-time DB init
# -------------------------------
ensure_db()

# -------------------------------
# Sidebar: Sections Management
# -------------------------------
st.sidebar.header("📁 Sections")
sec_df = fetch_sections()

with st.sidebar.expander("➕ Add Section"):
    new_sec_name = st.text_input("Section name", key="add_sec_name")
    if st.button("Add", key="btn_add_section") and new_sec_name.strip():
        try:
            add_section(new_sec_name)
            st.success(f"Added section: {new_sec_name}")
            st.rerun()
        except sqlite3.IntegrityError:
            st.error("Section name must be unique.")

if not sec_df.empty:
    with st.sidebar.expander("✏️ Rename / Reorder / Delete"):
        # Editable listing for sections
        for _, row in sec_df.iterrows():
            col1, col2, col3, col4 = st.columns([3, 2, 2, 2])
            with col1:
                new_name = st.text_input("Name", value=row["name"], key=f"sec_name_{row['id']}")
            with col2:
                order = st.number_input("Order", value=int(row["sort_order"]), step=1, key=f"sec_order_{row['id']}")
            with col3:
                if st.button("Save", key=f"sec_save_{row['id']}"):
                    update_section(int(row["id"]), new_name, int(order))
                    st.success("Saved")
                    st.rerun()
            with col4:
                if st.button("Delete", key=f"sec_del_{row['id']}"):
                    delete_section(int(row["id"]))
                    st.warning("Section deleted (tasks removed).")
                    st.rerun()

# -------------------------------
# Tabs
# -------------------------------
tab_tree, tab_add_task, tab_grid = st.tabs(["🌲 Tree View", "➕ Add Task", "📋 Grid View"])

# -------------------------------
# Add Task Tab
# -------------------------------
with tab_add_task:
    st.subheader("Add a Task")
    sec_df = fetch_sections()
    if sec_df.empty:
        st.info("Create a section first in the sidebar.")
    else:
        colA, colB = st.columns([2, 1])
        with colA:
            section_name = st.selectbox("Section", options=sec_df["name"].tolist(), index=0)
            section_id = int(sec_df[sec_df["name"] == section_name]["id"].iloc[0])
            task = st.text_input("Task title")
            owner = st.text_input("Owner")
        with colB:
            status = st.selectbox("Status", STATUS_OPTIONS, index=0)
            priority = st.selectbox("Priority", PRIORITY_OPTIONS, index=1)
            due = st.date_input("Due date", value=date.today())
        if st.button("Create Task", type="primary"):
            if task.strip():
                add_task(section_id, task, owner, status, due, priority)
                st.success("Task added")
                st.rerun()
            else:
                st.warning("Task title is required.")

# -------------------------------
# Tree View Tab
# -------------------------------
with tab_tree:
    st.subheader("Sections & Tasks (Tree)")
    sec_df = fetch_sections()
    if sec_df.empty:
        st.info("No sections yet. Add one from the sidebar.")
    else:
        for _, srow in sec_df.iterrows():
            with st.expander(f"📂 {srow['name']}", expanded=True):
                tdf = fetch_tasks(section_id=int(srow["id"]))
                # Type conversions for editor compatibility
                if not tdf.empty:
                    if "id" in tdf.columns:
                        tdf["id"] = pd.to_numeric(tdf["id"], errors="coerce").astype("Int64")
                    if "due_date" in tdf.columns:
                        tdf["due_date"] = pd.to_datetime(tdf["due_date"], errors="coerce").dt.date

                st.caption("Edit inline then click Save Changes below.")
                edited = st.data_editor(
                    tdf,
                    column_config={
                        "id": st.column_config.NumberColumn("ID", disabled=True),
                        "section_id": st.column_config.NumberColumn("Section ID", disabled=True),
                        "task": st.column_config.TextColumn("Task"),
                        "owner": st.column_config.TextColumn("Owner"),
                        "status": st.column_config.SelectboxColumn("Status", options=STATUS_OPTIONS),
                        "due_date": st.column_config.DateColumn("Due Date"),
                        "priority": st.column_config.SelectboxColumn("Priority", options=PRIORITY_OPTIONS),
                        "updated_by": st.column_config.TextColumn("Updated By", disabled=True),
                        "updated_at": st.column_config.TextColumn("Updated At", disabled=True),
                    },
                    hide_index=True,
                    num_rows="dynamic",
                    key=f"editor_sec_{srow['id']}"
                )

                save_col, add_col, del_col = st.columns([1,1,1])
                with save_col:
                    if st.button("💾 Save Changes", key=f"save_sec_{srow['id']}"):
                        # Update existing rows (those with id)
                        if not edited.empty:
                            for _, row in edited.iterrows():
                                if pd.notna(row.get("id")):
                                    update_task_row(row.to_dict())
                                else:
                                    # New row created inline → add if task name present
                                    if str(row.get("task", "")).strip():
                                        add_task(
                                            section_id=int(srow["id"]),
                                            task=row.get("task", ""),
                                            owner=row.get("owner") or "",
                                            status=row.get("status") or STATUS_OPTIONS[0],
                                            due_date_obj=row.get("due_date") or date.today(),
                                            priority=row.get("priority") or PRIORITY_OPTIONS[1],
                                        )
                        st.success("Saved.")
                        st.rerun()

                with add_col:
                    if st.button("➕ Quick Add Empty Row", key=f"quick_add_{srow['id']}"):
                        # Add a minimal task to this section
                        add_task(
                            section_id=int(srow["id"]),
                            task="New Task",
                            owner="",
                            status=STATUS_OPTIONS[0],
                            due_date_obj=date.today(),
                            priority=PRIORITY_OPTIONS[1],
                        )
                        st.rerun()

                with del_col:
                    # Provide a small delete control by ID
                    del_id = st.number_input("Delete Task ID", min_value=0, step=1, key=f"del_id_{srow['id']}")
                    if st.button("🗑️ Delete by ID", key=f"del_btn_{srow['id']}") and del_id > 0:
                        delete_task(int(del_id))
                        st.warning(f"Deleted task #{int(del_id)}")
                        st.rerun()

# -------------------------------
# Grid View Tab
# -------------------------------
with tab_grid:
    st.subheader("All Tasks (Grid)")
    all_df = fetch_tasks()
    if all_df.empty:
        st.info("No tasks yet.")
    else:
        # Style status & priority
        def style_status(val):
            return (
                "color: orange;" if val == "Not Started" else
                "color: blue;" if val == "In Progress" else
                "color: green;" if val == "Done" else ""
            )
        def style_priority(val):
            return (
                "color: green;" if val == "Low" else
                "color: orange;" if val == "Medium" else
                "color: red; font-weight: 600;" if val == "High" else ""
            )
        styled = all_df.style.map(style_status, subset=["status"]).map(style_priority, subset=["priority"])
        # st.dataframe supports width='stretch' in newer Streamlit; safe to omit for compatibility
        st.dataframe(styled, height=500)
