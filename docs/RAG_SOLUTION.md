# 轻量 RAG 服务方案

> 2026-06-22 边界修正：RAG 第一版不是面向普通用户开放的知识库产品。
> `/rag/*` 仅作为内部资料上传、摄取、验收和调试接口；普通 `/chat`
> 请求不需要也不应该传 `knowledge_base_id`，服务端会按内部配置透明使用知识库。

## 1. 背景与结论

当前 Chat Server 已经完成在线请求层、后台任务层、Pydantic AI Agent 编排层、Postgres、Redis、Queue/Worker 的基础边界。下一阶段如果要让 Agent 回答私有知识、项目文档、业务说明、操作手册等内容,需要补一套 RAG 能力。

本项目规模不会太大,不适合直接引入 RAGFlow、Dify、Flowise 这类完整 RAG 平台。它们适合做独立产品或大型知识库平台,但会带来额外 UI、权限体系、工作流、数据库、队列和运维面,并且和现有 Chat Server 架构重叠。

推荐第一阶段采用轻量自建方案:

```text
Client
  -> FastAPI Chat Service
  -> Pydantic AI Agent
  -> search_knowledge tool
  -> RAG Query Service / Module
  -> Postgres + pgvector

后台:
Document Upload / Import
  -> Queue / Worker
  -> Parser
  -> Chunker
  -> Embedder
  -> Postgres + pgvector
```

核心选择:

| 层级 | 第一阶段选择 | 后续扩展 |
| --- | --- | --- |
| 文档解析 | 先支持 txt / md / plain text,再接 Docling | 复杂 PDF、表格、OCR、PPT、Excel |
| 向量库 | Postgres + pgvector | 数据量或检索 QPS 增大后再评估 Qdrant |
| Pipeline | 项目内轻量实现 | 复杂检索链路再评估 Haystack / LlamaIndex |
| 检索策略 | vector search + metadata filter + citation | hybrid search、rerank、query rewrite |
| Agent 接入 | Pydantic AI tool | MCP tool 或独立 RAG API |
| 执行路径 | ingestion 走 Worker,query 走在线短路径 | 大文件、批量导入、重索引走后台任务 |

一句话:第一阶段不要做完整 RAG 平台,先做一套可靠、可观测、可回滚的轻量 RAG 服务,让 Agent 能查知识库并带引用回答。

## 2. RAG 到底是什么

RAG 是 Retrieval-Augmented Generation,即检索增强生成。它不是一个新的 Agent,也不是一个新的模型,而是一条给模型补充私有上下文的链路。

标准流程:

```text
document
  -> parse
  -> chunk
  -> embed
  -> store
  -> retrieve
  -> build context
  -> answer with citations
```

可以拆成两条链路:

### 2.1 离线构建链路

离线链路负责把知识变成可检索数据:

```text
上传/导入文档
  -> 解析成结构化文本
  -> 按语义或长度切 chunk
  -> 调 embedding model 生成向量
  -> 写入 Postgres + pgvector
  -> 记录 ingestion 状态
```

这条链路可能慢,也可能失败,所以必须走后台任务,不要占用在线 Chat 请求。

### 2.2 在线检索链路

在线链路负责在用户提问时找出相关上下文:

```text
用户问题
  -> Agent 判断需要查知识库
  -> 调用 search_knowledge 工具
  -> query embedding
  -> pgvector top_k 检索
  -> metadata filter / score threshold
  -> 返回 chunks + citations
  -> Agent 基于上下文回答
```

这条链路必须短、快、稳定。失败时应该降级为空检索结果,不能拖垮 Chat 主流程。

## 3. 与现有 Chat 架构的关系

RAG 的职责边界必须清楚:

| 模块 | 应负责 | 不应负责 |
| --- | --- | --- |
| FastAPI Chat Service | 接收请求、创建 run、路由实时/后台路径 | 文档解析、向量计算 |
| Pydantic AI Agent | 决定是否调用 `search_knowledge`,基于结果作答 | 存储知识库、维护向量索引 |
| RAG Service / Module | ingestion、chunk、embed、retrieve、citation | 会话持久化、全局限流、Agent 编排 |
| Postgres + pgvector | 存储文档元数据、chunk、embedding、检索日志 | 承担长任务调度 |
| Redis / Queue | ingestion 队列、状态缓存、重试辅助 | 最终知识库存储 |
| Worker | 文档解析、embedding、重索引 | 在线 SSE 流式输出 |

Agent 只把 RAG 当作工具:

```python
search_knowledge(query: str, filters: dict | None = None) -> list[RetrievedChunk]
```

这样 RAG 可以独立演进,Chat Server 的实时路径也不会被文档处理、重索引、OCR 这些慢任务拖住。

## 4. 技术选型

### 4.1 为什么不直接用重平台

不建议第一阶段直接引入 RAGFlow / Dify / Flowise:

- 功能边界太大,会接管知识库、应用编排、工作流、模型配置甚至 UI。
- 和当前 FastAPI + Pydantic AI + Postgres + Redis + Worker 的架构重叠。
- 后续要对齐现有鉴权、run 状态、限流、审计、事件流时成本高。
- 对当前规模而言,部署、升级、安全、备份和排障负担偏重。

这些平台可以作为参考或独立 PoC,但不应成为第一阶段核心依赖。

### 4.2 为什么第一阶段选 pgvector

本项目已经把 Postgres 作为权威存储。第一阶段使用 pgvector 的好处:

- 少引入一个独立向量数据库,部署简单。
- 文档元数据、chunk、embedding、run 日志可以在同一个事务边界内管理。
- 适合中小规模知识库和可控 QPS 的业务场景。
- 权限、备份、迁移、观测都复用现有 Postgres 体系。

需要注意:

- pgvector 不是无限扩展方案。数据量、embedding 维度、top_k、过滤条件、索引参数都会影响延迟。
- 大规模多租户、高 QPS、复杂 filter 或海量重索引时,再评估 Qdrant。
- pgvector 查询要避免和 Chat 主库争抢资源,必要时可以读写分离或单独 Postgres 实例。

### 4.3 为什么文档解析先轻后重

第一阶段先支持简单格式:

- Markdown
- TXT
- 已抽取的 plain text
- 小规模 PDF 文本抽取

等真实文档类型明确后,再接 Docling。Docling 适合解析复杂 PDF、表格、公式、OCR、阅读顺序等问题,但引入后会增加 CPU/内存开销,应放在 Worker 后台处理。

### 4.4 Haystack / LlamaIndex 的位置

第一阶段不需要马上接 Haystack 或 LlamaIndex。原因是我们要做的最小链路很清晰:

```text
parse -> chunk -> embed -> pgvector -> retrieve -> citation
```

手写轻量 pipeline 更容易保持边界稳定。如果后续出现以下需求,再评估引入:

- 多数据源 connector 很多。
- 检索策略需要快速实验。
- 需要复杂 rerank / router / query transform。
- 需要可配置 pipeline 或多套检索流程。

优先级建议:

1. 先实现项目内轻量 RAG。
2. 检索策略变复杂后评估 Haystack。
3. 数据连接器和索引形态变复杂后评估 LlamaIndex。

## 5. 第一阶段目标

第一阶段只做最小可用 RAG,目标是让 Agent 能可靠地查知识库并带引用回答。

必须完成:

- 创建知识库。
- 导入文档。
- 文档解析为文本。
- 文本切 chunk。
- 调 embedding model。
- chunk + embedding 入库。
- 在线按 query 检索 top_k chunks。
- Agent 通过 `search_knowledge` 调用检索。
- 最终答案能带来源引用。
- ingestion / retrieval 都有日志和状态。

暂不做:

- 完整知识库管理 UI。
- GraphRAG。
- 多向量库抽象。
- 复杂 workflow 编排。
- 全量 connector 生态。
- 用户可视化 pipeline。
- 大规模多租户知识库平台。

## 6. 数据模型设计

建议新增或演进以下表。命名可按项目现有 migration 风格调整。

### 6.1 knowledge_bases

知识库元数据。

| 字段 | 含义 |
| --- | --- |
| `id` | knowledge base id |
| `owner_user_id` | 所属用户或团队 |
| `name` | 知识库名称 |
| `description` | 描述 |
| `status` | active / disabled |
| `created_at` / `updated_at` | 时间 |

第一阶段可以只做用户级或系统级知识库,不做复杂 RBAC。

### 6.2 documents

原始文档记录。

| 字段 | 含义 |
| --- | --- |
| `id` | document id |
| `knowledge_base_id` | 所属知识库 |
| `source_type` | upload / url / manual / api |
| `source_uri` | 原始文件或来源地址 |
| `title` | 文档标题 |
| `content_hash` | 内容 hash,用于去重 |
| `mime_type` | 文件类型 |
| `status` | pending / parsing / embedded / failed |
| `error_message` | 失败原因 |
| `created_at` / `updated_at` | 时间 |

### 6.3 document_chunks

文档切片。

| 字段 | 含义 |
| --- | --- |
| `id` | chunk id |
| `document_id` | 来源文档 |
| `knowledge_base_id` | 冗余字段,便于过滤 |
| `chunk_index` | 文档内序号 |
| `content` | chunk 文本 |
| `content_hash` | chunk 内容 hash |
| `token_count` | 估算 token 数 |
| `page_number` | 页码,没有则为空 |
| `section_title` | 标题路径 |
| `metadata` | JSONB 元数据 |
| `embedding` | vector(dim) |
| `created_at` | 时间 |

索引建议:

```sql
CREATE INDEX idx_document_chunks_kb ON document_chunks (knowledge_base_id);
CREATE INDEX idx_document_chunks_doc ON document_chunks (document_id);
CREATE INDEX idx_document_chunks_meta ON document_chunks USING gin (metadata);
CREATE INDEX idx_document_chunks_embedding_hnsw
  ON document_chunks USING hnsw (embedding vector_cosine_ops);
```

第一阶段如果数据很少,可以先不建 HNSW,但需要在文档中明确上线前必须压测查询延迟。

### 6.4 rag_ingestion_jobs

文档导入任务。

| 字段 | 含义 |
| --- | --- |
| `id` | job id |
| `document_id` | 文档 id |
| `status` | pending / running / succeeded / failed |
| `attempts` | 尝试次数 |
| `started_at` / `finished_at` | 时间 |
| `error_message` | 失败原因 |

### 6.5 rag_retrieval_logs

检索审计与调试。

| 字段 | 含义 |
| --- | --- |
| `id` | log id |
| `agent_run_id` | 对应 run |
| `conversation_id` | 对应会话 |
| `knowledge_base_id` | 查询知识库 |
| `query` | 检索 query |
| `top_k` | 请求数量 |
| `matched_chunk_ids` | 命中的 chunk ids |
| `scores` | 相似度分数 |
| `latency_ms` | 检索耗时 |
| `degraded` | 是否降级 |
| `created_at` | 时间 |

## 7. 离线构建链路

### 7.1 文档导入

入口可以先做两种:

1. API 导入文本:

```http
POST /rag/documents
Content-Type: application/json

{
  "knowledge_base_id": "kb_xxx",
  "title": "项目说明",
  "content": "...markdown or text...",
  "metadata": {
    "source": "manual"
  }
}
```

2. 文件上传:

```http
POST /rag/documents/upload
Content-Type: multipart/form-data
```

第一阶段建议先做 JSON 文本导入,再做文件上传。这样可以先打通核心 RAG 链路,避免一开始被文件存储和复杂 parser 卡住。

### 7.2 入队与后台处理

API 收到文档后只做:

- 鉴权。
- 参数校验。
- 写 `documents`。
- 创建 `rag_ingestion_jobs`。
- 入队。
- 返回 `document_id` 和 `job_id`。

Worker 负责:

```text
load document
  -> parse
  -> normalize
  -> chunk
  -> batch embed
  -> upsert chunks + embeddings
  -> mark document embedded
```

不要在 HTTP 请求里直接解析大文件或调用 embedding API。

### 7.3 Parser

第一阶段 parser 接口:

```python
class DocumentParser(Protocol):
    async def parse(self, document: RawDocument) -> ParsedDocument:
        ...
```

返回结构:

```python
class ParsedDocument(BaseModel):
    title: str | None
    text: str
    sections: list[ParsedSection] = []
    metadata: dict = {}
```

初始实现:

- `PlainTextParser`
- `MarkdownParser`
- `SimplePdfParser` 可选

后续实现:

- `DoclingParser`

### 7.4 Chunking

第一阶段策略:

- 默认 500-800 tokens 或约 800-1200 中文字符。
- overlap 80-150 tokens 或约 100-200 中文字符。
- 尽量按标题、段落、句子边界切。
- 每个 chunk 保留来源 metadata: document_id、page、section、offset。

不要只按固定字符硬切。当前 `app/rag/chunker.py` 已有轻量 chunker,可以作为第一版基础,后续补 token-aware 和结构化切分。

### 7.5 Embedding

第一阶段需要把 embedding provider 和 chat LLM provider 分开配置。

建议配置:

```env
EMBEDDING_PROVIDER=openai
EMBEDDING_MODEL=text-embedding-3-small
EMBEDDING_DIM=1536
EMBEDDING_BATCH_SIZE=64
EMBEDDING_TIMEOUT_S=30
```

原则:

- 测试环境可以继续用 deterministic hash embedder。
- 生产环境必须使用真实 embedding model。
- embedding API 也要走 provider/model 级限流。
- 入库前校验向量维度,维度不一致直接失败。
- 更换 embedding model 不能直接覆盖旧索引,需要新建 index version。

## 8. 在线检索链路

### 8.1 Query API

建议先提供内部 API:

```http
POST /rag/query
Content-Type: application/json

{
  "knowledge_base_id": "kb_xxx",
  "query": "如何接入高并发 Chat Server?",
  "top_k": 5,
  "filters": {
    "source_type": "manual"
  }
}
```

返回:

```json
{
  "chunks": [
    {
      "chunk_id": "chk_xxx",
      "document_id": "doc_xxx",
      "title": "高并发 Chat 架构",
      "content": "...",
      "score": 0.82,
      "citation": {
        "source_uri": "docs/ARCHITECTURE.md",
        "page": null,
        "section": "实时路径"
      }
    }
  ],
  "degraded": false,
  "latency_ms": 35
}
```

### 8.2 检索策略

第一阶段:

```text
query
  -> query embedding
  -> pgvector cosine top_k
  -> metadata filter
  -> score threshold
  -> return chunks
```

建议默认:

- `top_k=5`
- `max_context_chars=6000`
- `score_threshold` 先配置化,不要写死。
- 如果结果为空,返回 `degraded=false, chunks=[]`,由 Agent 决定如何回答。
- 如果检索超时或异常,返回 `degraded=true`,主对话链路继续。

第二阶段再加:

- Postgres full-text search / BM25-like lexical search。
- vector + keyword hybrid merge。
- reranker。
- query rewrite。
- multi-query retrieval。

### 8.3 Context Builder

检索结果不能直接无限塞给模型,需要构造上下文:

```text
sort by score
  -> remove duplicate chunks
  -> group by document
  -> trim to max_context_chars
  -> attach citation markers
```

示例上下文:

```text
[source: doc_1#chunk_3 title="高并发 Chat 架构" section="实时路径"]
实时请求走 FastAPI + Pydantic AI run_stream,流式期间不持有 DB 连接...

[source: doc_2#chunk_1 title="Provider 限流" section="P0"]
真实 LLM 接入前必须做 provider/model 级 RPM/TPM 限流...
```

Agent 回答时必须能引用这些 source id。

## 9. Agent 接入方式

现有 `app/runtime/agent_factory.py` 已经有 `search_knowledge` 工具。下一步不是重新设计 Agent,而是把工具背后的 RAG 实现换成真实服务。

### 9.1 工具契约

建议工具返回统一结构:

```python
class KnowledgeSearchResult(BaseModel):
    chunk_id: str
    document_id: str
    title: str | None
    content: str
    score: float
    citation: dict
    metadata: dict
```

工具行为:

- 输入 query 和 filters。
- 使用当前用户或 conversation 绑定的 knowledge base。
- 调用 RAG Query Service。
- 写 `rag_retrieval_logs`。
- 返回有限数量 chunk。

### 9.2 Prompt 约束

Agent system prompt 需要补充:

- 需要私有知识、项目资料、文档说明时,先调用 `search_knowledge`。
- 有检索结果时,优先基于检索内容回答。
- 检索结果不足时,明确说明依据不足。
- 不要编造引用。
- 输出中保留简洁来源说明。

### 9.3 实时路径

实时 Chat:

```text
POST /chat
  -> create run
  -> agent.run_stream()
  -> Agent calls search_knowledge
  -> RAG query returns chunks
  -> token streaming
  -> persist answer + retrieval log
```

约束:

- RAG query 必须有短超时,例如 1-2 秒。
- 检索失败不能让 run 永久卡住。
- 检索期间不长持有 DB 连接。
- 检索日志可以异步写,但最终 run 需要能追踪到命中过哪些 chunk。

### 9.4 后台路径

长 RAG / 文件分析 / 批量问答:

```text
POST /chat mode=batch
  -> create run
  -> enqueue
  -> Worker agent.run()
  -> search_knowledge / long retrieval
  -> persist final output
```

适合:

- 大知识库检索。
- 多轮 query rewrite。
- 多文档综合。
- 需要 rerank。
- 需要较长工具链。

## 10. API 设计

第一阶段建议只做内部最小 API。

### 10.1 创建知识库

```http
POST /rag/knowledge-bases
```

```json
{
  "name": "项目文档",
  "description": "general-agent-ai 项目说明"
}
```

### 10.2 导入文档

```http
POST /rag/documents
```

```json
{
  "knowledge_base_id": "kb_xxx",
  "title": "架构文档",
  "content": "...",
  "metadata": {
    "source_uri": "docs/ARCHITECTURE.md"
  }
}
```

返回:

```json
{
  "document_id": "doc_xxx",
  "job_id": "job_xxx",
  "status": "pending"
}
```

### 10.3 查询导入状态

```http
GET /rag/documents/{document_id}
GET /rag/ingestion-jobs/{job_id}
```

### 10.4 检索

```http
POST /rag/query
```

这个接口主要给 Agent tool 和内部调试使用,不一定要开放给外部用户。

## 11. 搭建步骤

### Step 1: 启用 pgvector

Postgres 需要安装 pgvector extension:

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

本地 Docker 环境如果当前 Postgres 镜像不带 pgvector,有两个选择:

1. 替换为带 pgvector 的 Postgres 镜像。
2. 单独构建带 pgvector extension 的镜像。

### Step 2: 加 migration

新增:

- `knowledge_bases`
- `documents`
- `document_chunks`
- `rag_ingestion_jobs`
- `rag_retrieval_logs`

并给 `document_chunks.embedding` 建 vector 类型字段。

### Step 3: 实现 PgVectorStore

当前 `app/rag/vector_store.py` 里有 `PgVectorStore` 骨架。需要实现:

```python
async def add(self, docs: list[dict[str, Any]]) -> None
async def search(self, query_vec: list[float], top_k: int) -> list[tuple[dict, float]]
```

注意:

- 使用短事务,不要在 embedding API 调用期间持有 DB 连接。
- 批量 upsert chunks。
- search 支持 knowledge_base_id / document_id / metadata filters。
- 返回 score 和 citation metadata。

### Step 4: 拆分 Embedder 配置

当前 embedding 逻辑和 settings 里的 `llm_provider` 有一定耦合。需要独立:

- `embedding_provider`
- `embedding_model`
- `embedding_dim`
- `embedding_batch_size`
- `embedding_api_key`
- `embedding_base_url`

并接入已有 secret management 和 provider/model rate limit。

### Step 5: 实现 ingestion worker

新增任务:

```text
rag_ingest_document(document_id)
```

处理:

1. mark job running。
2. load document。
3. parse。
4. chunk。
5. batch embed。
6. upsert chunks。
7. mark document embedded。
8. failed 时记录 error,按策略重试。

### Step 6: 实现 RAG Query Service

可以先做项目内 service:

```python
class RAGQueryService:
    async def query(
        self,
        knowledge_base_id: str,
        query: str,
        top_k: int,
        filters: dict | None,
        agent_run_id: str | None,
    ) -> RAGQueryResult:
        ...
```

它内部调用 embedder + vector store + retrieval log。

### Step 7: 接入 Agent tool

把 `search_knowledge` 的 retriever 从当前 demo/in-memory 实现替换为真实 `RAGQueryService` 适配器。

保留现有 mock 路径用于测试。

### Step 8: 加测试和 smoke

至少覆盖:

- 文本导入后生成 chunks。
- embedding 维度错误会失败。
- pgvector search 能返回正确 top_k。
- metadata filter 生效。
- Agent 调 `search_knowledge` 后能基于 chunk 回答。
- 检索超时返回 degraded,Chat run 不崩。
- ingestion 失败会记录状态并可重试。

## 12. 配置建议

示例:

```env
RAG_ENABLED=true
RAG_VECTOR_STORE=pgvector
RAG_DEFAULT_TOP_K=5
RAG_MAX_CONTEXT_CHARS=6000
RAG_QUERY_TIMEOUT_MS=1500
RAG_SCORE_THRESHOLD=0.2

EMBEDDING_PROVIDER=openai
EMBEDDING_MODEL=text-embedding-3-small
EMBEDDING_DIM=1536
EMBEDDING_BATCH_SIZE=64
EMBEDDING_TIMEOUT_S=30

RAG_INGESTION_QUEUE=q.rag
RAG_INGESTION_MAX_RETRIES=3
```

## 13. 可观测性

RAG 必须能调试,否则回答质量出问题时无法定位。

指标:

| 指标 | 含义 |
| --- | --- |
| `rag_ingestion_jobs_total` | ingestion 任务数 |
| `rag_ingestion_failures_total` | ingestion 失败数 |
| `rag_ingestion_duration_seconds` | ingestion 耗时 |
| `rag_chunks_total` | chunk 数 |
| `rag_embedding_request_seconds` | embedding 请求耗时 |
| `rag_query_seconds` | 在线检索耗时 |
| `rag_query_degraded_total` | 检索降级次数 |
| `rag_retrieved_chunks` | 单次返回 chunk 数 |
| `rag_empty_result_total` | 空结果次数 |

日志:

- document_id
- knowledge_base_id
- job_id
- agent_run_id
- query hash,不要默认打印完整敏感 query
- top_k
- matched chunk ids
- latency_ms
- degraded reason

## 14. 安全与权限

第一阶段也要守住几条底线:

- 用户只能检索自己有权限的 knowledge base。
- Agent tool 调 RAG 时必须带 user_id / conversation_id / run_id 上下文。
- 文档原文可能包含敏感信息,日志不要打印完整 chunk。
- 原始文件不建议直接进 git 或镜像。
- 删除文档时要删除对应 chunks 和 embeddings。
- 如果支持团队知识库,需要明确 owner/team scope。

## 15. 阶段计划

### P0: 最小可用链路

目标:让 Agent 能查一批内部文档并带引用回答。

- pgvector migration。
- PgVectorStore。
- 文本导入 API。
- ingestion worker。
- embedding provider 独立配置。
- RAG query service。
- Agent tool 接入。
- 基础 retrieval log。

### P1: 文档能力增强

目标:支持真实业务文档。

- 文件上传。
- Docling parser。
- PDF/DOCX/PPT/XLSX 支持。
- 结构化 chunk。
- page/section citation。
- ingestion retry / reindex。

### P2: 检索质量增强

目标:提升命中率和答案质量。

- hybrid search。
- reranker。
- query rewrite。
- score calibration。
- answer citation enforcement。
- RAG evaluation dataset。

### P3: 规模与运维增强

目标:支撑更大数据量和更高 QPS。

- Qdrant 评估。
- 索引版本管理。
- 批量重建索引。
- embedding cache。
- 多 knowledge base 权限模型。
- dashboard 和告警。

## 16. 第一阶段验收标准

功能验收:

- 能创建 knowledge base。
- 能导入至少 3 篇 Markdown/TXT 文档。
- ingestion 后 chunks 和 embeddings 入库。
- `/rag/query` 能返回相关 chunk。
- Agent 能调用 `search_knowledge`。
- 最终回答包含来源引用。
- 检索失败时 Chat run 不失败。

性能验收:

- 小规模知识库下,`/rag/query` p95 < 300ms,不含 embedding provider 网络波动。
- RAG 工具调用总耗时 p95 < 1500ms。
- ingestion 不占用在线请求 DB 连接。

质量验收:

- 命中 chunk 可解释,能看到 document/title/section/page。
- 无结果时不编造。
- 引用来源必须来自检索结果。

运维验收:

- ingestion job 有状态。
- retrieval log 可追踪。
- embedding key 不进仓库。
- provider/model 限流覆盖 embedding 请求。

## 17. 参考资料

- Docling: <https://github.com/docling-project/docling>
- pgvector: <https://github.com/pgvector/pgvector>
- Qdrant: <https://github.com/qdrant/qdrant>
- Haystack: <https://github.com/deepset-ai/haystack>
- LlamaIndex: <https://github.com/run-llama/llama_index>
