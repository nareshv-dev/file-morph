import os

# Tests must never connect to or reset a developer's configured MongoDB.
os.environ["FILEMORPH_TESTING"] = "1"
