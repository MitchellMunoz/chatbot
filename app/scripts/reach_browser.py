import os

from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

load_dotenv()

LOGIN_URL = "https://app.reach.tools/v5/login"

EMAIL_FIELD = "input[name=formEmail]"
PASSWORD_FIELD = "input[name=formPassword]"
LOGIN_BUTTON = "button[type=submit]"


def open_browser(playwright):
    return playwright.chromium.launch(
        channel="chrome",
        headless=True,
        args=["--no-sandbox", "--disable-gpu"],
    )


def login(page, email, password):
    page.goto(LOGIN_URL, wait_until="networkidle", timeout=60000)
    page.fill(EMAIL_FIELD, email)
    page.fill(PASSWORD_FIELD, password)
    page.click(LOGIN_BUTTON)
    page.wait_for_load_state("networkidle", timeout=60000)


def logged_in(page):
    return "/login" not in page.url


def reach_login():
    email = os.getenv("REACH_EMAIL")
    password = os.getenv("REACH_PASSWORD")

    if not email or not password:
        return {"error": "REACH_EMAIL y REACH_PASSWORD no estan en el .env"}

    with sync_playwright() as playwright:
        browser = open_browser(playwright)
        page = browser.new_page()
        try:
            login(page, email, password)
            result = {
                "logged_in": logged_in(page),
                "url": page.url,
                "title": page.title(),
            }
        finally:
            browser.close()

    return result
