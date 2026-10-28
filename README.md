# 🧪 SQL Playground

A beginner-friendly, browser-based SQL lab built with **Streamlit**. Run SQL against a
pre-populated mock database (SQLite, in memory) and get help from **Google Gemini**
(via a Google AI Studio API key) to explain queries, fix errors, and turn plain-English
questions into SQL.

## Features

- **SQL Lab** – write a query, click Run, see results in a table.
- **10 guided examples** – from `SELECT *` to JOINs, GROUP BY / HAVING and subqueries.
- **Mock database** – `departments`, `employees`, `customers`, `products`, `orders`.
- **AI helper (Gemini)**
  - *Explain this error* when a query fails
  - *Generate SQL* from a plain-English question
  - *Explain my query* line by line
- **Safe by default** – read-only mode, `ATTACH`/`DETACH` blocked, 3-second query timeout,
  max 500 rows shown. Optional toggle to practice `INSERT` / `UPDATE` / `DELETE`;
  the **Reset database** button restores the original data.
- Every visitor gets their own private in-memory database.

## Project files

```
app.py            # the Streamlit app
requirements.txt  # Python dependencies
README.md         # this file
```

## Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Get a Google AI Studio API key

1. Go to <https://aistudio.google.com/apikey>
2. Sign in and click **Create API key**.
3. Copy the key. Never commit it to GitHub.

## Add the key

**Locally** – create `.streamlit/secrets.toml` (and add `.streamlit/secrets.toml` to `.gitignore`):

```toml
GOOGLE_API_KEY = "your-key-here"
```

Or set an environment variable: `export GOOGLE_API_KEY="your-key-here"`.

**On Streamlit Community Cloud** – after deploying, open the app's
**Settings → Secrets** and paste:

```toml
GOOGLE_API_KEY = "your-key-here"
```

You can also paste the key into the sidebar box while using the app (it is only
kept for your session).

## Deploy from GitHub

1. Push `app.py`, `requirements.txt` and `README.md` to a GitHub repository.
2. Go to <https://share.streamlit.io> and click **Create app**.
3. Select your repository, branch `main`, and main file `app.py`.
4. Open **Advanced settings → Secrets** and add `GOOGLE_API_KEY`.
5. Click **Deploy**.

## Changing the AI model

The sidebar has a **Model** box. The default is `gemini-flash-latest`, an alias that
points to the current Gemini Flash model. Replace it with any model name listed in
Google AI Studio if you want a specific one. If the free-tier quota runs out, the app
shows the error message instead of crashing.

## Customising the data

Edit the `DEPARTMENTS`, `EMPLOYEES`, `PRODUCTS` lists and `SCHEMA_SQL` at the top of
`app.py`, or add new tables to `SCHEMA_SQL` and insert rows in `build_database()`.
