# Meridian

Local workspace for asking questions of your own data. Connect PostgreSQL, MongoDB, Excel or CSV files, Google Analytics, and Google Ads, confirm which columns link the sources together, then ask in plain words. Each answer shows the chart, the rows, and the exact SQL that produced it, and any answer or report can be downloaded.

Nothing about the questions or the data is hard-coded. Meridian profiles whatever tables you connect (columns, types, value lists, date ranges), plans a read-only query from that profile, checks it, runs it, and writes the answer from the returned rows only.

## Run it

```bash
cp .env.example .env
# Generate the encryption key for saved passwords and paste it into APP_SECRET_KEY in .env
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
# Optional: add OPENAI_API_KEY to .env for open-ended questions and cross-source joins
docker compose up -d
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
pytest
uvicorn app.main:app --reload --port 8010
```

In another terminal:

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:3000. The API docs are at http://localhost:8010/docs.

`docker compose up -d` starts PostgreSQL on host port **55432** and MongoDB on host port **27018**. Those ports stay off 5432 and 27017 so they do not collide with a database already running on the machine.

To run the API and web app in containers as well:

```bash
docker compose --profile app up -d --build
```

Reset the sample databases:

```bash
docker compose down -v
```

## How a question is answered

The assistant is a LangGraph flow in `backend/app/agent/graph.py`:

1. **Read the data.** The selected sources are loaded through MCP tools into in-memory DuckDB tables (up to 5,000 rows per table). Each table is profiled.
2. **Plan.** With `OPENAI_API_KEY` set, the model receives the question, the profiles, and the confirmed links, and returns a plan: a query, a multi-section report, a description of the data, or a clarifying question with options. Without a key, an offline planner (local `BAAI/bge-small-en-v1.5` embeddings) handles simple totals, rankings, filters, and reports.
3. **Check.** `agent/guard.py` parses the SQL with DuckDB and rejects anything other than one `SELECT`, table functions, file reads, and unknown tables. Tables from different sources may only be joined on a confirmed link that appears in a top-level `AND` of the join or `WHERE` condition.
4. **Run.** DuckDB runs the query with external access disabled and configuration locked. If the check or the run fails, the error goes back to the planner, which gets up to two retries.
5. **Answer.** The answer is written from the returned rows. If the model's wording contains a number that is not in the rows (or a total, share, or difference computed from them), the plain version is used instead.

Links are managed on the **Links** page. Meridian suggests links by comparing the actual values in each column across sources; nothing joins until you confirm a link.

## Encryption key rotation

Saved database passwords are encrypted with `APP_SECRET_KEY`. To rotate it, move the current key into `APP_SECRET_KEY_PREVIOUS`, put a new key in `APP_SECRET_KEY`, and restart the API. Stored secrets are re-encrypted on startup, after which the previous key can be removed.

## Sample logins

These roles exist only on the local Docker databases.

| Role | Password | Access |
| --- | --- | --- |
| `commerce_reader` | `commerce_reader` | `SELECT` on the commerce database |
| `crm_reader` | `crm_reader` | read on the `crm` database |
| `platform` | `platform` | Meridian metadata only |

## Privacy

With an OpenAI key set, the table profiles are sent to OpenAI to plan the query: table and column names, row counts, min/max values, the full value list for text columns with 25 or fewer distinct values, and three example values for other text columns (these can include names or emails). Up to 30 result rows per query are sent to write the answer. Without a key, everything stays on the machine.
