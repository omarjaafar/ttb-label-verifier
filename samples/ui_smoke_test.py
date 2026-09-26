"""End-to-end smoke test through a real browser: single label + full batch of the sample labels.

Usage: python samples/ui_smoke_test.py [BASE_URL]      (default http://localhost:8000)
Requires: pip install playwright && playwright install chromium   (or have Microsoft Edge installed)
"""

import glob
import sys
import time

from playwright.sync_api import sync_playwright

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000").rstrip("/") + "/"


def launch(p):
    try:
        return p.chromium.launch(channel="msedge", headless=True)
    except Exception:
        return p.chromium.launch(headless=True)


def main():
    with sync_playwright() as p:
        browser = launch(p)
        page = browser.new_page(viewport={"width": 1100, "height": 1400})
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(BASE)

        page.click("#submit")
        assert "Please fill in" in page.inner_text("#form-error"), "empty form should show a validation message"

        page.set_input_files("#image", "samples/labels/04_title_case_warning.jpg")
        for name, value in [("brand_name", "Old Tom Distillery"), ("class_type", "Kentucky Straight Bourbon Whiskey"),
                            ("alcohol_content", "45%"), ("net_contents", "750 mL")]:
            page.fill(f"input[name={name}]", value)
        page.click("#submit")
        page.wait_for_selector("#results:not([hidden])", timeout=30000)
        verdict = page.inner_text("#verdict h2")
        print(f"single: {verdict} | {page.inner_text('#meta')}")
        assert verdict == "Problem found"

        page.click("#tab-batch")
        page.set_input_files("#batch-images", sorted(glob.glob("samples/labels/*.jpg")))
        page.set_input_files("#batch-csv", "samples/labels/applications.csv")
        start = time.time()
        page.click("#batch-submit")
        page.wait_for_function(
            "document.getElementById('batch-progress-text').textContent.startsWith('Done')", timeout=300000)
        print(f"batch: {page.inner_text('#batch-progress-text')} in {time.time() - start:.1f}s")
        print("tally:", " | ".join(page.inner_text("#batch-tally").split("\n")))

        assert not errors, f"JavaScript errors: {errors}"
        browser.close()
    print("OK")


if __name__ == "__main__":
    main()
