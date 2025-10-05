import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import date, datetime
from dateutil.relativedelta import relativedelta
from sqlalchemy import create_engine, text
import uuid

# ---------- Config ----------
st.set_page_config(page_title="Intelligent Work Management Platform", layout="wide")
DB_URL = "sqlite:///iwmp.db"  # swap to postgres if needed
engine = create_engine(DB_URL, future=True)

# ---------- Bootstrap schema ----------
DDL = """
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS tasks(
  id TEXT PRIMARY KEY,
  project_id TEXT,
  section_id TEXT,
  parent_id TEXT,
  title TEXT NOT NULL,
  description TEXT,
  status TEXT DEFAULT 'todo',
  priority TEXT DEFAULT 'medium',
  assignee TEXT,
  start_date TEXT,
  due_date TEXT,
  estimate_hours REAL,
  actual_hours REAL,
  labels TEXT,
  created_at TEXT,
  updated_at TEXT
);
"""
with engine.begin() as conn:
    for stmt in DDL.split(";"):
        s = stmt.strip()
        if s:
            conn.exec_driver_sql(s + ";")

# ---------- Helpers ----------
def uid():
    return str(uuid.uuid4())

STATUS_OPTIONS = ["backlog", "todo", "doing", "blocked", "done"]
PRIORITY_OPTIONS = ["low", "medium", "high", "critical"]

def df_tasks():
    with engine.begin() as conn:
        return pd.read_sql(text("""
            SELECT * FROM tasks
            ORDER BY COALESCE(due_date, '9999-12-31'), created_at DESC
        """), conn)

def insert_task(project_id, section_id, title, description, status, priority, assignee, start, due):
    now = datetime.utcnow().isoformat()
    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO tasks(
                id, project_id, section_id, parent_id, title, description,
                status, priority, assignee, start_date, due_date,
                estimate_hours, actual_hours, labels, created_at, updated_at
            )
            VALUES(
                :id, :pr, :sec, NULL, :ti, :de,
                :st, :pry, :assignee, :sd, :dd,
                NULL, NULL, NULL, :ca, :ua
            )
        """), dict(
            id=uid(),
            pr=project_id, sec=section_id,
            ti=title, de=description or "",
            st=status, pry=priority,
            assignee=assignee or "",
            sd=start, dd=due,
            ca=now, ua=now
        ))

def update_task_row(row):
    now = datetime.utcnow().isoformat()
    with engine.begin() as conn:
        conn.execute(text("""
            UPDATE tasks
            SET title=:ti, description=:de, status=:st, priority=:pry,
                assignee=:assignee, start_date=:sd, due_date=:dd,
                estimate_hours=:eh, actual_hours=:ah, updated_at=:ua
            WHERE id=:id
        """), dict(
            id=row["id"],
            ti=row["title"],
            de=row.get("description", ""),
            st=row["status"],
            pry=row["priority"],
            assignee=row.get("assignee", ""),
            sd=row.get("start_date"),
            dd=row.get("due_date"),
            eh=row.get("estimate_hours"),
            ah=row.get("actual_hours"),
            ua=now
        ))

def delete_task(task_id):
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM tasks WHERE id=:id"), dict(id=task_id))

# ---------- AI Stubs (replace with real provider) ----------
def ai_summarize(text_in: str) -> str:
    return (text_in or "").split("\n")[0][:220]

def ai_predict_priority(title: str, desc: str) -> str:
    s = (title + " " + (desc or "")).lower()
    if any(w in s for w in ["urgent", "blocker", "outage", "critical"]):
        return "critical"
    if any(w in s for w in ["delay", "risk", "late", "dependency"]):
        return "high"
    return "medium"

def ai_detect_blocked(title: str, desc: str) -> bool:
    s = (title + " " + (desc or "")).lower()
    return any(w in s for w in ["waiting on", "blocked", "dependency", "pending"])

# ---------- UI ----------
st.title("🧠 Intelligent Work Management Platform")

tabs = st.tabs(["📋 Grid", "🧱 Kanban", "📆 Calendar", "⚙️ Automations", "🔎 Search & AI", "📈 Insights"])

# --- Quick Add Task ---
with st.expander("➕ Quick Add Task"):
    c1, c2, c3, c4 = st.columns([3, 2, 2, 2])
    with c1:
        title = st.text_input("Title")
        desc = st.text_area("Description", height=80)
    with c2:
        status = st.selectbox("Status", STATUS_OPTIONS, index=1)
        priority = st.selectbox("Priority", PRIORITY_OPTIONS, index=1)
    with c3:
        assignee = st.text_input("Assignee")
        start = st.date_input("Start", value=date.today())
        due = st.date_input("Due", value=date.today() + relativedelta(days=7))
    with c4:
        project_id = "default-project"
        section_id = "default-section"
        if st.button("Add Task", type="primary"):
            if not desc:
                priority = ai_predict_priority(title, desc)
                if ai_detect_blocked(title, desc) and status != "done":
                    status = "blocked"
            insert_task(project_id, section_id, title, desc, status, priority, assignee, str(start), str(due))
            st.success("Task created")
            st.rerun()  # ✅ updated

# --- Grid View ---
with tabs[0]:
    st.subheader("Grid")
    df = df_tasks()
    if df.empty:
        st.info("No tasks yet.")
    else:
        for col in ["estimate_hours", "actual_hours"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        edited = st.data_editor(
            df,
            key="grid_editor",
            num_rows="dynamic",
            column_config={
                "id": st.column_config.TextColumn("ID", disabled=True),
                "title": st.column_config.TextColumn("Title"),
                "description": st.column_config.TextColumn("Description"),
                "status": st.column_config.SelectboxColumn("Status", options=STATUS_OPTIONS),
                "priority": st.column_config.SelectboxColumn("Priority", options=PRIORITY_OPTIONS),
                "assignee": st.column_config.TextColumn("Assignee"),
                "start_date": st.column_config.DateColumn("Start"),
                "due_date": st.column_config.DateColumn("Due"),
                "estimate_hours": st.column_config.NumberColumn("Est (h)"),
                "actual_hours": st.column_config.NumberColumn("Actual (h)")
            },
            hide_index=True
        )
        c1, c2 = st.columns([1, 1])
        with c1:
            if st.button("💾 Save"):
                for _, row in edited.iterrows():
                    update_task_row(row)
                st.success("Saved")
        with c2:
            if st.button("🗑️ Delete All Tasks"):
                for tid in edited["id"].tolist():
                    delete_task(tid)
                st.rerun()  # ✅ updated

# --- Kanban View ---
with tabs[1]:
    st.subheader("Kanban")
    df = df_tasks()
    if df.empty:
        st.info("No tasks.")
    else:
        cols = st.columns(len(STATUS_OPTIONS))
        for i, st_name in enumerate(STATUS_OPTIONS):
            with cols[i]:
                st.markdown(f"**{st_name.upper()}**")
                sub = df[df["status"] == st_name]
                for _, r in sub.iterrows():
                    st.markdown(f"• **{r['title']}** — _{r.get('assignee','')}_  \n📅 {r.get('due_date','')}, 🚩 {r.get('priority','')}")
                st.divider()

# --- Calendar View ---
with tabs[2]:
    st.subheader("Calendar")
    df = df_tasks()
    if df.empty:
        st.info("No tasks.")
    else:
        cal = df.dropna(subset=["due_date"]).copy()
        cal["due_date"] = pd.to_datetime(cal["due_date"], errors="coerce")
        if not cal.empty:
            cal["day"] = cal["due_date"].dt.date
            st.dataframe(cal[["day", "title", "assignee", "status", "priority"]].sort_values("day"))
            cal["start"] = pd.to_datetime(cal["start_date"], errors="coerce").fillna(cal["due_date"])
            fig = px.timeline(cal, x_start="start", x_end="due_date", y="title", color="status")
            st.plotly_chart(fig, use_container_width=True)

# --- Automations ---
with tabs[3]:
    st.subheader("Automations")
    st.caption("Example rule (to be implemented):")
    st.code("""
Event: task.updated
Condition: status == 'blocked'
Action: notify(assignee, 'Your task is blocked')
    """, language="yaml")

# --- Search & AI ---
with tabs[4]:
    st.subheader("Search & AI")
    q = st.text_input("Search tasks")
    df = df_tasks()
    if st.button("Search") and q:
        sub = df[df.apply(lambda r: q.lower() in (r["title"]+" "+str(r.get("description",""))).lower(), axis=1)]
        st.dataframe(sub)
    if not df.empty:
        sel = st.selectbox("Summarize a task", options=[""] + df["title"].tolist())
        if sel:
            body = df[df["title"] == sel]["description"].iloc[0]
            st.write(ai_summarize(body or "No details"))

# --- Insights ---
with tabs[5]:
    st.subheader("Insights")
    df = df_tasks()
    if df.empty:
        st.info("No data.")
    else:
        c1, c2 = st.columns(2)
        with c1:
            st.bar_chart(df["status"].value_counts())
        with c2:
            st.bar_chart(df["priority"].value_counts())
