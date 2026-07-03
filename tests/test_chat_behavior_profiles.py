from __future__ import annotations

from app.core.config import Settings
from app.runtime.chat_behavior import (
    DEFAULT_BEHAVIOR_PROFILE,
    DEFAULT_CHAT_BEHAVIOR_POLICY,
    build_system_prompt,
    get_behavior_profile,
    select_behavior_profile,
)


def test_default_behavior_profile_preserves_current_policy():
    profile = get_behavior_profile("ask_this_agent")

    assert profile.name == "ask_this_agent"
    assert profile.policy is DEFAULT_CHAT_BEHAVIOR_POLICY
    assert build_system_prompt(profile.policy) == build_system_prompt(
        DEFAULT_CHAT_BEHAVIOR_POLICY
    )


def test_unknown_behavior_profile_fails_closed_to_default():
    assert get_behavior_profile("does-not-exist") is DEFAULT_BEHAVIOR_PROFILE


def test_behavior_profile_selection_is_settings_owned_not_client_metadata():
    settings = Settings(
        _env_file=None,
        chat_behavior_profile="ask_this_agent",
    )

    selected = select_behavior_profile(
        settings,
        metadata={"behavior_profile": "does-not-exist"},
        run_context={"behavior_profile": "does-not-exist"},
    )

    assert selected.name == "ask_this_agent"
