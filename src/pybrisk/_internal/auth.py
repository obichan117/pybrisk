"""Authentication: Playwright login → SBI → BRiSK → extract cookies."""

from __future__ import annotations

from pybrisk._internal.config import Config
from pybrisk._internal.exceptions import AuthenticationError
from pybrisk._internal.session import Session

_SBI_LOGIN_URL = "https://www.sbisec.co.jp/ETGate"
_BRISK_ORIGIN = "https://sbi.brisk.jp"


def login_with_browser(config: Config, session: Session) -> None:
    """Open browser, log into SBI Securities, launch BRiSK, extract cookies."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        raise AuthenticationError(
            "Playwright is required for browser login. "
            "Install with: pip install 'pybrisk[browser]'"
        ) from None

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()

        # Step 1: Navigate to SBI login page
        page.goto(_SBI_LOGIN_URL)
        page.wait_for_load_state("networkidle")

        # Step 2: Fill login form
        page.fill('input[name="user_id"]', config.username)
        page.fill('input[name="user_password"]', config.password)
        page.click('input[name="ACT_login"]')
        page.wait_for_load_state("networkidle")

        # Step 3: Navigate to BRiSK / 全板 service
        # Look for the BRiSK link in the navigation
        page.goto(
            "https://www.sbisec.co.jp/ETGate/"
            "?_ControlID=WPLETmgR001Control&_PageID=DefaultPID&"
            "_DataStoreID=DSWPLETmgR001Control&"
            "_ActionID=DefaultAID&burl=search_home&"
            "cat1=home&cat2=service&dir=service&file=home_zenita.html"
        )
        page.wait_for_load_state("networkidle")

        # Step 4: Click the BRiSK launch link and wait for new tab
        with context.expect_page() as new_page_info:
            # Look for a link that opens BRiSK
            brisk_link = page.locator('a[href*="brisk"]').first
            if brisk_link.count() == 0:
                # Try button or other element
                brisk_link = page.locator('text=BRiSK').first
            brisk_link.click()

        brisk_page = new_page_info.value
        brisk_page.wait_for_url(f"{_BRISK_ORIGIN}/**")
        brisk_page.wait_for_load_state("networkidle")

        # Step 5: Extract cookies for brisk.jp domain
        all_cookies = context.cookies(_BRISK_ORIGIN)
        cookies = {c["name"]: c["value"] for c in all_cookies}

        if not cookies:
            raise AuthenticationError(
                "No cookies extracted from BRiSK. Login may have failed."
            )

        session.load_cookies(cookies)
        browser.close()


def login_with_cookies(cookies: dict[str, str], session: Session) -> None:
    """Use manually provided cookies — no browser needed."""
    session.load_cookies(cookies)
