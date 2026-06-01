# RAG 金融政策问答系统

将金融政策等专业文件构建知识库，通过 Agentic RAG Workflow 精准定位关键信息，再根据这些信息回答用户问题。

## 技术栈

- **Web 框架**: FastAPI + Uvicorn
- **工作流编排**: LangGraph
- **LLM**: 支持 DeepSeek / 阿里云 DashScope / OpenAI 兼容接口
- **向量数据库**: Milvus (standalone)
- **关系数据库**: PostgreSQL
- **缓存**: Redis
- **包管理**: uv

## 环境准备

### 1. 安装 uv 包管理工具

```bash
pip install uv
```

### 2. 安装 Python 依赖

```bash
uv sync --frozen
```

### 3. 配置环境变量

```bash
cp .env.example .env
```

然后编辑 `.env`，填入真实的 API Key 和模型配置：

| 配置项 | 说明 |
|--------|------|
| `CHAT_MODEL` | 对话模型名称，如 `deepseek-chat` |
| `CHAT_API_KEY` | 对话模型 API Key |
| `CHAT_BASE_URL` | 对话模型 API 地址，如 `https://api.deepseek.com/v1` |
| `EMBEDDING_MODEL` | Embedding 模型名称 |
| `EMBEDDING_API_KEY` | Embedding 模型 API Key |
| `JWT_SECRET_KEY` | JWT 加密密钥，随便填一个字符串 |
| `POSTGRES_URL` | PostgreSQL 连接串，与 docker-compose 中配置保持一致 |
| `MILVUS_DATABASE` | 默认填写 `default` |

其余数据库配置（Redis、Milvus 地址端口等）保持默认即可。

### 4. 启动数据库

通过 Docker Compose 启动数据库服务（**注意不要启动 app 服务，app 通过本地 `python main.py` 运行**）：

```bash
docker-compose up -d postgres redis etcd minio milvus
```

包含的数据库服务：

| 服务 | 镜像 | 端口 |
|------|------|------|
| PostgreSQL | postgres:15-alpine | 5432 |
| Redis | redis:7-alpine | 6379 |
| Milvus | milvusdb/milvus:v2.5.4 | 19530 |
| etcd（Milvus 依赖） | quay.io/coreos/etcd:v3.5.5 | 2379 |
| MinIO（Milvus 依赖） | minio/minio | 9000 |

> **注意**：Milvus 镜像必须使用 **v2.4 及以上**版本（项目固定 v2.5.4），因为 pymilvus 2.5+ 移除了 gRPC 支持，仅使用 RESTful API，而 Milvus v2.3 及更早版本不支持 RESTful。

### 5. 确认服务健康

```bash
docker-compose ps
```

所有服务状态显示 `healthy` 即为正常。

## 项目启动

```bash
python main.py
```

启动后访问：
- API 文档：http://localhost:8000/docs
- 健康检查：http://localhost:8000/health

## 停止项目

```bash
# 停止应用：Ctrl+C

# 停止数据库容器
docker-compose down
```
