# rag系统

## 功能说明

将金融政策等专业文件构建知识库，通过 agentic rag workflow 精准定位关键信息，再根据这些信息回答用户问题。

## 环境准备

### 数据库准备

本项目使用三个数据库：postgres，redis，milvus。三个数据库都是通过docker启动的容器

其中，milvus的启动参考官网教程：https://milvus.io/docs/zh/install_standalone-windows.md

### 虚拟环境准备

本项目使用uv管理工具。使用通过如下命令下载uv管理工具

```bash
pip install uv
```

然后通过以下命令安装虚拟环境
```bash
uv sync --frozen
```

### 大模型 api key 准备

复制 `conf.example.yaml` 为 `conf.yaml`，复制 `.env.example` 为 `.env`，并配置对应的参数。

## 项目启动

准备工作完成后，启动项目

```bash
python main.py
```
