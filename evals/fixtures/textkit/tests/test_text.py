import unittest

from textkit import slugify, wordcount


class TextTest(unittest.TestCase):
    def test_slugify_basic(self):
        self.assertEqual(slugify("Hello World"), "hello-world")

    def test_wordcount_basic(self):
        self.assertEqual(wordcount("one two three"), 3)


if __name__ == "__main__":
    unittest.main()
