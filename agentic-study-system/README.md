# 基于大模型的个性化学习资源生成与学习多智能体系统

本项目是面向高校课程学习场景的个性化学习工作台。导入课程 PDF 后，系统会围绕同一门课程完成资料解析、分层讲义生成、知识图解、拓展材料、互动测评、学习画像、个性化学习路径和课程资料问答。

项目目录位于本仓库的：

```text
agentic-study-system/
```

## 功能概览

| 功能 | 说明 |
| --- | --- |
| 课程管理 | 新建、选择、重命名、删除课程；每门课程独立保存章节、画像、诊断和学习路径。 |
| PDF 资料接入 | 在 Web 页面拖入或选择课程 PDF，系统会自动创建新的章节。 |
| 分层讲义 | 将 PDF 解析为 `Beginner.md`、`Intermediate.md`、`Advanced.md` 三层中文讲义。 |
| 知识图解 | 根据讲义生成 `Diagrams.md`，包含 Mermaid 知识结构图和辅助图像。 |
| 拓展材料 | 生成 `Extension.md`，提供拓展阅读、应用案例、复习建议等内容。 |
| 智能测评 | 生成 `Quiz.json`、`Quiz.md`、`Answers.md`，支持客观题即时检查和开放题深度反馈。 |
| 学习诊断 | 提交测评后生成 `Feedback.md`，并追加到课程 `Diagnostic.md`。 |
| 学习画像 | 手动填写或从访谈记录中提取学生画像，保存为 `Profile.json` / `Profile.md`。 |
| 个性化路径 | 基于画像、诊断和章节进度生成 `LearningPath.md`。 |
| 知识问答 | 未启动 LightRAG 时使用本地课程资料检索；启动 LightRAG 后使用知识图谱增强检索。 |

## 目录结构

```text
agentic-study-system/
├── agents/              # 各类任务智能体
├── core/                # 配置、模型路由、课程库、PDF/OCR、RAG、画像、安全校验
├── prompts/             # 中文提示词模板
├── webapp/              # FastAPI 后端和原生 HTML/CSS/JS 前端
├── curriculum/          # 课程数据、章节资料和生成结果
├── study/               # 预留学习资料入口
├── scripts/             # 启动脚本，含 LightRAG Server 启动脚本
├── docs/                # 详细使用、部署和测试文档
├── LightRAG/            # 已归并的 LightRAG Server 核心源码
├── config.yaml          # 智能体模型路由和题量等参数
├── requirements.txt     # Python 依赖，包含内嵌 LightRAG editable 安装
├── main.py              # 命令行入口
├── .env.example         # 环境变量模板
└── .env                 # 本地密钥配置，已被 git 忽略
```

## 环境准备

建议使用 Python 3.11 或 3.12。

```powershell
cd agentic-study-system

python -m venv .venv
.\.venv\Scripts\Activate.ps1

python -m pip install --upgrade pip
pip install -r requirements.txt
```

`requirements.txt` 会以 editable 方式安装内嵌的 `LightRAG`：

```text
-e ./LightRAG[api]
```

如果需要 OCR 扫描版 PDF，还需要额外安装 Tesseract OCR 及中文语言包。

## 环境变量

复制模板并填写本地配置：

```powershell
Copy-Item .env.example .env
```

常用配置如下。不要把真实 API Key 写入 README 或提交到 git。

```env
# 主系统大模型提供方：anthropic | openai | vllm
API_PROVIDER=openai

# OpenAI 或 OpenAI-compatible 服务
OPENAI_API_KEY=your_openai_or_compatible_key
OPENAI_BASE_URL=https://api.openai.com/v1

# Anthropic 可选
ANTHROPIC_API_KEY=

# 自部署 vLLM 可选，仅 API_PROVIDER=vllm 时使用
VLLM_BASE_URL=http://localhost:8006/v1
VLLM_API_KEY=EMPTY

# Ollama，本地对话和 LightRAG embedding 默认使用
OLLAMA_HOST=http://localhost:11434

# 主系统调用 LightRAG Server 的地址
LIGHTRAG_BASE_URL=http://127.0.0.1:9621
LIGHTRAG_API_KEY=
LIGHTRAG_DEFAULT_MODE=mix

# LightRAG Server 调用大模型的配置
LIGHTRAG_LLM_API_KEY=your_openai_or_compatible_key
LIGHTRAG_LLM_BASE_URL=https://api.openai.com/v1
LIGHTRAG_LLM_MODEL=gpt-5.4-mini
```

主系统模型名在 `config.yaml` 中配置：

```yaml
api_models:
  anthropic: claude-opus-4-7
  openai: gpt-5.4-mini
  vllm: gpt-oss-120b
```

## 启动方式

### 仅启动主系统

不使用 LightRAG 时也可以正常运行，知识问答会自动回退到本地课程资料检索。

```powershell
python main.py serve --port 8000
```

浏览器访问：

```text
http://127.0.0.1:8000
```

### 启动 LightRAG 增强检索

LightRAG 使用本地 Ollama 的 `nomic-embed-text` 做 embedding。首次使用前先拉取模型：

```powershell
ollama pull nomic-embed-text
```

打开第一个终端，启动 LightRAG Server：

```powershell
cd agentic-study-system
.\scripts\start_lightrag.ps1
```

打开第二个终端，启动主系统：

```powershell
cd agentic-study-system
.\.venv\Scripts\Activate.ps1
python main.py serve --port 8000
```

LightRAG 数据默认保存到：

```text
agentic-study-system\lightrag-data
```

该目录已在 `.gitignore` 中忽略。

## Web 操作流程

### 1. 新建课程

1. 打开 `http://127.0.0.1:8000`。
2. 在左侧“当前课程”区域点击“新建”。
3. 输入课程名称，例如“软件安全”或“人工智能导论”。

课程数据会保存到：

```text
curriculum\<课程slug>\
```

### 2. 导入资料

在左侧“资料接入”区域点击选择 PDF，或直接拖入 PDF。系统会自动创建新的章节：

```text
curriculum\<课程slug>\Week_01\input\*.pdf
```

### 3. 资源中心

每个章节卡片提供这些操作：

| 按钮 | 输出 |
| --- | --- |
| 生成讲义 | `Beginner.md`、`Intermediate.md`、`Advanced.md` |
| 知识图解 | `Diagrams.md`、`assets/*` |
| 拓展材料 | `Extension.md` |
| 测评 | 打开智能测评页签；无题库时可生成题库 |

生成后的文件会出现在章节卡片中，点击文件名即可在右侧“资源中心”预览。

### 4. 智能测评

1. 在章节卡片点击“测评”。
2. 若还没有题库，点击“生成题库”。
3. 客观题可以点击“检查”或“检查客观题”即时反馈。
4. 开放题和论述题作答后，点击“提交深度反馈”。

相关输出：

```text
Week_XX\Quiz.json      # 结构化题库和答案依据
Week_XX\Quiz.md        # 可读题面
Week_XX\Answers.md     # 学生答案
Week_XX\Essay.md       # 综合论述
Week_XX\Feedback.md    # 深度反馈
Diagnostic.md          # 课程级诊断日志
```

### 5. 知识问答

进入“知识问答”页签。

未启动 LightRAG 时，系统会基于当前课程的 Markdown/PDF 做本地检索问答。

启动 LightRAG 后：

1. 点击“索引全部课程资料”。
2. 等待状态显示“知识图谱已就绪”。
3. 选择 `mix`、`hybrid`、`local`、`global` 或 `naive` 模式。
4. 输入课程相关问题并点击“提问”。

索引范围包括所有章节的 PDF、Markdown 和生成资源。

### 6. 学习画像与路径

进入“学习画像”页签。

可手动填写字段，也可以在“自然语言访谈记录 / 学习行为观察”中输入描述，然后点击“从访谈记录提取画像”。

常见输入示例：

```text
我是计算机专业大二学生，Python 基础一般，概率论薄弱。
我更喜欢图解、代码案例和分步骤例题，希望两周内掌握搜索算法和机器学习基础。
```

可用操作：

| 按钮 | 作用 |
| --- | --- |
| 加载画像 | 读取当前课程的 `Profile.json` / `Profile.md` |
| 保存画像 | 保存当前页面填写的画像 |
| 从访谈记录提取画像 | 调用大模型根据访谈、诊断和章节进度生成画像 |
| 生成个性化学习计划 | 生成 `LearningPath.md` |
| 查看学习计划 | 打开已生成的学习路径 |

### 7. 学习诊断

点击顶部“学习诊断”可查看当前课程的 `Diagnostic.md`。测评反馈、画像信号和部分学习行为会持续写入课程日志，用于后续个性化路径规划。

## 命令行用法

Web UI 覆盖主要操作；也可以使用 CLI：

```powershell
python main.py serve --port 8000
python main.py ingest    --week 1 --subject software-security
python main.py explore   --week 1 --subject software-security
python main.py extension --week 1 --subject software-security
python main.py quiz      --week 1 --subject software-security
python main.py grade     --week 1 --subject software-security
```

`--subject` 可传课程 slug 或课程名称；不传时默认使用第一个课程。

## 生成文件说明

```text
curriculum\<课程slug>\
├── subject.json
├── Profile.json
├── Profile.md
├── Diagnostic.md
├── LearningPath.md
├── BehaviorLog.jsonl
└── Week_XX\
    ├── input\*.pdf
    ├── assets\*
    ├── generated_assets\*
    ├── Beginner.md
    ├── Intermediate.md
    ├── Advanced.md
    ├── Diagrams.md
    ├── Extension.md
    ├── Quiz.json
    ├── Quiz.md
    ├── Answers.md
    ├── Essay.md
    └── Feedback.md
```

## Push 前检查

```powershell
git status --short
```

确认以下内容不要提交：

- `.env`，包含真实 API Key
- `.venv/` 或 `venv/`
- `curriculum/**/input/*.pdf`
- `curriculum/**/assets/*`
- `study/inbox/*.pdf`
- `lightrag-data/`
- `__pycache__/`

## 常见问题

**1. 页面提示 LightRAG 未配置或不可用**

确认 `.env` 中有：

```env
LIGHTRAG_BASE_URL=http://127.0.0.1:9621
```

并且已在另一个终端运行：

```powershell
.\scripts\start_lightrag.ps1
```

**2. LightRAG 启动后索引失败**

先确认 Ollama 正在运行，并已拉取 embedding 模型：

```powershell
ollama pull nomic-embed-text
```

`scripts/start_lightrag.ps1` 已固定：

```powershell
EMBEDDING_MODEL=nomic-embed-text
EMBEDDING_DIM=768
```

如果更换 embedding 模型，需要清空 `lightrag-data` 后重新索引。

**3. 大模型报 401 或 invalid api key**

检查 `.env` 中的 `OPENAI_API_KEY`、`OPENAI_BASE_URL`、`LIGHTRAG_LLM_API_KEY`、`LIGHTRAG_LLM_BASE_URL` 是否对应同一个服务商。

**4. 生成讲义或题库时报模型不可用**

检查 `config.yaml` 中当前 provider 对应的模型名是否是服务商实际支持的模型。

## 技术栈

Python · FastAPI · Uvicorn · PyMuPDF · Tesseract OCR · LightRAG · Ollama · OpenAI-compatible API · Mermaid · 原生 HTML/CSS/JS

## 许可证

MIT License
