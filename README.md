# Meridian

Local workspace for connecting PostgreSQL, MongoDB, and spreadsheets. Phase 1 covers connection management, schema browsing, spreadsheet profiling, and the Northline Outfitters sample data. Natural-language questions arrive in Phase 2.

## Run it

```bash
cp .env.example .env
docker compose up -d
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
pytest
uvicorn app.main:app --reload --port 8000
```

In another terminal:

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:3000. The API docs are at http://localhost:8000/docs.

`docker compose up -d` starts PostgreSQL on host port **55432** and MongoDB on host port **27018**. Those ports stay off 5432 and 27017 so they do not collide with a database already running on the machine. Inside Compose, the API container still uses the service names and the databases' own ports.

To run the API and web app in containers as well:

```bash
docker compose --profile app up -d --build
```

Reset the sample databases:

```bash
docker compose down -v
```

## Sample logins

These roles exist only on the local Docker databases.

| Role | Password | Access |
| --- | --- | --- |
| `commerce_reader` | `commerce_reader` | `SELECT` on the commerce database |
| `crm_reader` | `crm_reader` | read on the `crm` database |
| `platform` | `platform` | Meridian metadata only |

The `.env` Fernet key is for local development. Generate a new one before pointing Meridian at a database you care about.
