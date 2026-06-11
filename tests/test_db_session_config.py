from __future__ import annotations

from types import SimpleNamespace


def test_engine_options_use_explicit_pool_settings():
    from app.db.session import _engine_options_from_settings

    settings = SimpleNamespace(
        db_pool_size=20,
        db_max_overflow=0,
        db_pool_pre_ping=False,
        db_pool_recycle_s=1800,
    )

    options = _engine_options_from_settings(settings)

    assert options["pool_size"] == 20
    assert options["max_overflow"] == 0
    assert options["pool_pre_ping"] is False
    assert options["pool_recycle"] == 1800
