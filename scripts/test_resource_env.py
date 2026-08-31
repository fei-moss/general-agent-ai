#!/usr/bin/env python3
"""Map the owned test connection contract to this project's async clients."""

import os
import sys
from urllib.parse import parse_qsl, quote, urlencode, urlsplit, urlunsplit


def connection_overrides(values):
    required = ("HARNESS_RESOURCE_RUN_ID", "TEST_DATABASE_DSN", "TEST_REDIS_ADDR", "TEST_REDIS_USERNAME", "TEST_REDIS_PASSWORD", "TEST_REDIS_DB")
    if any(not values.get(key) for key in required):
        raise ValueError("managed test connection settings are incomplete")
    database = int(values["TEST_REDIS_DB"])
    if database <= 0:
        raise ValueError("managed Redis database must be positive")
    postgres = urlsplit(values["TEST_DATABASE_DSN"])
    if postgres.scheme not in ("postgres", "postgresql") or not postgres.hostname or not postgres.path.strip("/"):
        raise ValueError("invalid managed PostgreSQL connection")
    query = dict(parse_qsl(postgres.query))
    if "sslmode" in query:
        query["ssl"] = query.pop("sslmode")
    db_url = urlunsplit(("postgresql+asyncpg", postgres.netloc, postgres.path, urlencode(query), ""))
    username = quote(values["TEST_REDIS_USERNAME"], safe="")
    password = quote(values["TEST_REDIS_PASSWORD"], safe="")
    redis_url = f"redis://{username}:{password}@{values['TEST_REDIS_ADDR']}/{database}"
    return {"DB_URL": db_url, "REDIS_URL": redis_url, "CELERY_BROKER_URL": redis_url, "CELERY_RESULT_BACKEND": redis_url}


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit("a test command is required")
    try:
        overrides = connection_overrides(os.environ)
    except ValueError:
        raise SystemExit("invalid or incomplete managed test connection") from None
    os.execvpe(sys.argv[1], sys.argv[1:], {**os.environ, **overrides})
