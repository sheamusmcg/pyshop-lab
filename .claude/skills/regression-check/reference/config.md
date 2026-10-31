# regression-check.yml

One file at the repo root. The skill reads it; the scripts run it; CI protects
`baseline_dir`. Change it through a PR like code.

| Key | Meaning |
| :- | :- |
| `project` | Name recorded in every baseline file |
| `runner` | `python` or `dotnet`; informational, the `app.start` command does the work |
| `baseline_dir` | Where committed baselines live; the CI guard watches this path |
| `app.start` | Shell command that starts the app. `{db}` becomes a fresh SQLite path, `{port}` a free port |
| `app.ready_url`, `app.ready_timeout_s` | Polled until it answers |
| `database.kind` | `sqlite` today. For a server DB, set `reset` to a command that drops, recreates and seeds, and extend `capture.py`'s `snapshot_tables` with a driver |
| `database.tables[]` | `name`, `key` (identity columns), `fields` (compared columns), optional `where` to keep snapshots small |
| `scenarios[]` | `id`, `description`, `steps[]` of `method`, `path`, optional `json` body, `business_fields` (JSON paths within the response body) |
| `normalize[]` | `path` (`$.response.headers.Date`, `$.response.body.created_at`, `$.response.body.items[*].id`) and `replace` |
| `baseline_approval` | The label and CODEOWNERS path CI enforces |

## .NET example (eShopOnWeb)

Not executed in the session's build environment; verify locally. eShopOnWeb
uses `UseOnlyInMemoryDatabase`, which does not persist between processes, so the
harness runs it against a file-backed SQLite connection string instead and the
`Infrastructure` project's `UseSqlite` provider. Alternatively, run against a
local SQL Server and set `database.reset` to a script that restores a seeded
backup.

```yaml
project: eshoponweb
runner: dotnet
baseline_dir: tests/baselines
app:
  start: >
    ASPNETCORE_ENVIRONMENT=Development
    ConnectionStrings__CatalogConnection="Data Source={db}"
    ConnectionStrings__IdentityConnection="Data Source={db}"
    ASPNETCORE_URLS=http://127.0.0.1:{port}
    dotnet run --project src/PublicApi --no-build
  ready_url: "http://127.0.0.1:{port}/api/catalog-items?pageSize=1"
  ready_timeout_s: 60
database:
  kind: sqlite
  reset: fresh_file
  tables:
    - { name: Orders,      key: [Id],            fields: [Id, BuyerId] }
    - { name: OrderItems,  key: [OrderId, Id],   fields: [OrderId, Units, UnitPrice] }
    - { name: Catalog,     key: [Id],            fields: [Id, Price],  where: "Id IN (1, 2, 3)" }
scenarios:
  - id: add_to_basket_and_checkout
    description: Add catalog item 1 to a basket and check out
    steps:
      - { method: POST, path: /api/basket/items, json: { catalogItemId: 1, quantity: 2 },
          business_fields: [items[0].quantity, items[0].unitPrice] }
      - { method: POST, path: /api/orders/checkout, json: { basketId: 1 }, business_fields: [total] }
normalize:
  - { path: "$.response.headers.Date", replace: "<date>" }
  - { path: "$.response.body.id", replace: "<id>" }
baseline_approval:
  label: baseline-change
  codeowners_path: tests/baselines/
```

The PublicApi routes above are indicative; confirm the actual endpoints and
authentication in the repo before relying on this file. The eShopOnWeb order
path requires an authenticated user, so the start command may need a test
token or the lab's demo-user credentials.
