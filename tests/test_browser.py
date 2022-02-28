"""First test of OrderPortal.
Requires pytest-playwright.
"""

import json
import urllib.parse

import pytest


@pytest.fixture(scope="module")
def settings():
    """Get the settings from
    1) defaults
    2) file 'settings.json' in this directory
    """
    result = {
        "BASE_URL": "http://localhost:8881/",
        "USERNAME": None,
        "PASSWORD": None,
    }

    try:
        with open("settings.json", "rb") as infile:
            result.update(json.load(infile))
    except IOError:
        pass
    for key in result:
        if result.get(key) is None:
            raise KeyError(f"Missing {key} value in settings.")
    # Ensure trailing slash.
    result["BASE_URL"] = result["BASE_URL"].rstrip("/") + "/"
    return result


def test_no_login(settings, page): # 'page' fixture from 'pytest-playwright'
    "Actions without logging in."
    url = f"{settings['BASE_URL']}"
    page.goto(url)

    page.click("text=About us")
    assert page.url == "http://localhost:8881/about"

    page.click("text=Contact")
    assert page.url == "http://localhost:8881/contact"

    page.click("text=Documents")
    assert page.url == "http://localhost:8881/files"

    page.click("text=Information")
    page.click("text=How to place an order")
    assert page.url == "http://localhost:8881/info/how_to_place_an_order"

    page.click("#home >> span")
    assert page.url == "http://localhost:8881/"


def test_login(settings, page): # 'page' fixture from 'pytest-playwright'
    "Login to a user account."
    url = f"{settings['BASE_URL']}"
    page.goto(url)
    # page.click("""[placeholder="Email address of account"]""")
    page.fill("""[placeholder="Email address of account"]""",settings["USERNAME"])
    page.press("""[placeholder="Email address of account"]""", "Tab")
    page.fill("""input[name="password"]""", settings["PASSWORD"])
    page.click("""button:has-text("Login")""")

    assert page.url == url
    page.click(f"""text={settings["USERNAME"]}""")
    assert urllib.parse.unquote(page.url) == f"""{url}account/{settings["USERNAME"]}"""
