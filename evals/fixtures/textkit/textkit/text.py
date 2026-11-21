"""Text helpers."""


def slugify(text):
    """Lowercase the text and turn spaces into dashes.

    >>> slugify("Hello World")
    'hello-world'
    """
    return text.strip().lower().replace(" ", "-")


def wordcount(text):
    """Count the words in the text.

    >>> wordcount("one two three")
    3
    """
    return len(text.split(" "))
