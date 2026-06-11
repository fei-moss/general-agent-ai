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
    agent_run_id    VARCHAR(64),
    role            VARCHAR(16) NOT NULL,
    content         TEXT NOT NULL,
    token_count     INTEGER NOT NULL DEFAULT 0,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    meta            JSONB NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS ix_message_conversation_id
    ON message (conversation_id);
CREATE INDEX IF NOT EXISTS ix_message_agent_run_id
    ON message (agent_run_id);
CREATE UNIQUE INDEX IF NOT EXISTS uq_message_assistant_per_run
    ON message (agent_run_id, role)
    WHERE agent_run_id IS NOT NULL AND role = 'ASSISTANT';

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

CREATE TABLE IF NOT EXISTS idempotency_record (
    id              VARCHAR(64) PRIMARY KEY,
    user_id         VARCHAR(64) NOT NULL,
    idempotency_key VARCHAR(256) NOT NULL,
    agent_run_id    VARCHAR(64) NOT NULL
        REFERENCES agent_run(id) ON DELETE CASCADE
        DEFERRABLE INITIALLY DEFERRED,
    request_hash    VARCHAR(128) NOT NULL,
    response        JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_idempotency_record_user_key
        UNIQUE (user_id, idempotency_key)
);
CREATE INDEX IF NOT EXISTS ix_idempotency_record_agent_run_id
    ON idempotency_record (agent_run_id);

ALTER TABLE IF EXISTS idempotency_record
    DROP CONSTRAINT IF EXISTS idempotency_record_agent_run_id_fkey;
ALTER TABLE IF EXISTS idempotency_record
    ADD CONSTRAINT idempotency_record_agent_run_id_fkey
    FOREIGN KEY (agent_run_id)
    REFERENCES agent_run(id)
    ON DELETE CASCADE
    DEFERRABLE INITIALLY DEFERRED;

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
    attempt      INTEGER NOT NULL DEFAULT 0,
    latency_ms   INTEGER NOT NULL DEFAULT 0,
    status       VARCHAR(16) NOT NULL DEFAULT 'DONE',
    started_at   TIMESTAMPTZ,
    finished_at  TIMESTAMPTZ,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_tool_call_log_agent_run_id
    ON tool_call_log (agent_run_id);

ALTER TABLE IF EXISTS message
    ADD COLUMN IF NOT EXISTS agent_run_id VARCHAR(64);
CREATE INDEX IF NOT EXISTS ix_message_agent_run_id
    ON message (agent_run_id);
CREATE UNIQUE INDEX IF NOT EXISTS uq_message_assistant_per_run
    ON message (agent_run_id, role)
    WHERE agent_run_id IS NOT NULL AND role = 'ASSISTANT';

ALTER TABLE IF EXISTS tool_call_log
    ADD COLUMN IF NOT EXISTS attempt INTEGER NOT NULL DEFAULT 0;
ALTER TABLE IF EXISTS tool_call_log
    ADD COLUMN IF NOT EXISTS started_at TIMESTAMPTZ;
ALTER TABLE IF EXISTS tool_call_log
    ADD COLUMN IF NOT EXISTS finished_at TIMESTAMPTZ;
