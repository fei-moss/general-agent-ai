-- 初始化建表脚本(对应 app/core/models.py)
-- Postgres 16。可重复执行(IF NOT EXISTS)。
-- 含必要索引:message.conversation_id / agent_run.conversation_id / tool_call_log.agent_run_id

CREATE TABLE IF NOT EXISTS conversation (
    id          VARCHAR(64) PRIMARY KEY,
    user_id     VARCHAR(64),
    title       VARCHAR(512),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS message (
    id              VARCHAR(64) PRIMARY KEY,
    conversation_id VARCHAR(64) NOT NULL
        REFERENCES conversation(id) ON DELETE CASCADE,
    role            VARCHAR(16) NOT NULL,
    content         TEXT NOT NULL,
    token_count     INTEGER NOT NULL DEFAULT 0,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    meta            JSONB NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS ix_message_conversation_id
    ON message (conversation_id);

CREATE TABLE IF NOT EXISTS agent_run (
    id              VARCHAR(64) PRIMARY KEY,
    conversation_id VARCHAR(64) NOT NULL
        REFERENCES conversation(id) ON DELETE CASCADE,
    trace_id        VARCHAR(64) NOT NULL,
    status          VARCHAR(16) NOT NULL DEFAULT 'PENDING',
    intent          VARCHAR(32),
    plan            JSONB,
    error           TEXT,
    started_at      TIMESTAMPTZ,
    finished_at     TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS ix_agent_run_conversation_id
    ON agent_run (conversation_id);
CREATE INDEX IF NOT EXISTS ix_agent_run_trace_id
    ON agent_run (trace_id);

CREATE TABLE IF NOT EXISTS task_state (
    id           VARCHAR(64) PRIMARY KEY,
    agent_run_id VARCHAR(64) NOT NULL
        REFERENCES agent_run(id) ON DELETE CASCADE,
    task_type    VARCHAR(32) NOT NULL,
    status       VARCHAR(16) NOT NULL DEFAULT 'QUEUED',
    attempt      INTEGER NOT NULL DEFAULT 0,
    payload      JSONB,
    result       JSONB,
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_task_state_agent_run_id
    ON task_state (agent_run_id);

CREATE TABLE IF NOT EXISTS tool_call_log (
    id           VARCHAR(64) PRIMARY KEY,
    agent_run_id VARCHAR(64) NOT NULL
        REFERENCES agent_run(id) ON DELETE CASCADE,
    tool_name    VARCHAR(128) NOT NULL,
    arguments    JSONB,
    result       JSONB,
    latency_ms   INTEGER NOT NULL DEFAULT 0,
    status       VARCHAR(16) NOT NULL DEFAULT 'DONE',
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_tool_call_log_agent_run_id
    ON tool_call_log (agent_run_id);
