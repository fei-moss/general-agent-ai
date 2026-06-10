"""应用配置。

基于 pydantic-settings 从环境变量 / .env 读取配置,提供带 lru_cache
的 get_settings() 单例访问器。所有配置项均有默认值,保证零外部依赖即可启动。
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """全局配置。字段名对应大写下划线环境变量(大小写不敏感)。"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- 数据库 / 中间件 ---
    db_url: str = "postgresql+asyncpg://postgres:postgres@localhost:55432/agent"
    redis_url: str = "redis://localhost:55379/0"

    # --- Celery ---
    celery_broker_url: str = "redis://localhost:55379/1"
    celery_result_backend: str = "redis://localhost:55379/2"

    # --- LLM provider 选择 ---
    # 运行时(app.runtime)由 PydanticAI 驱动 agentic loop,按下方选择原生 model:
    #   mock      -> FunctionModel(零 key 确定性中文回答,无需任何外部依赖)
    #   openai    -> OpenAIChatModel(openai_base_url/openai_model)
    #   qwen      -> OpenAIChatModel(qwen_base_url/qwen_model,DashScope 兼容端点)
    #   anthropic -> AnthropicModel(anthropic_model)
    #   gemini    -> GoogleModel(gemini_model)
    llm_provider: str = "mock"  # mock | openai | qwen | anthropic | gemini
    openai_base_url: str = "https://api.openai.com/v1"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-6"
    # 通义千问 Qwen:走 DashScope 的 OpenAI 兼容端点(key 见 dashscope_api_key)
    qwen_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    qwen_model: str = "qwen-plus"
    # Google Gemini(key 见 gemini_api_key)
    gemini_model: str = "gemini-2.5-flash"

    # --- LiteLLM 统一网关(多厂商:OpenAI / Claude / Qwen / Gemini ...) ---
    # 主模型必须带 provider 前缀,如 openai/gpt-4o、anthropic/claude-sonnet-4-6、
    # gemini/gemini-2.5-flash、dashscope/qwen-plus。
    litellm_model: str = "openai/gpt-4o"
    # 跨厂商 fallback 链:逗号分隔,主模型失败时依次降级。
    # 例:anthropic/claude-sonnet-4-6,gemini/gemini-2.5-flash,dashscope/qwen-plus
    litellm_fallbacks: str = ""
    # 各厂商 key(litellm 通过标准环境变量读取;留空则沿用已注入 os.environ 的值)
    gemini_api_key: str = ""
    dashscope_api_key: str = ""  # 通义千问 Qwen (DashScope)

    @property
    def litellm_fallback_list(self) -> list[str]:
        """把逗号分隔的 fallback 配置解析为去空白的模型列表。"""
        return [m.strip() for m in self.litellm_fallbacks.split(",") if m.strip()]

    # --- 运行参数 ---
    rate_limit_per_min: int = 60
    max_turns: int = 10
    retrieval_top_k: int = 5
    embedding_dim: int = 256
    request_timeout_s: float = 60.0

    # --- 服务 ---
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    """返回进程内缓存的 Settings 单例。"""
    return Settings()
