"""End-to-end tests - drive the running app with Playwright.
Mirrors eShopOnWeb EndToEndTests (Playwright). Skipped if Playwright/browser
not installed; the lab walks through the one-time setup."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import pytest

pytest.importorskip("playwright", reason="Playwright not installed - see lab setup")

from playwright.sync_api import sync_playwright
import threading, time
from werkzeug.serving import make_server
from pyshop.web.app import create_app

@pytest.fixture(scope="module")
def live_server():
    app = create_app()
    srv = make_server("127.0.0.1", 5099, app)
    t = threading.Thread(target=srv.serve_forever); t.start()
    time.sleep(0.5)
    yield "http://127.0.0.1:5099"
    srv.shutdown(); t.join()

def test_catalog_loads_and_filters(live_server):
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page()
        page.goto(live_server)
        assert "Azure Mug" in page.content()
        page.select_option("select[name=brand]", "1")
        page.wait_for_load_state("networkidle")
        assert "Azure Mug" in page.content()
        assert "VS Mug" not in page.content()
        browser.close()
