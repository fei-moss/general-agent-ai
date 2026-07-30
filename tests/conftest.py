import pytest
import uvloop


@pytest.fixture
def event_loop_policy():
    # Uvicorn's default --loop auto selects installed uvloop in the production API.
    return uvloop.EventLoopPolicy()
