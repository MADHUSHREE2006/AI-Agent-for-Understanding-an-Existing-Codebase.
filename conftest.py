"""Pytest configuration: make the project root importable for tests.

Having a ``conftest.py`` at the project root ensures ``import config``,
``import tools``, etc. resolve correctly regardless of where pytest is
invoked from.
"""

import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
