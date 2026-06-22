# Figure Contracts

This file records the drawing contract used to regenerate the report figures. The figures are mechanism/workflow schematics, so the core claim is design-structure evidence rather than numeric experiment evidence.

| Figure | Type | Core claim | Data/source basis | Output |
| --- | --- | --- | --- | --- |
| `fig_system_architecture` | workflow-diagram | The system is organized as a layered local study platform: UI/CLI entry points delegate to FastAPI orchestration, task agents, core services, and file/external-service storage. | `README.md`, `main.py`, `webapp/server.py`, `core/config.py`, `core/llm_router.py`, `core/library.py` | SVG + PNG |
| `fig_learning_workflow` | workflow-diagram | The learning workflow forms a closed loop from PDF ingestion to resource generation, assessment, diagnosis, profile update, and next-step recommendation. | `README.md`, `agents/ingestion_agent.py`, `agents/quiz_agent.py`, `agents/grader_agent.py`, `core/personalization.py`, `core/recommendations.py` | SVG + PNG |
| `fig_agent_collaboration` | mechanism-schematic | Agents are coordinated by a unified model router and exchange durable state through course files rather than direct long-context coupling. | `core/base_agent.py`, `core/llm_router.py`, `agents/*.py`, `core/state.py` | SVG + PNG |
| `fig_module_structure` | mechanism-schematic | The implementation decomposes into seven functional modules that share REST APIs, filesystem state, and model routing. | `webapp/server.py`, `core/*.py`, `agents/*.py` | SVG + PNG |
| `fig_filesystem_data_model` | workflow-diagram | The project uses course-level and week-level filesystem artifacts as the primary data model, with optional generated assets and LightRAG indexes. | `core/library.py`, `core/personalization.py`, `core/telemetry.py`, `README.md` | SVG + PNG |
| `fig_rag_flow` | workflow-diagram | RAG questions use LightRAG when available and deterministically fall back to local retrieval when the external service is unavailable. | `core/rag_client.py`, `webapp/server.py` | SVG + PNG |

Rendering requirements:

- Primary editable source: SVG with text preserved where possible.
- Report raster: PNG at 320 dpi.
- Font: Microsoft YaHei or SimHei on Windows, falling back to Matplotlib sans-serif.
- Minimum intended text size: 8 pt.
- No intentional text overlap or clipping.
