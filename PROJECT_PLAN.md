# Meridian — Project Plan

Meridian is a local-first data intelligence workspace. People connect the databases and files they already have, then ask questions in plain language. Phase 1, which this repository implements now, is connection management, schema browsing, spreadsheet profiling, and a shared demo dataset. Later phases add the assistant, MCP connectors, Google Ads, and approved imports.

The product name in the UI is Meridian. The demo company inside the sample data is Northline Outfitters.

## 1. Requirements analysis and technical risks

The platform has four separate jobs. Mixing them together is the main design risk.

| Job | Responsibility | Explicitly not its job |
| --- | --- | --- |
| Source registry | Store connections, test them, browse schemas, enable or disable sources | Run analytical joins |
| MCP adapters | Expose one source's tools through a stable protocol | Combine results from other servers |
| Query orchestrator | Pick sources, plan read-only queries, ask when a mapping is ambiguous | Invent metrics or execute shell commands |
| Federation layer | Join and aggregate already-fetched tabular results in DuckDB | Call databases or MCP servers itself |

### Risks and how the design handles them

1. **MCP cannot federate queries.** MCP transports tool calls. It has no cross-server join. Cross-source questions run independent reads, then DuckDB joins the frames using mappings a person confirmed.
2. **Unmaintained database MCP servers.** `@modelcontextprotocol/server-postgres` is archived. Several community servers expose administrative tools. Postgres and MongoDB access for Meridian goes through our own read-only connectors, which can later be wrapped as in-process MCP tools. External products (Google Ads, Salesforce, Snowflake) register as outside MCP servers.
3. **MCP Python SDK and LangChain are on different majors.** On 2026-10-10, `mcp` is 2.3.0 and `langchain-mcp-adapters` 0.3.2 still requires `mcp>=1.24,<2`. Phase 2 should call the official MCP client (`mcp==2.3.0`) and adapt tools with a small internal bridge. That avoids pinning the project to the 1.x SDK.
4. **The model will invent SQL, fields, and business metrics.** The orchestrator may only query objects discovered from live catalogs. Joins require a stored field mapping. If two mappings could apply, the assistant asks. Answers are written from returned rows. Unsupported metrics are declined.
5. **Secrets leaking into prompts or the browser.** Passwords are encrypted at rest with Fernet. API responses, logs, and future prompts receive schema metadata only. Connection errors are scrubbed before they are stored or returned.
6. **LLM-generated code execution.** The agent never receives a Python or shell tool. It may emit SQL, a MongoDB filter document, or GAQL. Those strings pass a validator, then the connector runs them under a read-only role, a statement timeout, and a row cap.
7. **Prompt injection from cell values.** Spreadsheet and database values are untrusted data. They are fenced as query results in the prompt and are never treated as instructions.
8. **Google Ads auth is operationally heavy.** Phase 3 ships a synthetic adapter with the same tool names the chat will use later (`list_accessible_customers`, `search`, `get_resource_metadata`). Every response carries `data_origin: "sample"` or `"live"`. Replacing the adapter means changing the MCP registration, not the chat UI. The official server is [googleads/google-ads-mcp](https://github.com/googleads/google-ads-mcp).
9. **Schema drift and schemaless MongoDB.** Catalogs are read at query time. MongoDB field lists are labeled as inferred from a sample document.
10. **Large uploads.** Phase 1 accepts `.csv` and `.xlsx` up to 8 MB. Imports that write to a database wait until Phase 4 and require an explicit approval step.
11. **Next.js security patch.** Next.js 16.4.0 (2026-10-06) is the current stable release. An out-of-band security update is scheduled for 2026-10-14. Upgrade `next` when that release is published.
12. **Single-user local scope.** Phase 1 has no accounts. Anyone who can reach the API can manage sources. Bind it to localhost. Multi-user auth is out of scope until a deployment phase.

## 2. Dependency versions

Checked against PyPI and npm on 2026-10-10. Phase 1 installs only the rows marked **now**. AI and federation packages stay out of the runtime until the phase that uses them, so the local app stays small.

| Package | Version | When |
| --- | --- | --- |
| Python | 3.13 | now |
| Node.js | 24 | now |
| Next.js | 16.4.0 | now |
| React / React DOM | 19.3.0 | now |
| TypeScript | 7.0.2 | now |
| Tailwind CSS | 4.3.3 | now |
| FastAPI | 0.143.0 | now |
| Uvicorn | 0.54.0 | now |
| Pydantic | 2.14.0 | now |
| Pydantic Settings | 2.15.0 | now |
| SQLAlchemy | 2.1.4 | now |
| psycopg | 3.3.6 | now |
| PyMongo | 4.18.3 | now |
| pandas | 3.0.6 | now |
| openpyxl | 3.1.5 | now |
| cryptography | 50.0.2 | now |
| PostgreSQL image | `postgres:16-alpine` | now |
| MongoDB image | `mongo:7` | now |
| LangGraph | 1.2.14 | Phase 2 |
| LangChain Core | 1.6.9 | Phase 2 |
| langchain-openai | 1.7.0 | Phase 2 |
| MCP Python SDK | 2.3.0 | Phase 2 |
| fastembed | 0.9.0 | Phase 2, local text-to-SQL schema linking (`BAAI/bge-small-en-v1.5`) |
| DuckDB | 1.5.6 | Phase 2 |
| Alembic | 1.20.0 | Phase 5, when migrations are worth the ceremony |

`langchain-mcp-adapters` 0.3.2 is intentionally not a dependency. Its `mcp<2` constraint conflicts with the current SDK.

## 3. Architecture

```text
Browser (Next.js)
    |
    |  HTTPS JSON, no secrets in responses
    v
FastAPI
    |-- Source registry -------- PostgreSQL `platform` (metadata, encrypted secrets, mappings, access log)
    |-- Connector registry
    |     |-- PostgresConnector      read-only role, statement timeout
    |     |-- MongoConnector         read role, find/list only
    |     +-- SpreadsheetConnector   files under the upload or seed directories
    |
    |-- MCP client manager -- in-process tools and registerable external servers
    |     |-- postgres / mongo / spreadsheet   catalog, sample
    |     +-- google-ads sample adapter        list_accessible_customers, search, get_resource_metadata
    |-- Phase 2: LangGraph orchestrator
    +-- DuckDB federation (joins already-fetched frames)
```

A connector is registered by source type. Adding Salesforce or Snowflake later means a new adapter module plus a registry entry. The API routes, chat page, and federation service stay as they are.

### Request path for a natural-language question

```text
question + selected sources
  -> workspace: read each table through MCP into a DuckDB frame (5,000 rows max)
  -> profile: columns, types, value lists, date ranges, row counts
  -> plan (LLM, or offline embeddings): query | report | describe | clarify
  -> clarify: stop and return the question with 2-4 options
  -> guard: one SELECT, known tables, no table functions,
            cross-source joins only on a confirmed link in a top-level AND
  -> run: DuckDB with external access off and configuration locked
  -> on rejection or error: back to plan with the error (2 retries)
  -> answer from the rows; numbers not in the rows are rejected
  -> return answer, sections, SQL, chart spec, steps, assumptions, status
```

The chart spec is data (`bar` or `line`, plus category and value fields). The UI renders it. The model does not emit JavaScript.

### Google Ads swap

The chat calls a capability, `ads.search`, through the connector registry. In Phase 3 that capability is bound to the synthetic adapter. Later it is rebound to `googleads/google-ads-mcp` over stdio or Streamable HTTP. Tool arguments stay GAQL-shaped so the official `search` tool can take them. Responses always include `data_origin`.

## 4. Repository layout

Phase 1 creates the tree below. Planned Phase 2–5 modules are listed so new work has an obvious home; those packages are not created yet.

```text
db-mcp-agent/
  PROJECT_PLAN.md
  README.md
  docker-compose.yml
  .env.example
  docker/
    postgres/init.sql          # platform DB, commerce DB, read-only role
    mongo/init.js              # crm reader and writer roles
  backend/
    Dockerfile
    requirements.txt
    requirements-dev.txt
    app/
      main.py                  # FastAPI app and demo seed on startup
      config.py
      db.py
      models.py                # data_sources, field_mappings, access_logs
      schemas.py
      security.py              # Fernet, error scrubbing
      identifiers.py
      api/routes.py
      agent/
        workspace.py           # load sources through MCP into DuckDB frames
        profile.py             # generic table profiles
        planner.py             # LLM and offline planners
        guard.py               # SQL checks and locked-down DuckDB execution
        graph.py               # LangGraph flow
        answer.py              # answer writing with the number check
      connectors/
        postgres.py
        mongo.py
        spreadsheet.py
        registry.py
      services/
        sources.py
        seed.py
      seed_data/
        catalog.py             # Northline Outfitters records
        service_cases.csv
    tests/
  frontend/
    Dockerfile
    app/                       # dashboard, sources, chat, transform, settings
    components/
    lib/
```

Planned later:

```text
backend/app/mcp/client_manager.py
backend/app/mcp/google_ads_sample.py
backend/app/imports/approve.py
```

## 5. API and connector interfaces

Base URL: `http://localhost:8010/api`

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/health` | Process is up |
| GET | `/meta` | Public configuration. Never returns secrets |
| GET | `/dashboard` | Source counts, status, recent activity, mappings |
| GET | `/sources` | List sources without secrets |
| POST | `/sources` | Create a Postgres or MongoDB source and test it |
| GET | `/sources/{id}` | One source |
| PATCH | `/sources/{id}` | Rename, enable, replace config, rotate password |
| DELETE | `/sources/{id}` | Remove a source. Uploaded files are deleted with it |
| POST | `/sources/{id}/test` | Re-test and store status |
| GET | `/sources/{id}/catalog` | Tables, collections, or columns |
| GET | `/sources/{id}/sample` | Read-only sample. `limit` max 100 |
| GET | `/sources/{id}/profile` | Spreadsheet types, nulls, duplicate rows, suggested DDL |
| POST | `/uploads` | `.csv` or `.xlsx`, max 8 MB. Registers a spreadsheet source |
| GET | `/mappings` | Confirmed cross-source links |
| POST | `/mappings` | Confirm a link between two columns |
| DELETE | `/mappings/{id}` | Remove a link |
| GET | `/mappings/suggestions` | Candidate links found by comparing column values across sources |
| POST | `/suggestions` | Starter questions generated from the selected sources' profiles |
| GET | `/activity` | Access log |
| GET | `/mcp/tools` | In-process MCP tools and registered servers |
| POST | `/ask` | Natural-language question against selected sources. Returns the answer, sections, SQL, chart spec, steps, assumptions, and clarification options |
| POST | `/report` | Same flow in report mode: two to four charted sections |

Connector contract used by the service layer:

```python
class DataConnector(Protocol):
    source_type: str

    def test(self, source: ResolvedSource) -> str: ...
    def catalog(self, source: ResolvedSource) -> list[CatalogObject]: ...
    def sample(
        self,
        source: ResolvedSource,
        schema_name: str | None,
        object_name: str,
        limit: int,
    ) -> SampleResult: ...
```

`ResolvedSource` carries the decrypted password in process memory for the duration of one request. It is not serialized.

Phase 2 MCP registration shape:

```json
{
  "name": "google-ads",
  "transport": "stdio",
  "command": ["google-ads-mcp"],
  "enabled": true,
  "data_origin": "live"
}
```

Environment variables for that process are stored encrypted and are not sent to the model. The client manager discovers tools, drops any tool that is not on an allowlist, and registers the rest by namespaced name (`google-ads.search`).

## 6. Sample data and relationships

Northline Outfitters is a fictional outdoor retailer. The same `customer_id` and `product_id` values appear in every source. Dates run from 2026-08-03 through 2026-09-28, so "last month" on 2026-10-10 means September 2026.

### Commerce PostgreSQL (`commerce`, role `commerce_reader`)

- `customers` — 12 people, primary key `customer_id` (`C001`–`C012`)
- `products` — 8 products, primary key `product_id` (`P001`–`P008`), plus `unit_cost` and `list_price`
- `orders` — 26 orders. `status` is `fulfilled` or `refunded`. One order, `O025`, is refunded
- `order_items` — line quantity and `unit_price`

### Customer CRM MongoDB (`crm`, role `crm_reader`)

- `customer_profiles` — one document per `customer_id`, with `segment` and `loyalty_points`
- `product_reviews` — reviews keyed by `customer_id` and `product_id`

`loyalty_points` is a CRM balance. It is not revenue.

### Service cases spreadsheet

`backend/app/seed_data/service_cases.csv` references the same customer and product ids. It intentionally contains blank cells and one repeated row so profiling has something to show.

### Confirmed mappings seeded into `field_mappings`

| Left | Right | Field |
| --- | --- | --- |
| Commerce PostgreSQL `customers` | Customer CRM `customer_profiles` | `customer_id` |
| Commerce PostgreSQL `customers` | Service cases | `customer_id` |
| Commerce PostgreSQL `products` | Commerce PostgreSQL `order_items` | `product_id` |
| Commerce PostgreSQL `products` | Customer CRM `product_reviews` | `product_id` |
| Commerce PostgreSQL `products` | Service cases | `product_id` |
| Commerce PostgreSQL `orders` | Commerce PostgreSQL `order_items` | `order_id` |
| Customer CRM `customer_profiles` | Customer CRM `product_reviews` | `customer_id` |

Purchases means the sum of `quantity * unit_price` on order lines whose order status is `fulfilled`. Refunded orders stay in the tables and are excluded from that metric.

Verified fulfilled totals:

| Rank | Customer | Purchases |
| --- | --- | --- |
| 1 | Sofia Rossi (`C009`) | 1245.00 |
| 2 | Andre Wallace (`C002`) | 1036.00 |
| 3 | Elena Vasquez (`C005`) | 965.00 |
| 4 | Chris Dalton (`C006`) | 277.00 |
| 5 | Ben Okonkwo (`C010`) | 260.00 |

September 2026 fulfilled totals, which is "last month" as of 2026-10-10: Elena Vasquez 544.00, Sofia Rossi 538.00, Andre Wallace 394.00.

```sql
SELECT c.customer_id, c.full_name,
       SUM(oi.quantity * oi.unit_price) AS purchases
FROM customers c
JOIN orders o ON o.customer_id = c.customer_id
JOIN order_items oi ON oi.order_id = o.order_id
WHERE o.status = 'fulfilled'
GROUP BY c.customer_id, c.full_name
ORDER BY purchases DESC
LIMIT 5;
```

Phase 3 will add a synthetic Google Ads table (`campaign_id`, name, type, date, impressions, clicks, cost, conversions, conversion value) with `data_origin = sample`. Profit questions need a further confirmed mapping from campaign to `products.category`, then `revenue - quantity * unit_cost - ad cost`. That metric is not implied by any column that exists today.

### Demo credentials

These are local sample roles, created by Docker init:

| Role | Password | Privilege |
| --- | --- | --- |
| `commerce_reader` | `commerce_reader` | `SELECT`, and the role defaults to read-only transactions |
| `crm_reader` | `crm_reader` | MongoDB `read` on `crm` |
| `platform` / `platform` | metadata database | application tables only |

The commerce admin and CRM writer passwords exist so the seed job can load data. They are not stored in `data_sources`.

## 7. How a cross-source question will be answered

Example: "Find customers stored in MongoDB who have placed orders in PostgreSQL."

1. The registry shows Customer CRM and Commerce PostgreSQL enabled.
2. Catalogs show `customer_profiles.customer_id` and `customers.customer_id`.
3. A confirmed mapping links those fields. The planner is allowed to join on them.
4. Mongo read: project `customer_id`, `full_name`, `segment` from `customer_profiles`.
5. Postgres read: distinct `customer_id` from `orders` where `status = 'fulfilled'`.
6. DuckDB: `crm JOIN orders USING (customer_id)`.
7. The answer lists only rows from that join and shows both queries.

Example that must stop: "Which campaign was most profitable?" before a campaign-to-product mapping and a profit definition exist. The assistant asks which cost columns to include. It does not subtract `loyalty_points` from ad spend or fill the gap with an estimate.

Ambiguous case: two mappings can relate "customer" (email and `customer_id`). The graph interrupts and asks which key to use. The choice is saved as the mapping to prefer next time.

## 8. Security controls in Phase 1

- Read-only database roles, plus `default_transaction_read_only` for Postgres and a session `statement_timeout` of 8 seconds.
- Connectors issue fixed catalog SQL or a `SELECT` of a validated identifier. They do not accept arbitrary SQL from the client.
- Identifier allowlist: `[A-Za-z_][A-Za-z0-9_]*`. Sample size is at most 100 rows.
- Spreadsheet paths must stay inside the upload directory or the seed-data directory.
- Secrets are Fernet-encrypted. `GET` payloads include `has_secret` and omit the ciphertext.
- Access log records tests, catalog reads, samples, uploads, and deletes.
- Writes and imports are not exposed. Phase 4 will require a separate approval call before any `INSERT` or collection write.

## 9. Milestones

### Phase 1 — Foundation (this implementation)

- [x] Docker Compose for PostgreSQL and MongoDB, with a read-only commerce role and a read-only CRM role
- [x] FastAPI source registry with encrypted secrets
- [x] Test connection, enable or disable, browse catalogs, sample rows
- [x] Excel and CSV upload, type inference, missing values, duplicate rows, suggested DDL
- [x] Northline seed data with shared ids and stored field mappings
- [x] Dashboard, data sources, upload, and settings UI
- [ ] Accounts, hosted deployment, MySQL, Snowflake, Salesforce

### Phase 2 — Assistant and MCP

- [x] MCP client manager (`mcp` 2.3) and in-process read-only tools for Postgres, MongoDB, and spreadsheets
- [x] Local text-to-SQL schema linking with `BAAI/bge-small-en-v1.5`. The embedding model picks the table and columns. DuckDB still runs the read-only query
- [x] Optional OpenAI writer (`gpt-4o-mini`) that rephrases the answer from query rows. Numbers are rejected if they were not in those rows
- [x] LangGraph flow: profile, plan, clarify, check, run, retry, answer (`agent/graph.py`)
- [x] DuckDB federation that rejects unmapped joins (`agent/guard.py`)
- [x] LLM planner that works from a generated data profile, with no per-dataset glossary
- [x] Links page with value-overlap suggestions, confirm, and remove
- [x] Multi-source questions, clarification options, and a step-by-step "How I answered" trail
- [x] Chat page with the answer, the queries, the sources, the table, and status
- [x] Query log entries on the existing activity feed

### Phase 3 — Google Ads

- [x] Synthetic campaign dataset and MCP adapter with `data_origin: sample`
- [x] Campaign questions answered from the generic planner
- [ ] Postgres-plus-ads comparison (needs a link between orders and campaigns, which the sample data does not have)
- [x] Registration path for the official Google Ads MCP server, left unwired until credentials exist

### Phase 4 — Transformation

- [x] Review screen for inferred schemas, column renames, types, duplicates, and empty cells
- [x] Approved import into Imported PostgreSQL and Imported MongoDB, or a cleaned spreadsheet
- [ ] Oracle-compatible DDL as a downloadable script, with no Oracle connection yet

### Phase 5 — Polish

- [x] Bar, line, and pie charts from the chart spec, with downloadable HTML reports
- [ ] Push queries down to the source databases instead of loading up to 5,000 rows per table
- [ ] Clearer query errors and timeouts
- [ ] Integration tests against the Compose databases
- [ ] Alembic migrations once the metadata schema needs to change in place

## 10. Phase 1 decisions

- Synchronous SQLAlchemy and PyMongo behind FastAPI. The connectors are blocking and the local concurrency is low. Async can wrap the same registry later.
- `create_all` for the metadata tables. Alembic waits until there is a schema to migrate.
- Demo data loads on API startup when `SEED_DEMO_DATA=true`. Re-running startup does not duplicate rows.
- The UI talks to the API on `http://localhost:8010`. That URL is what the browser uses even when the API container is on the Compose network.
