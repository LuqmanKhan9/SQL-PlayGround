"""SQL Playground - a beginner-friendly SQL lab built with Streamlit.

Runs SQL against a pre-populated mock SQLite database (in memory, per session)
and uses Google AI Studio (Gemini) to explain queries, fix errors, and turn
plain-English questions into SQL.
"""

import os
import random
import re
import sqlite3
import time
from datetime import date, timedelta

import pandas as pd
import streamlit as st

try:
    from google import genai
except ImportError:  # keeps the SQL lab usable even if the AI package is missing
    genai = None

# --------------------------------------------------------------------------
# Page config
# --------------------------------------------------------------------------
st.set_page_config(page_title="SQL Playground", page_icon="🧪", layout="wide")

MAX_ROWS = 500          # rows shown per query
QUERY_TIMEOUT_S = 3     # stop runaway queries (e.g. infinite recursive CTEs)
DEFAULT_MODEL = "gemini-flash-latest"

# --------------------------------------------------------------------------
# Mock database
# --------------------------------------------------------------------------
SCHEMA_SQL = """
CREATE TABLE departments (
    dept_id     INTEGER PRIMARY KEY,
    dept_name   TEXT NOT NULL,
    location    TEXT
);
CREATE TABLE employees (
    emp_id      INTEGER PRIMARY KEY,
    first_name  TEXT NOT NULL,
    last_name   TEXT NOT NULL,
    dept_id     INTEGER REFERENCES departments(dept_id),
    manager_id  INTEGER REFERENCES employees(emp_id),
    salary      INTEGER,
    hire_date   TEXT
);
CREATE TABLE customers (
    customer_id INTEGER PRIMARY KEY,
    name        TEXT NOT NULL,
    email       TEXT,
    city        TEXT,
    country     TEXT,
    signup_date TEXT
);
CREATE TABLE products (
    product_id  INTEGER PRIMARY KEY,
    name        TEXT NOT NULL,
    category    TEXT,
    price       REAL,
    stock       INTEGER
);
CREATE TABLE orders (
    order_id    INTEGER PRIMARY KEY,
    customer_id INTEGER REFERENCES customers(customer_id),
    product_id  INTEGER REFERENCES products(product_id),
    quantity    INTEGER,
    order_date  TEXT,
    status      TEXT
);
"""

DEPARTMENTS = [
    (1, "Engineering", "Berlin"),
    (2, "Sales", "London"),
    (3, "Marketing", "New York"),
    (4, "HR", "London"),
    (5, "Finance", "Toronto"),
]

EMPLOYEES = [
    (1, "Alice", "Morgan", 1, None, 150000, "2015-03-01"),
    (2, "Bob", "Chen", 1, 1, 120000, "2017-06-15"),
    (3, "Carla", "Diaz", 1, 1, 115000, "2018-09-01"),
    (4, "Dev", "Patel", 1, 2, 95000, "2020-01-20"),
    (5, "Elena", "Rossi", 2, None, 130000, "2016-02-11"),
    (6, "Farid", "Khan", 2, 5, 85000, "2019-05-05"),
    (7, "Grace", "Lee", 2, 5, 82000, "2021-07-12"),
    (8, "Hugo", "Martin", 3, None, 105000, "2018-11-30"),
    (9, "Ines", "Silva", 3, 8, 78000, "2022-03-14"),
    (10, "Jon", "Baker", 4, None, 90000, "2017-08-21"),
    (11, "Kira", "Novak", 4, 10, 62000, "2023-01-09"),
    (12, "Liam", "Walsh", 5, None, 125000, "2014-10-10"),
    (13, "Mina", "Ito", 5, 12, 88000, "2020-12-01"),
    (14, "Noah", "Brown", 1, 3, 70000, "2023-06-19"),
    (15, "Omar", "Haddad", 2, 5, 76000, "2022-09-26"),
]

CITIES = [
    ("London", "UK"), ("Manchester", "UK"), ("Berlin", "Germany"),
    ("Munich", "Germany"), ("Paris", "France"), ("New York", "USA"),
    ("Austin", "USA"), ("Toronto", "Canada"), ("Sydney", "Australia"),
    ("Lahore", "Pakistan"), ("Peshawar", "Pakistan"), ("Madrid", "Spain"),
]

FIRST = ["Ava", "Ben", "Chloe", "Dan", "Eva", "Finn", "Gia", "Hank", "Isla",
         "Jack", "Kai", "Lena", "Max", "Nora", "Otto", "Pia", "Quinn", "Ravi",
         "Sara", "Tom", "Uma", "Vik", "Wes", "Xena", "Yusuf", "Zoe"]
LAST = ["Adams", "Bell", "Cruz", "Dunn", "Ellis", "Fox", "Gray", "Hill",
        "Ivanov", "Jones", "Khan", "Lopez", "Moore", "Nash", "Ortiz", "Price"]

PRODUCTS = [
    (1, "Laptop Pro 14", "Electronics", 1299.00, 25),
    (2, "Wireless Mouse", "Electronics", 29.99, 200),
    (3, "Mechanical Keyboard", "Electronics", 89.50, 80),
    (4, "USB-C Hub", "Electronics", 45.00, 120),
    (5, "Noise-Cancelling Headphones", "Electronics", 199.00, 60),
    (6, "Standing Desk", "Furniture", 450.00, 15),
    (7, "Ergonomic Chair", "Furniture", 320.00, 22),
    (8, "Desk Lamp", "Furniture", 35.00, 150),
    (9, "Notebook (3-pack)", "Stationery", 12.50, 500),
    (10, "Gel Pens (10-pack)", "Stationery", 8.99, 400),
    (11, "Whiteboard", "Stationery", 60.00, 40),
    (12, "Coffee Beans 1kg", "Grocery", 18.00, 90),
]

STATUSES = ["delivered", "delivered", "delivered", "shipped", "pending", "cancelled"]


def build_database(allow_writes: bool) -> sqlite3.Connection:
    """Create a fresh in-memory SQLite DB filled with mock data."""
    rng = random.Random(42)  # deterministic so every session sees the same data
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.executescript(SCHEMA_SQL)

    conn.executemany("INSERT INTO departments VALUES (?,?,?)", DEPARTMENTS)
    conn.executemany("INSERT INTO employees VALUES (?,?,?,?,?,?,?)", EMPLOYEES)
    conn.executemany("INSERT INTO products VALUES (?,?,?,?,?)", PRODUCTS)

    customers = []
    for cid in range(1, 41):
        first, last = rng.choice(FIRST), rng.choice(LAST)
        city, country = rng.choice(CITIES)
        signup = date(2022, 1, 1) + timedelta(days=rng.randint(0, 900))
        customers.append(
            (cid, f"{first} {last}", f"{first}.{last}{cid}@example.com".lower(),
             city, country, signup.isoformat())
        )
    conn.executemany("INSERT INTO customers VALUES (?,?,?,?,?,?)", customers)

    orders = []
    for oid in range(1, 151):
        order_date = date(2024, 1, 1) + timedelta(days=rng.randint(0, 600))
        orders.append(
            (oid, rng.randint(1, 40), rng.randint(1, 12), rng.randint(1, 5),
             order_date.isoformat(), rng.choice(STATUSES))
        )
    conn.executemany("INSERT INTO orders VALUES (?,?,?,?,?,?)", orders)
    conn.commit()

    # Safety: never let user SQL touch the filesystem or other databases.
    def authorizer(action, arg1, arg2, db_name, trigger):
        if action in (sqlite3.SQLITE_ATTACH, sqlite3.SQLITE_DETACH):
            return sqlite3.SQLITE_DENY
        return sqlite3.SQLITE_OK

    conn.set_authorizer(authorizer)
    if not allow_writes:
        conn.execute("PRAGMA query_only = ON")
    return conn


def get_conn(allow_writes: bool) -> sqlite3.Connection:
    """One DB per browser session; rebuilt when the write mode changes."""
    if (
        "conn" not in st.session_state
        or st.session_state.get("conn_writes") != allow_writes
    ):
        st.session_state.conn = build_database(allow_writes)
        st.session_state.conn_writes = allow_writes
    return st.session_state.conn


def schema_text(conn: sqlite3.Connection) -> str:
    """Current CREATE statements, used as context for the AI."""
    rows = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' "
        "AND name NOT LIKE 'sqlite_%' ORDER BY name"
    ).fetchall()
    return "\n".join(r[0].strip() + ";" for r in rows if r[0])


# --------------------------------------------------------------------------
# Running queries
# --------------------------------------------------------------------------
def run_query(conn: sqlite3.Connection, sql: str):
    """Returns (DataFrame | None, message, error | None)."""
    sql = sql.strip()
    if not sql:
        return None, "", "Please type a query first."

    start = time.time()
    conn.set_progress_handler(
        lambda: 1 if time.time() - start > QUERY_TIMEOUT_S else 0, 10000
    )
    try:
        cur = conn.execute(sql)
        if cur.description:  # SELECT-like: has columns
            cols = [d[0] for d in cur.description]
            rows = cur.fetchmany(MAX_ROWS + 1)
            truncated = len(rows) > MAX_ROWS
            df = pd.DataFrame(rows[:MAX_ROWS], columns=cols)
            msg = f"{len(df)} row(s) returned in {time.time() - start:.3f}s"
            if truncated:
                msg += f" (showing first {MAX_ROWS})"
            return df, msg, None
        conn.commit()
        return None, f"Statement OK - {cur.rowcount} row(s) affected.", None
    except sqlite3.OperationalError as e:
        text = str(e)
        if "interrupted" in text:
            text = f"Query stopped after {QUERY_TIMEOUT_S}s - it was taking too long."
        return None, "", text
    except sqlite3.Error as e:
        return None, "", str(e)
    finally:
        conn.set_progress_handler(None, 0)


# --------------------------------------------------------------------------
# Gemini helper (Google AI Studio API key)
# --------------------------------------------------------------------------
def get_api_key() -> str:
    """Order: sidebar box -> Streamlit secrets -> environment variable."""
    typed = st.session_state.get("typed_key", "").strip()
    if typed:
        return typed
    try:
        if "GOOGLE_API_KEY" in st.secrets:
            return st.secrets["GOOGLE_API_KEY"]
        if "GEMINI_API_KEY" in st.secrets:
            return st.secrets["GEMINI_API_KEY"]
    except Exception:
        pass  # no secrets file present
    return os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY") or ""


def ask_gemini(prompt: str, model: str) -> str:
    key = get_api_key()
    if genai is None:
        return "⚠️ The `google-genai` package isn't installed. Check requirements.txt."
    if not key:
        return ("⚠️ No API key found. Add `GOOGLE_API_KEY` to Streamlit secrets "
                "or paste it in the sidebar.")
    try:
        client = genai.Client(api_key=key)
        resp = client.models.generate_content(model=model, contents=prompt)
        return resp.text or "The model returned an empty answer. Try again."
    except Exception as e:  # network, quota, invalid key, bad model name...
        return f"⚠️ AI request failed: {e}"


TUTOR_RULES = (
    "You are a friendly SQL tutor for complete beginners. The database is SQLite. "
    "Keep answers short, use plain language, and put SQL in ```sql code blocks. "
    "Only use tables and columns that exist in the schema below.\n\n"
    "SCHEMA:\n{schema}\n\n"
)


def extract_sql(text: str) -> str:
    m = re.search(r"```(?:sql)?\s*(.*?)```", text, re.S | re.I)
    return (m.group(1) if m else text).strip()


# --------------------------------------------------------------------------
# Example queries
# --------------------------------------------------------------------------
EXAMPLES = {
    "— pick an example —": "",
    "1. Look at a table": "SELECT * FROM employees;",
    "2. Choose columns": "SELECT first_name, last_name, salary\nFROM employees;",
    "3. Filter rows (WHERE)": "SELECT name, price\nFROM products\nWHERE category = 'Electronics' AND price < 100;",
    "4. Sort results (ORDER BY)": "SELECT first_name, salary\nFROM employees\nORDER BY salary DESC\nLIMIT 5;",
    "5. Count and group": "SELECT country, COUNT(*) AS customers\nFROM customers\nGROUP BY country\nORDER BY customers DESC;",
    "6. JOIN two tables": "SELECT e.first_name, e.last_name, d.dept_name\nFROM employees e\nJOIN departments d ON e.dept_id = d.dept_id;",
    "7. Revenue per product (JOIN + SUM)": "SELECT p.name, SUM(o.quantity * p.price) AS revenue\nFROM orders o\nJOIN products p ON p.product_id = o.product_id\nWHERE o.status <> 'cancelled'\nGROUP BY p.name\nORDER BY revenue DESC;",
    "8. HAVING": "SELECT d.dept_name, ROUND(AVG(e.salary)) AS avg_salary\nFROM employees e\nJOIN departments d ON d.dept_id = e.dept_id\nGROUP BY d.dept_name\nHAVING AVG(e.salary) > 90000;",
    "9. Self join (who reports to whom)": "SELECT e.first_name AS employee, m.first_name AS manager\nFROM employees e\nLEFT JOIN employees m ON e.manager_id = m.emp_id;",
    "10. Subquery": "SELECT name, price\nFROM products\nWHERE price > (SELECT AVG(price) FROM products);",
}


def apply_example():
    choice = st.session_state.get("example_choice")
    if choice and EXAMPLES.get(choice):
        st.session_state.sql_text = EXAMPLES[choice]


# --------------------------------------------------------------------------
# UI
# --------------------------------------------------------------------------
st.title("🧪 SQL Playground")
st.caption("Practice SQL on a safe mock database. Nothing you do here affects real data.")

with st.sidebar:
    st.header("Settings")
    allow_writes = st.toggle(
        "Allow INSERT / UPDATE / DELETE",
        value=False,
        help="Off = read-only (SELECT only). Turning it on resets the database.",
    )
    if st.button("🔄 Reset database", width="stretch"):
        st.session_state.pop("conn", None)
        st.session_state.pop("last_result", None)
        st.rerun()

    st.divider()
    st.subheader("🤖 AI helper (Gemini)")
    if get_api_key():
        st.success("API key found")
    else:
        st.warning("No API key found")
    st.text_input(
        "Google AI Studio API key",
        type="password",
        key="typed_key",
        help="Optional if you already set GOOGLE_API_KEY in Streamlit secrets.",
    )
    model_name = st.text_input("Model", value=DEFAULT_MODEL)

conn = get_conn(allow_writes)

with st.sidebar:
    st.divider()
    st.subheader("📚 Tables")
    for (tname,) in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' "
        "AND name NOT LIKE 'sqlite_%' ORDER BY name"
    ).fetchall():
        info = conn.execute(f'PRAGMA table_info("{tname}")').fetchall()
        count = conn.execute(f'SELECT COUNT(*) FROM "{tname}"').fetchone()[0]
        with st.expander(f"{tname} ({count} rows)"):
            for _cid, col, ctype, notnull, _d, pk in info:
                st.markdown(f"`{col}` {ctype}" + (" 🔑" if pk else ""))

tab_lab, tab_ai, tab_browse = st.tabs(["▶️ SQL Lab", "🤖 Ask AI", "🗂️ Browse tables"])

# ---- SQL Lab --------------------------------------------------------------
with tab_lab:
    st.selectbox(
        "Start from an example", list(EXAMPLES), key="example_choice",
        on_change=apply_example,
    )
    st.session_state.setdefault("sql_text", "SELECT * FROM customers LIMIT 10;")
    st.text_area("Write your SQL here", key="sql_text", height=180)

    if st.button("▶️ Run query", type="primary"):
        df, msg, err = run_query(conn, st.session_state.sql_text)
        st.session_state.last_result = {
            "df": df, "msg": msg, "err": err, "sql": st.session_state.sql_text,
        }

    res = st.session_state.get("last_result")
    if res:
        if res["err"]:
            st.error(res["err"])
            if st.button("🩹 Explain this error with AI"):
                prompt = (
                    TUTOR_RULES.format(schema=schema_text(conn))
                    + f"The student ran this query:\n```sql\n{res['sql']}\n```\n"
                    f"SQLite returned this error: {res['err']}\n"
                    "Explain in 2-3 sentences what went wrong and show the fixed query."
                )
                with st.spinner("Thinking..."):
                    st.session_state.error_help = ask_gemini(prompt, model_name)
            if st.session_state.get("error_help"):
                st.info(st.session_state.error_help)
        else:
            st.session_state.pop("error_help", None)
            st.success(res["msg"])
            if res["df"] is not None:
                st.dataframe(res["df"], width="stretch", hide_index=True)

# ---- Ask AI ---------------------------------------------------------------
with tab_ai:
    st.markdown("**Turn a question into SQL**")
    question = st.text_input(
        "Ask in plain English",
        placeholder="e.g. Which 3 customers placed the most orders?",
    )
    if st.button("✨ Generate SQL") and question.strip():
        prompt = (
            TUTOR_RULES.format(schema=schema_text(conn))
            + f"Write one SQLite query that answers: {question}\n"
            "Give the query in a ```sql block, then explain it step by step in "
            "simple words (max 5 short bullet points)."
        )
        with st.spinner("Thinking..."):
            st.session_state.ai_answer = ask_gemini(prompt, model_name)

    if st.session_state.get("ai_answer"):
        st.markdown(st.session_state.ai_answer)
        if "```" in st.session_state.ai_answer:
            def _copy_to_editor():
                st.session_state.sql_text = extract_sql(st.session_state.ai_answer)
            st.button("📋 Put this query in the SQL Lab editor", on_click=_copy_to_editor)

    st.divider()
    st.markdown("**Explain the query currently in the editor**")
    if st.button("🧑‍🏫 Explain my query"):
        current = st.session_state.get("sql_text", "").strip()
        if not current:
            st.warning("The editor is empty.")
        else:
            prompt = (
                TUTOR_RULES.format(schema=schema_text(conn))
                + f"Explain this query line by line for a beginner:\n```sql\n{current}\n```"
            )
            with st.spinner("Thinking..."):
                st.session_state.explain_answer = ask_gemini(prompt, model_name)
    if st.session_state.get("explain_answer"):
        st.markdown(st.session_state.explain_answer)

# ---- Browse ---------------------------------------------------------------
with tab_browse:
    tables = [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' "
        "AND name NOT LIKE 'sqlite_%' ORDER BY name").fetchall()]
    if tables:
        pick = st.selectbox("Table", tables)
        preview = pd.read_sql_query(f'SELECT * FROM "{pick}" LIMIT 50', conn)
        st.dataframe(preview, width="stretch", hide_index=True)
        st.caption("Showing up to 50 rows.")
