"Test runner."

import unittest

import browser_anonymous
import browser_login

loader = unittest.TestLoader()
suite = unittest.TestSuite()

suite.addTests(loader.loadTestsFromModule(browser_anonymous))
suite.addTests(loader.loadTestsFromModule(browser_login))

runner = unittest.TextTestRunner(verbosity=2)
runner.run(suite)
