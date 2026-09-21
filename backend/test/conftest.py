from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Avoid package-level knowledge graph initialization during pytest collection.
os.environ.setdefault("YUXI_SKIP_APP_INIT", "1")


def pytest_configure(config: pytest.Config) -> None:
    """Register shared markers without binding every test to a live environment."""
    config.addinivalue_line("markers", "unit: marks tests that run without live services")
    config.addinivalue_line("markers", "auth: marks tests that require authentication")
    config.addinivalue_line("markers", "integration: marks tests that hit the live API service")
    config.addinivalue_line("markers", "e2e: marks tests that exercise an end-to-end workflow")
    config.addinivalue_line("markers", "slow: marks tests as slow")


pytest_plugins = ["pytest_asyncio"]

# SQLite compatibility compilers for Postgres-specific types during unit testing
from sqlalchemy.dialects.postgresql import ARRAY, INET, JSONB, TSVECTOR
from sqlalchemy.ext.compiler import compiles


@compiles(JSONB, "sqlite")
def compile_jsonb_sqlite(type_, compiler, **kw):
    return "JSON"


@compiles(ARRAY, "sqlite")
def compile_array_sqlite(type_, compiler, **kw):
    return "JSON"


@compiles(TSVECTOR, "sqlite")
def compile_tsvector_sqlite(type_, compiler, **kw):
    return "TEXT"


@compiles(INET, "sqlite")
def compile_inet_sqlite(type_, compiler, **kw):
    return "TEXT"
