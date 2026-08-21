"""Small, fail-closed additive migration runner for DockerHost releases."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from sqlalchemy import text

from app.db.session import dispose_engine, engine


@dataclass(frozen=True)
class Migration:
    version: str
    statements: tuple[str, ...]


MIGRATIONS = (
    Migration(
        version="20260727_001_production_readiness",
        statements=(
            """
            CREATE TABLE IF NOT EXISTS conversation_anchor (
                id VARCHAR(64) PRIMARY KEY,
                conversation_id VARCHAR(64) NOT NULL
                    REFERENCES conversation(id) ON DELETE CASCADE,
                user_id VARCHAR(64) NOT NULL,
                anchor_type VARCHAR(64) NOT NULL,
                anchor_key VARCHAR(256) NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                CONSTRAINT uq_conversation_anchor_user_type_key
                    UNIQUE (user_id, anchor_type, anchor_key)
            )
            """,
            """
            CREATE INDEX IF NOT EXISTS ix_conversation_anchor_conversation_id
            ON conversation_anchor (conversation_id)
            """,
            """
            ALTER TABLE agent_run
            ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ
            """,
            """
            UPDATE agent_run
            SET created_at = COALESCE(started_at, finished_at, now())
            WHERE created_at IS NULL
            """,
            """
            ALTER TABLE agent_run
            ALTER COLUMN created_at SET DEFAULT now()
            """,
            """
            ALTER TABLE agent_run
            ALTER COLUMN created_at SET NOT NULL
            """,
            """
            ALTER TABLE rag_ingestion_job
            ADD COLUMN IF NOT EXISTS dispatch_attempts INTEGER NOT NULL DEFAULT 0
            """,
            """
            ALTER TABLE rag_ingestion_job
            ADD COLUMN IF NOT EXISTS last_dispatched_at TIMESTAMPTZ
            """,
            """
            CREATE INDEX IF NOT EXISTS ix_rag_ingestion_dispatch
            ON rag_ingestion_job (status, last_dispatched_at, created_at)
            """,
        ),
    ),
    Migration(
        version="20260821_001_rag_embedding_dimensionless",
        statements=(
            # Drop first so ALTER TYPE never attempts to rebuild a
            # dimension-typed ANN index against the dimensionless column.
            """
            DROP INDEX IF EXISTS ix_rag_chunk_embedding_hnsw
            """,
            """
            ALTER TABLE rag_document_chunk
            ALTER COLUMN embedding TYPE vector
            """,
        ),
    ),
)


async def migrate() -> None:
    """Apply each repository-owned additive migration exactly once."""
    async with engine.begin() as connection:
        await connection.execute(text("SET LOCAL lock_timeout = '5s'"))
        await connection.execute(text("SET LOCAL statement_timeout = '120s'"))
        await connection.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS schema_migration (
                    version VARCHAR(128) PRIMARY KEY,
                    applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
                )
                """
            )
        )
        for migration in MIGRATIONS:
            applied = await connection.scalar(
                text("SELECT 1 FROM schema_migration WHERE version = :version"),
                {"version": migration.version},
            )
            if applied:
                continue
            for statement in migration.statements:
                await connection.execute(text(statement))
            await connection.execute(
                text(
                    """
                    INSERT INTO schema_migration (version)
                    VALUES (:version)
                    ON CONFLICT (version) DO NOTHING
                    """
                ),
                {"version": migration.version},
            )


async def _amain() -> None:
    try:
        await migrate()
    finally:
        await dispose_engine()


def main() -> None:
    asyncio.run(_amain())


if __name__ == "__main__":
    main()
