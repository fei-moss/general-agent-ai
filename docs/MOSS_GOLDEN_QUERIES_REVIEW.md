# MOSS Golden Queries Review

## Scope

This review covers the expanded MOSS Wiki retrieval-eval dataset for `SPEC-RAG-EVAL-001`.
It remains retrieval-only: the goal is to verify whether RAG retrieves the right evidence before answer-level judging is added.

Reviewed artifacts:

- `tests/rag_eval/moss_corpus.jsonl`
- `tests/rag_eval/moss_golden_queries.jsonl`
- `tests/rag_eval/moss_golden_query_review.jsonl`
- `tests/rag_eval/moss_coverage_contract.json`
- `tests/rag_eval/moss_acceptance_evidence_contract.json`
- `tests/rag_eval/moss_rag_seed_manifest.json`
- `tests/rag_eval/moss_import_payloads.py`
- `tests/rag_eval/moss_promptfooconfig.yaml`
- `docs/MOSS_RAG_INGESTION_RUNBOOK.md`

Source index:

- `https://moss-5.gitbook.io/moss/llms.txt`
- `https://moss-5.gitbook.io/moss/sitemap.xml`

## Review Conclusion

The expanded set contains 79 reviewed Golden Queries over 40 MOSS corpus summaries.
The corpus imports P0/P1/P2 pages that are useful for product support, onboarding, troubleshooting, strategy education, copy trading, architecture, analytics, and ecosystem questions.

| Priority | Corpus docs | Meaning |
| --- | ---: | --- |
| P0 | 26 | User-facing safety, setup, copy trading, risk, FAQ, and support knowledge. |
| P1 | 8 | Deeper operational, architecture, migration, strategy, and reliability guidance. |
| P2 | 6 | Ecosystem, analytics, Chrome extension, and community-growth knowledge. |

The canonical corpus uses English GitBook markdown pages as source-backed summaries. Chinese and Korean translation pages are not duplicated in this seed to avoid equivalent documents competing for rank; Chinese, English, and mixed-language Golden Queries still test multilingual user phrasing.

## Coverage Contract

Machine-readable coverage contract: `SPEC-RAG-EVAL-001-MOSS-COVERAGE`.
Machine-readable acceptance evidence contract: `SPEC-RAG-EVAL-001-MOSS-ACCEPTANCE-EVIDENCE`.

- at least 79 Golden Queries and 40 corpus documents
- at least 30 challenge types
- at least 15 multi-source retrieval queries
- Chinese, English, and mixed-language phrasing

## Capability Coverage

| Capability group | Query count | Query ids |
| --- | ---: | --- |
| `safety_permissions_privacy` | 5 | `moss_q_simulated_capital_safety`, `moss_q_readonly_access_scope`, `moss_q_privacy_collected_info`, `moss_q_privacy_sell_personal_info`, `moss_q_privacy_delete_withdraw_rights` |
| `agent_creation_and_management` | 4 | `moss_q_hosted_agent_creation_flow`, `moss_q_self_hosted_setup_flow`, `moss_q_active_agent_limit_delete`, `moss_q_edit_agent_parameters` |
| `copy_trading_real_funds_and_controls` | 6 | `moss_q_copy_trading_real_funds`, `moss_q_copy_trading_custody`, `moss_q_copy_multiple_agents`, `moss_q_copy_position_scaling`, `moss_q_copy_pause_close_positions`, `moss_q_copy_capital_ratio_increase` |
| `copy_trading_operations` | 4 | `moss_q_get_usdc_arbitrum`, `moss_q_device_awake_required`, `moss_q_enable_watchdog`, `moss_q_skill_update_rollback` |
| `strategy_and_risk` | 6 | `moss_q_strategy_four_layers`, `moss_q_strategy_exit_logic_importance`, `moss_q_atr_sl_atr_mult`, `moss_q_max_drawdown_interpretation`, `moss_q_multi_agent_portfolio`, `moss_q_friction_cost_layers` |
| `architecture_backtesting_evolution` | 5 | `moss_q_architecture_llm_math_boundary`, `moss_q_five_signal_dimensions`, `moss_q_backtest_friction_layers`, `moss_q_cross_margin_liquidation`, `moss_q_weekly_evolution_loop` |
| `ambush_bot_and_signals` | 5 | `moss_q_ambush_bot_token_selection`, `moss_q_ambush_bot_trigger_conditions`, `moss_q_ambush_bot_risk_rules`, `moss_q_x_signals_score`, `moss_q_x_sentiment_tracks` |
| `ecosystem_and_growth` | 5 | `moss_q_diamonds_earn`, `moss_q_diamonds_future_use`, `moss_q_agent_arena_definition`, `moss_q_builders_program_rewards`, `moss_q_builders_program_join` |
| `analytics_and_extension` | 4 | `moss_q_trader_leaderboard_metrics`, `moss_q_trader_ai_analysis`, `moss_q_chrome_extension_features`, `moss_q_extension_install_invite` |
| `troubleshooting` | 3 | `moss_q_clawhub_rate_limit`, `moss_q_python_env_missing`, `moss_q_pair_code_invalid` |

## Corpus Coverage

| Priority | Corpus id | Source | Section |
| --- | --- | --- | --- |
| P0 | `moss_product_safety` | [moss-agent-overview](https://moss-5.gitbook.io/moss/creating-your-ai-trading-agent/agent-overview.md) | `product_safety` |
| P0 | `moss_leaderboards_modes` | [moss-agent-overview](https://moss-5.gitbook.io/moss/creating-your-ai-trading-agent/agent-overview.md) | `leaderboards_modes` |
| P0 | `moss_agent_detail_metrics` | [moss-agent-overview](https://moss-5.gitbook.io/moss/creating-your-ai-trading-agent/agent-overview.md) | `agent_detail` |
| P0 | `moss_setup_install_bind` | [self-hosted-agent](https://moss-5.gitbook.io/moss/creating-your-ai-trading-agent/self-hosted-agent.md) | `setup_bind` |
| P0 | `moss_strategy_prompt_config` | [strategy-guide](https://moss-5.gitbook.io/moss/strategy-guide/how-to-write-a-good-strategy-description.md) | `strategy_prompt` |
| P0 | `moss_launch_modes` | [hosted-agent](https://moss-5.gitbook.io/moss/creating-your-ai-trading-agent/hosted-agent.md) | `launch_modes` |
| P0 | `moss_manage_limits_delete` | [manage-your-agent](https://moss-5.gitbook.io/moss/creating-your-ai-trading-agent/manage-your-agent.md) | `management_limits` |
| P0 | `moss_visibility_refresh_faq` | [faq-general](https://moss-5.gitbook.io/moss/faq/general.md) | `visibility_refresh` |
| P0 | `moss_claude_code_install` | [self-hosted-agent](https://moss-5.gitbook.io/moss/creating-your-ai-trading-agent/self-hosted-agent.md) | `claude_code_skill` |
| P0 | `moss_bot_troubleshooting` | [faq-interactions](https://moss-5.gitbook.io/moss/faq/interactions.md) | `bot_troubleshooting` |
| P0 | `moss_privacy_collection` | [moss-privacy-policy](https://moss-5.gitbook.io/moss) | `privacy_collection` |
| P0 | `moss_privacy_sharing_rights` | [moss-privacy-policy](https://moss-5.gitbook.io/moss) | `privacy_sharing_rights` |
| P0 | `moss_about_platform` | [about-moss](https://moss-5.gitbook.io/moss/introduction/about-moss.md) | `about_platform` |
| P0 | `moss_agent_supported_assets` | [agent-overview](https://moss-5.gitbook.io/moss/creating-your-ai-trading-agent/agent-overview.md) | `supported_assets` |
| P0 | `moss_hosted_agent_creation` | [hosted-agent](https://moss-5.gitbook.io/moss/creating-your-ai-trading-agent/hosted-agent.md) | `hosted_agent_flow` |
| P0 | `moss_self_hosted_agent_flow` | [self-hosted-agent](https://moss-5.gitbook.io/moss/creating-your-ai-trading-agent/self-hosted-agent.md) | `self_hosted_flow` |
| P0 | `moss_ambush_bot_rules` | [ambush-bot](https://moss-5.gitbook.io/moss/creating-your-ai-trading-agent/ambush-bot.md) | `ambush_bot` |
| P1 | `moss_agent_migration_process` | [agent-migration-guide](https://moss-5.gitbook.io/moss/creating-your-ai-trading-agent/agent-migration-guide.md) | `agent_migration` |
| P0 | `moss_copy_trading_overview` | [what-is-copy-trading](https://moss-5.gitbook.io/moss/start-copy-trading/what-is-copy-trading.md) | `copy_trading_overview` |
| P0 | `moss_copy_trading_mechanics_rules` | [copy-trading-mechanics-&-rules](https://moss-5.gitbook.io/moss/start-copy-trading/copy-trading-mechanics-and-rules.md) | `copy_trading_rules` |
| P0 | `moss_copy_trading_start_flow` | [how-to-start-copy-trading](https://moss-5.gitbook.io/moss/start-copy-trading/how-to-start-copy-trading.md) | `copy_trading_start` |
| P1 | `moss_copy_trading_usdc_arbitrum` | [how-to-get-usdc-on-arbitrum](https://moss-5.gitbook.io/moss/start-copy-trading/how-to-start-copy-trading/how-to-get-usdc-on-arbitrum.md) | `copy_trading_usdc` |
| P1 | `moss_copy_trading_device_awake` | [how-to-keep-your-device-awake-(required-for-running-agent-locally)](https://moss-5.gitbook.io/moss/start-copy-trading/how-to-start-copy-trading/how-to-keep-your-device-awake-required-for-running-agent-locally.md) | `device_awake` |
| P1 | `moss_copy_trading_watchdog_updates` | [auto-restart-and-skill-updates](https://moss-5.gitbook.io/moss/start-copy-trading/how-to-start-copy-trading/auto-restart-and-skill-updates.md) | `watchdog_updates` |
| P1 | `moss_architecture_math_ai_layers` | [architecture-overview](https://moss-5.gitbook.io/moss/technology/architecture-overview.md) | `architecture` |
| P1 | `moss_backtesting_friction_margin` | [backtesting-engine](https://moss-5.gitbook.io/moss/technology/backtesting-engine.md) | `backtesting` |
| P1 | `moss_self_evolution_loop` | [self-evolution-system](https://moss-5.gitbook.io/moss/technology/self-evolution-system.md) | `self_evolution` |
| P2 | `moss_x_signals_sentiment` | [x-signals](https://moss-5.gitbook.io/moss/other-features/x-signals.md) | `x_signals` |
| P2 | `moss_trader_feature_profiles` | [trader](https://moss-5.gitbook.io/moss/other-features/trader.md) | `trader` |
| P2 | `moss_chrome_extension_features` | [other-features](https://moss-5.gitbook.io/moss/other-features/other-features.md) | `chrome_features` |
| P0 | `moss_strategy_description_framework` | [how-to-write-a-good-strategy-description](https://moss-5.gitbook.io/moss/strategy-guide/how-to-write-a-good-strategy-description.md) | `strategy_description` |
| P0 | `moss_key_metrics_risk` | [key-metrics-explained](https://moss-5.gitbook.io/moss/strategy-guide/key-metrics-explained.md) | `key_metrics` |
| P1 | `moss_advanced_strategy_techniques` | [advanced-techniques](https://moss-5.gitbook.io/moss/strategy-guide/advanced-techniques.md) | `advanced_strategy` |
| P0 | `moss_friction_costs` | [friction-cost-guide](https://moss-5.gitbook.io/moss/strategy-guide/friction-cost-guide.md) | `friction_costs` |
| P2 | `moss_diamonds_rewards` | [diamonds](https://moss-5.gitbook.io/moss/moss-ecosystem/diamonds.md) | `diamonds` |
| P2 | `moss_agent_arena_competitions` | [agent-arena-trading-competitions](https://moss-5.gitbook.io/moss/moss-ecosystem/agent-arena-trading-competitions.md) | `agent_arena` |
| P2 | `moss_builders_program_rewards` | [builders-program](https://moss-5.gitbook.io/moss/moss-ecosystem/builders-program.md) | `builders_program` |
| P0 | `moss_faq_general_core` | [general](https://moss-5.gitbook.io/moss/faq/general.md) | `faq_general` |
| P0 | `moss_faq_interactions_troubleshooting` | [interactions](https://moss-5.gitbook.io/moss/faq/interactions.md) | `faq_interactions` |
| P0 | `moss_faq_copy_trading` | [copy-trading](https://moss-5.gitbook.io/moss/faq/copy-trading.md) | `faq_copy_trading` |

## Golden Query Review Matrix

| Query id | Challenge type | Expected docs | Tags |
| --- | --- | --- | --- |
| `moss_q_simulated_capital_safety` | `safety_boundary` | `moss_product_safety`, `moss_faq_general_core` | `moss`, `safety`, `zh` |
| `moss_q_readonly_access_scope` | `permission_scope_multi_source` | `moss_product_safety`, `moss_privacy_collection`, `moss_faq_general_core` | `moss`, `permissions`, `zh` |
| `moss_q_live_vs_hell_listing` | `mode_comparison` | `moss_leaderboards_modes`, `moss_faq_general_core` | `moss`, `leaderboard`, `zh` |
| `moss_q_hell_backtest_period` | `specific_fact` | `moss_leaderboards_modes` | `moss`, `hell-mode`, `zh` |
| `moss_q_leaderboard_metrics` | `list_extraction` | `moss_leaderboards_modes`, `moss_agent_arena_competitions` | `moss`, `metrics`, `zh` |
| `moss_q_agent_detail_exposure` | `feature_surface_detail` | `moss_agent_detail_metrics`, `moss_trader_feature_profiles` | `moss`, `agent-detail`, `zh` |
| `moss_q_strategy_prompt_required_fields` | `procedure_requirements` | `moss_strategy_description_framework`, `moss_strategy_prompt_config` | `moss`, `strategy`, `zh` |
| `moss_q_starting_capital_fixed` | `constraint_fact` | `moss_strategy_prompt_config`, `moss_faq_general_core` | `moss`, `capital`, `zh` |
| `moss_q_after_backtest_choices` | `workflow_branching` | `moss_launch_modes`, `moss_hosted_agent_creation` | `moss`, `workflow`, `zh` |
| `moss_q_advanced_params_leverage` | `risk_and_configuration` | `moss_launch_modes`, `moss_friction_costs`, `moss_key_metrics_risk` | `moss`, `risk`, `zh` |
| `moss_q_active_agent_limit_delete` | `limit_and_irreversible_action` | `moss_manage_limits_delete`, `moss_faq_general_core` | `moss`, `management`, `zh` |
| `moss_q_public_visibility` | `privacy_visibility_product_faq` | `moss_visibility_refresh_faq`, `moss_faq_general_core` | `moss`, `visibility`, `zh` |
| `moss_q_rank_refresh_interval` | `specific_fact` | `moss_visibility_refresh_faq` | `moss`, `refresh`, `zh` |
| `moss_q_live_hell_independent_boards` | `mode_disambiguation` | `moss_visibility_refresh_faq`, `moss_leaderboards_modes` | `moss`, `leaderboard`, `zh` |
| `moss_q_claude_code_install_skill` | `tooling_command` | `moss_claude_code_install`, `moss_self_hosted_agent_flow` | `moss`, `setup`, `en` |
| `moss_q_clawhub_rate_limit` | `troubleshooting` | `moss_bot_troubleshooting`, `moss_faq_interactions_troubleshooting` | `moss`, `troubleshooting`, `zh` |
| `moss_q_python_env_missing` | `troubleshooting` | `moss_bot_troubleshooting`, `moss_faq_interactions_troubleshooting` | `moss`, `troubleshooting`, `zh` |
| `moss_q_pair_code_invalid` | `troubleshooting_mixed_language` | `moss_bot_troubleshooting`, `moss_faq_interactions_troubleshooting` | `moss`, `troubleshooting`, `mixed` |
| `moss_q_privacy_collected_info` | `privacy_data_inventory` | `moss_privacy_collection` | `moss`, `privacy`, `zh` |
| `moss_q_privacy_sell_personal_info` | `privacy_sharing_policy` | `moss_privacy_sharing_rights` | `moss`, `privacy`, `zh` |
| `moss_q_privacy_delete_withdraw_rights` | `privacy_rights` | `moss_privacy_sharing_rights` | `moss`, `privacy-rights`, `zh` |
| `moss_q_what_is_moss` | `platform_positioning` | `moss_about_platform` | `moss`, `about`, `en` |
| `moss_q_who_is_moss_for` | `audience_segmentation` | `moss_about_platform` | `moss`, `about`, `zh` |
| `moss_q_supported_assets` | `supported_assets` | `moss_agent_supported_assets` | `moss`, `assets`, `zh` |
| `moss_q_choose_asset_in_prompt` | `asset_selection_prompt` | `moss_agent_supported_assets`, `moss_strategy_description_framework` | `moss`, `assets`, `strategy`, `zh` |
| `moss_q_hosted_agent_creation_flow` | `hosted_workflow` | `moss_hosted_agent_creation` | `moss`, `hosted`, `zh` |
| `moss_q_hosted_setup_questions` | `hosted_questionnaire` | `moss_hosted_agent_creation` | `moss`, `hosted`, `setup`, `mixed` |
| `moss_q_self_hosted_setup_flow` | `self_hosted_workflow` | `moss_self_hosted_agent_flow`, `moss_setup_install_bind` | `moss`, `self-hosted`, `setup`, `zh` |
| `moss_q_self_hosted_control` | `hosted_self_hosted_comparison` | `moss_self_hosted_agent_flow`, `moss_faq_general_core` | `moss`, `self-hosted`, `hosted`, `zh` |
| `moss_q_ambush_bot_token_selection` | `ambush_bot_token_scope` | `moss_ambush_bot_rules` | `moss`, `ambush`, `zh` |
| `moss_q_ambush_bot_trigger_conditions` | `ambush_bot_trigger_logic` | `moss_ambush_bot_rules` | `moss`, `ambush`, `signals`, `zh` |
| `moss_q_ambush_bot_risk_rules` | `ambush_bot_risk_rules` | `moss_ambush_bot_rules` | `moss`, `ambush`, `risk`, `zh` |
| `moss_q_agent_migration_required` | `migration_requirement` | `moss_agent_migration_process` | `moss`, `migration`, `zh` |
| `moss_q_migration_retrieve_params` | `migration_parameter_recovery` | `moss_agent_migration_process` | `moss`, `migration`, `zh` |
| `moss_q_copy_trading_real_funds` | `copy_trading_real_funds` | `moss_copy_trading_overview`, `moss_faq_copy_trading` | `moss`, `copy-trading`, `safety`, `zh` |
| `moss_q_copy_trading_custody` | `copy_trading_custody` | `moss_faq_copy_trading`, `moss_copy_trading_overview` | `moss`, `copy-trading`, `custody`, `zh` |
| `moss_q_copy_multiple_agents` | `copy_trading_limit` | `moss_faq_copy_trading`, `moss_copy_trading_mechanics_rules` | `moss`, `copy-trading`, `limits`, `zh` |
| `moss_q_copy_trading_fees` | `copy_trading_fees` | `moss_faq_copy_trading`, `moss_copy_trading_mechanics_rules` | `moss`, `copy-trading`, `fees`, `zh` |
| `moss_q_copy_position_scaling` | `copy_position_scaling` | `moss_faq_copy_trading`, `moss_copy_trading_mechanics_rules` | `moss`, `copy-trading`, `risk`, `zh` |
| `moss_q_copy_pause_close_positions` | `copy_pause_close` | `moss_faq_copy_trading`, `moss_copy_trading_mechanics_rules` | `moss`, `copy-trading`, `risk`, `zh` |
| `moss_q_copy_latency_slippage` | `copy_latency_slippage` | `moss_faq_copy_trading`, `moss_copy_trading_mechanics_rules` | `moss`, `copy-trading`, `risk`, `zh` |
| `moss_q_copy_capital_ratio_increase` | `copy_capital_ratio_constraint` | `moss_faq_copy_trading` | `moss`, `copy-trading`, `risk`, `zh` |
| `moss_q_get_usdc_arbitrum` | `usdc_arbitrum_setup` | `moss_copy_trading_usdc_arbitrum` | `moss`, `copy-trading`, `usdc`, `en` |
| `moss_q_device_awake_required` | `local_runtime_awake` | `moss_copy_trading_device_awake` | `moss`, `copy-trading`, `device`, `zh` |
| `moss_q_enable_watchdog` | `watchdog_enablement` | `moss_copy_trading_watchdog_updates` | `moss`, `copy-trading`, `watchdog`, `zh` |
| `moss_q_skill_update_rollback` | `skill_update_rollback` | `moss_copy_trading_watchdog_updates` | `moss`, `copy-trading`, `updates`, `zh` |
| `moss_q_architecture_llm_math_boundary` | `architecture_boundary` | `moss_architecture_math_ai_layers` | `moss`, `architecture`, `ai-boundary`, `zh` |
| `moss_q_five_signal_dimensions` | `signal_dimensions` | `moss_architecture_math_ai_layers` | `moss`, `architecture`, `signals`, `zh` |
| `moss_q_locked_vs_evolvable_params` | `parameter_evolution_boundary` | `moss_architecture_math_ai_layers`, `moss_self_evolution_loop` | `moss`, `architecture`, `evolution`, `mixed` |
| `moss_q_backtest_friction_layers` | `backtest_friction_layers` | `moss_backtesting_friction_margin`, `moss_friction_costs` | `moss`, `backtesting`, `friction`, `zh` |
| `moss_q_backtest_hyperliquid_fees` | `specific_fee_fact` | `moss_backtesting_friction_margin`, `moss_friction_costs` | `moss`, `backtesting`, `fees`, `mixed` |
| `moss_q_cross_margin_liquidation` | `cross_margin_semantics` | `moss_backtesting_friction_margin` | `moss`, `backtesting`, `margin`, `zh` |
| `moss_q_weekly_evolution_loop` | `evolution_loop_steps` | `moss_self_evolution_loop`, `moss_faq_general_core` | `moss`, `evolution`, `zh` |
| `moss_q_stop_loss_too_tight` | `evolution_diagnosis` | `moss_self_evolution_loop`, `moss_key_metrics_risk` | `moss`, `evolution`, `risk`, `zh` |
| `moss_q_x_signals_score` | `x_signal_score` | `moss_x_signals_sentiment` | `moss`, `x-signals`, `kol`, `zh` |
| `moss_q_x_sentiment_tracks` | `x_sentiment_tracking` | `moss_x_signals_sentiment` | `moss`, `x-signals`, `sentiment`, `zh` |
| `moss_q_trader_leaderboard_metrics` | `trader_metrics` | `moss_trader_feature_profiles` | `moss`, `trader`, `metrics`, `zh` |
| `moss_q_trader_ai_analysis` | `trader_ai_analysis` | `moss_trader_feature_profiles` | `moss`, `trader`, `analytics`, `zh` |
| `moss_q_chrome_extension_features` | `extension_feature_inventory` | `moss_chrome_extension_features` | `moss`, `extension`, `features`, `zh` |
| `moss_q_extension_install_invite` | `extension_onboarding_reward` | `moss_chrome_extension_features`, `moss_diamonds_rewards` | `moss`, `extension`, `diamonds`, `zh` |
| `moss_q_strategy_four_layers` | `strategy_four_layers` | `moss_strategy_description_framework` | `moss`, `strategy`, `zh` |
| `moss_q_strategy_exit_logic_importance` | `strategy_exit_logic` | `moss_strategy_description_framework`, `moss_key_metrics_risk` | `moss`, `strategy`, `risk`, `zh` |
| `moss_q_atr_sl_atr_mult` | `atr_metric` | `moss_key_metrics_risk` | `moss`, `metrics`, `risk`, `mixed` |
| `moss_q_max_drawdown_interpretation` | `drawdown_metric` | `moss_key_metrics_risk` | `moss`, `metrics`, `risk`, `zh` |
| `moss_q_multi_agent_portfolio` | `multi_agent_portfolio` | `moss_advanced_strategy_techniques` | `moss`, `strategy`, `portfolio`, `zh` |
| `moss_q_what_not_to_do_constraints` | `negative_constraints` | `moss_advanced_strategy_techniques` | `moss`, `strategy`, `constraints`, `zh` |
| `moss_q_friction_cost_layers` | `friction_cost_layers` | `moss_friction_costs`, `moss_backtesting_friction_margin` | `moss`, `friction`, `fees`, `zh` |
| `moss_q_monthly_friction_calculation` | `friction_cost_calculation` | `moss_friction_costs` | `moss`, `friction`, `risk`, `zh` |
| `moss_q_fee_tiers_hype_discount` | `fee_tier_discount` | `moss_friction_costs` | `moss`, `friction`, `fees`, `en` |
| `moss_q_diamonds_earn` | `diamonds_earning` | `moss_diamonds_rewards` | `moss`, `diamonds`, `zh` |
| `moss_q_diamonds_future_use` | `diamonds_future_use` | `moss_diamonds_rewards` | `moss`, `diamonds`, `zh` |
| `moss_q_agent_arena_definition` | `arena_definition` | `moss_agent_arena_competitions` | `moss`, `arena`, `competition`, `zh` |
| `moss_q_agent_arena_transparency` | `arena_transparency` | `moss_agent_arena_competitions`, `moss_leaderboards_modes` | `moss`, `arena`, `leaderboard`, `zh` |
| `moss_q_builders_program_rewards` | `builders_rewards` | `moss_builders_program_rewards` | `moss`, `builders`, `rewards`, `zh` |
| `moss_q_builders_program_join` | `builders_join` | `moss_builders_program_rewards` | `moss`, `builders`, `en` |
| `moss_q_is_moss_free` | `faq_free` | `moss_faq_general_core` | `moss`, `faq`, `pricing`, `zh` |
| `moss_q_managed_vs_self_hosted` | `managed_self_hosted_comparison` | `moss_faq_general_core`, `moss_self_hosted_agent_flow` | `moss`, `faq`, `self-hosted`, `zh` |
| `moss_q_edit_agent_parameters` | `edit_parameters` | `moss_faq_general_core`, `moss_manage_limits_delete` | `moss`, `faq`, `management`, `zh` |
| `moss_q_copy_resume_after_stop` | `copy_resume` | `moss_faq_copy_trading` | `moss`, `copy-trading`, `faq`, `zh` |

## Acceptance Evidence

Final completion requires these artifacts to pass together:

- Gemini preflight: `.artifacts/release/moss_gemini_preflight.json`
- semantic Promptfoo eval: `.artifacts/release/moss_rag_promptfoo_eval.json`
- persistent ingestion summary: `.artifacts/release/moss_rag_ingestion_summary.json`
- release gate summary: `.artifacts/release/summary.json`
- acceptance validator: `.venv/bin/python -m tests.rag_eval.moss_acceptance_validator`

## Current Limitations

- This is still a curated, source-backed summary corpus rather than a verbatim full-page mirror.
- Translation pages are intentionally excluded from the first expanded seed to reduce duplicate-rank noise.
- Answer-level LLM judging remains out of scope for this phase.
