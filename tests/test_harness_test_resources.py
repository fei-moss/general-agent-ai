from pathlib import Path
import runpy

import pytest


def resource_environment():
    return runpy.run_path(str(Path(__file__).resolve().parents[1] / "scripts/test_resource_env.py"))["connection_overrides"]


def managed_settings():
    return {
        "HARNESS_RESOURCE_RUN_ID": "owned-run",
        "TEST_DATABASE_DSN": "postgres://task:p%40ss@127.0.0.1:54321/run_db?sslmode=disable",
        "TEST_REDIS_ADDR": "127.0.0.1:54322",
        "TEST_REDIS_USERNAME": "task",
        "TEST_REDIS_PASSWORD": "p@ss:/word",
        "TEST_REDIS_DB": "7",
        "DB_URL": "postgresql+asyncpg://foreign/database",
        "REDIS_URL": "redis://foreign/0",
    }


def test_task_connections_replace_legacy_urls_without_losing_isolation():
    result = resource_environment()(managed_settings())
    assert result["DB_URL"] == "postgresql+asyncpg://task:p%40ss@127.0.0.1:54321/run_db?ssl=disable"
    expected = "redis://task:p%40ss%3A%2Fword@127.0.0.1:54322/7"
    assert result["REDIS_URL"] == expected
    assert result["CELERY_BROKER_URL"] == expected
    assert result["CELERY_RESULT_BACKEND"] == expected


@pytest.mark.parametrize("key", ["HARNESS_RESOURCE_RUN_ID", "TEST_DATABASE_DSN", "TEST_REDIS_ADDR", "TEST_REDIS_USERNAME", "TEST_REDIS_PASSWORD", "TEST_REDIS_DB"])
def test_incomplete_managed_connection_never_falls_back_to_foreign_data(key):
    values = managed_settings()
    values[key] = ""
    with pytest.raises(ValueError):
        resource_environment()(values)


@pytest.mark.parametrize("database", ["0", "-1", "invalid"])
def test_invalid_logical_database_is_rejected(database):
    values = managed_settings()
    values["TEST_REDIS_DB"] = database
    with pytest.raises(ValueError):
        resource_environment()(values)
