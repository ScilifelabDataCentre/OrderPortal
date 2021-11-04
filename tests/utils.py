"Some utilities for the tests."

import json
import unittest

import selenium.webdriver


class BrowserTestCase(unittest.TestCase):
    "Browser driver setup."

    def setUp(self):
        self.settings = get_settings()
        self.driver = get_browser_driver(self.settings["BROWSER"])

    def tearDown(self):
        self.driver.close()
        self.driver.quit()


class ApiMixin:
    "Provides method the check the validity of a result against its schema."

    def setUp(self):
        self.settings = get_settings()
        self.headers = {"X-OrderPortal-API-key": self.settings["APIKEY"]}


def get_settings():
    """Get the settings from
    1) default
    2) settings file
    """
    result = {
        "BROWSER": "Chrome",
        "BASE_URL": "http://localhost:8881/",
        "VERSION": "5.2.0",
        "USERNAME": None,
        "PASSWORD": None
    }

    try:
        with open("settings.json", "rb") as infile:
            result.update(json.load(infile))
    except IOError:
        pass
    for key in result:
        if result.get(key) is None:
            raise KeyError(f"Missing {key} value in settings.")
    return result

def get_browser_driver(name):
    "Return the Selenium driver for the browser given by name."
    if name == "Chrome":
        return selenium.webdriver.Chrome()
    elif name == "Firefox":
        return selenium.webdriver.Firefox()
    elif name == "Edge":
        return selenium.webdriver.Edge()
    elif name == "Safari":
        return selenium.webdriver.Safari()
    else:
        raise ValueError(f"Unknown browser driver '{name}'.")
