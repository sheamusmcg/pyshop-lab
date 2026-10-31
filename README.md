# PyShop - Python lab reference application

A small Flask catalog application for the AI-Enabled SDLC Automation course
(Python track). It mirrors the shape of eShopOnWeb (the .NET track's app) so
the same stories, defects, review checklist, and learning outcomes apply to
both teams - only the repository-specific lab instructions differ.

---

## Setup (do this first - nothing is pre-installed)

Don't assume your machine already has what this needs. Work through these steps
in order; each one tells you how to check before you move on.

### 1. Check your Python version - you need 3.10 or newer

    python3 --version

If it prints 3.10, 3.11, 3.12 or newer, you're fine. If it prints 3.9 or lower
(many Macs ship 3.9 as the system Python), install a newer Python first:

- macOS:    brew install python@3.12      then use  python3.12  below
- Windows:  download from python.org (3.10+), tick "Add to PATH"
- Linux:    use your package manager, e.g.  sudo apt install python3.12 python3.12-venv

Then re-check with  python3.12 --version  (use whichever command maps to 3.10+).
The SQLAlchemy version this project uses does not support Python 3.9.

### 2. Install the GitHub CLI (gh) - you need it for the lab's pull request

    gh --version

If that prints a version, you're set. If not, install it:

- macOS:    brew install gh
- Windows:  winget install GitHub.cli
- Linux:    see cli.github.com

Then sign in once:

    gh auth login

Choose GitHub.com, HTTPS, and "Login with a web browser". The last lab block
uses gh to open the pull request.

### 3. Create and activate a virtual environment

A venv keeps these packages isolated from your system Python. From the
pyshop-lab folder:

    python3 -m venv .venv          # or python3.12 -m venv .venv

    # activate it:
    source .venv/bin/activate      # macOS / Linux
    .venv\Scripts\activate         # Windows (PowerShell/cmd)

Your prompt should now show (.venv). Everything below runs inside it.
(When you're done for the day, run  deactivate  to leave the venv.)

### 4. Install the dependencies

    pip install -r requirements.txt

Confirm Flask landed:

    python -c "import flask, sqlalchemy; print('ok')"

If that prints ok, you're ready. If you see "No module named 'flask'", the
venv probably isn't activated (step 3) or the install didn't run - redo both.

### 5. Run the app

    python -m pyshop.web.app

Open http://localhost:5001 - you should see the catalog with brand and type
filters. Ctrl+C to stop it.

### 6. Run the tests

    python -m pytest tests/test_unit.py tests/test_integration.py

Nine tests should pass. These need no browser.

### 7. (For the end-to-end test) install the Playwright browser - one time

The e2e test drives a real browser and skips itself until you install one:

    pip install playwright
    playwright install chromium

Then:

    python -m pytest tests/test_e2e.py

If  playwright install  fails behind a corporate proxy or locked-down machine,
tell your facilitator - the unit and integration tests cover most of the lab
without it.

### Troubleshooting

- "No module named 'flask'"  -> venv not activated, or deps not installed (steps 3-4).
- "command not found: python3" -> try  python  instead, or install Python (step 1).
- SQLAlchemy / typing errors on startup -> you're on Python 3.9 or older (step 1).
- Port 5001 already in use -> stop the other process, or edit the port in pyshop/web/app.py.
- Playwright "browser not found" -> run  playwright install chromium  (step 7).

---

## Architecture (layered, mirrors eShopOnWeb)
- `pyshop/domain/`        - entities + the catalog filter spec (no framework)
- `pyshop/infrastructure/`- SQLAlchemy models + repository (swappable DB)
- `pyshop/web/`           - Flask blueprint, view-model, catalog template
- `tests/`                - unit, integration (in-memory SQLite), e2e (Playwright)

## Coverage (Session 2)

    pip install coverage
    coverage run -m pytest tests/test_unit.py tests/test_integration.py
    coverage report --include="pyshop/*"

## Orders (Session 2 regression lab)
`POST /order` with `{"lines":[{"item_id":1,"quantity":2}]}` records an order and
reduces stock. `GET /order/<id>` returns it. The seed has 30 items with stock.
Set `PYSHOP_DB=sqlite:///some/file.db` to run against a file database the
regression harness can reset and inspect.

## The lab feature
Add a price-range filter to the catalog page, alongside brand and type.
Requirements match the .NET track exactly: appears with the existing filters,
narrows results, clearing restores the list within remaining filters, existing
filters still work, correct under pagination.

## The deliberate gotchas (what a good CLAUDE.md warns about)
1. Duplicated predicate: `item_matches` AND `filter_predicate_for_count` in
   domain/catalog_filter.py both decide what matches. A new filter must go in
   BOTH, or the paged list and the total count drift apart.
2. Count must match the list: `CatalogRepository.count_items` has to apply the
   same filters as `list_items`. Add the price filter to the list query but not
   the count query, and the page numbers are wrong once a price range is active.

These mirror eShopOnWeb's duplicated CatalogFilter specifications, so the
CLAUDE.md teaching transfers across both tracks.
