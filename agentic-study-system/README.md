# 基于大模型的个性化资源生成与学习多智能体系统

本项目是面向高校课程学习场景的个性化学习资源生成系统。上传课程 PDF 后，多个智能体协作生成中文学习讲义、知识图解、拓展材料、测评题库、学习画像和个性化学习路径。

## 功能概览

| 功能 | 说明 |
| --- | --- |
| 课程管理 | 新建、选择、重命名、删除课程；每门课程下按章节管理资料。 |
| PDF 资料接入 | 上传课程 PDF，系统自动建立章节。 |
| 生成讲义 | 将 PDF 整理为三层中文讲义：基础层、应用层、提升层。 |
| 知识图解 | 根据讲义生成 Mermaid 知识结构图，支持缩放。 |
| 拓展材料 | 生成拓展阅读方向、实操案例和复习建议。 |
| 智能测评 | 生成结构化题库，支持答案反馈与诊断。 |
| 知识问答 | 基于课程资料问答；配置 LightRAG 后使用知识图谱增强检索。 |
| 学习画像 | 根据访谈、诊断记录和学习进度构建动态学习画像。 |
| 个性化学习计划 | 根据画像和课程进度生成个性化学习路径。 |

## 多智能体设计

每个智能体负责一个明确任务，通过文件和 API 协作，不依赖复杂 agent 框架。

| 智能体 | 文件 | 作用 |
| --- | --- | --- |
| 讲义生成 | `agents/ingestion_agent.py` | 解析 PDF，生成三层讲义 |
| 知识图解 | `agents/web_explorer.py` | 生成 Mermaid 知识结构图 |
| 拓展材料 | `agents/extension_agent.py` | 生成拓展阅读、实操案例 |
| 测评 | `agents/quiz_agent.py` | 生成分层题库和答案模板 |
| 诊断反馈 | `agents/grader_agent.py` | 根据答案生成学习诊断 |
| 学习画像 | `agents/profile_agent.py` | 构建和更新学生画像 |
| 路径规划 | `agents/path_planner.py` | 生成个性化学习路径 |

所有模型调用统一经过 `core/llm_router.py`，配置集中在 `config.yaml`。

## 目录结构

```text
agentic-study-system/
├── agents/          # 各类智能体
├── core/            # 配置、模型路由、PDF 解析、校验、课程管理
├── prompts/         # 中文智能体提示词
├── webapp/          # FastAPI 后端与前端页面
├── curriculum/      # 课程数据与生成结果（git 忽略 PDF 和图片）
├── scripts/         # 启动脚本（含 LightRAG 启动脚本）
├── docs/            # 使用说明文档
├── config.yaml      # 智能体模型路由配置
├── requirements.txt # Python 依赖
├── main.py          # 命令行入口
└── .env.example     # 环境变量模板
```

## 环境准备

**1. 创建 conda 环境**

```powershell
conda create -n agent python=3.11 -y
conda activate agent
```

**2. 安装依赖**

```powershell
pip install -r requirements.txt
```

**3. 配置环境变量**

```powershell
Copy-Item .env.example .env
```

编辑 `.env`，填入你的 API Key：

```env
API_PROVIDER=openai
OPENAI_API_KEY=your_key_here
OPENAI_BASE_URL=https://api.openai.com/v1   # 第三方兼容接口填对应地址

OLLAMA_HOST=http://localhost:11434

LIGHTRAG_BASE_URL=http://127.0.0.1:9621     # 配置 LightRAG 后填写，否则留空
LIGHTRAG_API_KEY=
LIGHTRAG_DEFAULT_MODE=mix

LIGHTRAG_LLM_API_KEY=your_key_here          # LightRAG docker-compose 用，同上
```

`.env` 已加入 `.gitignore`，不会被提交。

## 启动系统

```powershell
python main.py serve --port 8000
```

浏览器访问 `http://127.0.0.1:8000`。

## LightRAG 知识图谱 RAG（可选）

不配置 LightRAG 时，知识问答使用本地词频检索，功能正常但语义理解较弱。配置后使用知识图谱增强检索，效果更好。

**前置条件**

1. 安装 [Ollama](https://ollama.com/download)，拉取 embedding 模型：

```powershell
ollama pull nomic-embed-text
```

2. 确保 `lightrag-hku[api]` 已安装（已包含在 `requirements.txt`）。

**启动 LightRAG Server**

```powershell
.\scripts\start_lightrag.ps1
```

脚本会自动从 `.env` 读取 API Key，启动后监听 `http://127.0.0.1:9621`。

**使用流程**

1. 启动 LightRAG Server（先于主程序启动）
2. 启动主程序 `python main.py serve`
3. 页面"知识问答"标签会显示"LightRAG 服务已连接"
4. 上传 PDF 并生成讲义后，点击**"索引全部课程资料"**
5. 状态栏显示"✅ 知识图谱已就绪"后即可提问

> 每次重新启动 LightRAG 或清空数据后，需要重新索引。

**注意事项**

- LightRAG 数据目录默认为 `D:\lightrag-data`，已加入 `.gitignore`
- 如需更换目录，修改 `scripts/start_lightrag.ps1` 中的 `$workDir`
- `nomic-embed-text` 输出维度为 768，脚本中已通过 `EMBEDDING_DIM=768` 指定，不可更改

## 命令行用法

```powershell
python main.py ingest    --week 1   # 生成分层讲义
python main.py explore   --week 1   # 生成知识图解
python main.py extension --week 1   # 生成拓展材料
python main.py quiz      --week 1   # 生成测评题库
python main.py grade     --week 1   # 生成诊断反馈
```

## Push 前检查

```powershell
git status --short
```

确认以下内容不在提交列表中：

- `.env`（含真实 API Key）
- `curriculum/*/input/*.pdf`（PDF 原文件）
- `curriculum/*/assets/`（页面截图）
- `lightrag-data/`（向量数据库）
- `__pycache__/`

## 技术栈

Python · FastAPI · Uvicorn · PyMuPDF · LightRAG · Ollama · OpenAI-compatible API · Mermaid · 原生 HTML/CSS/JS

## 许可证

MIT License
