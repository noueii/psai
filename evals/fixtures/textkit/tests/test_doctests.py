import doctest
import unittest

import textkit.text


def load_tests(loader, tests, ignore):
    tests.addTests(doctest.DocTestSuite(textkit.text))
    return tests
