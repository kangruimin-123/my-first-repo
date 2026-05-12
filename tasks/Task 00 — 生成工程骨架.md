## Goal

生成 bdc-ai-agent-service 完整工程目录，所有模块为空壳，/ask 端点返回最小桩响应，pytest 可运行。

## Input

- AGENTS.md

## Files 允许创建

```text
bdc-ai-agent-service/
├── README.md
├── pyproject.toml
├── app.py
├── config/
│   ├── settings.yaml
│   ├── enabled_tools.yaml
│   ├── metric_dictionary.yaml
│   ├── dimension_mapping.yaml
│   ├── field_mapping.yaml
│   ├── project_alias.yaml
│   ├── event_dictionary.yaml
│   ├── value_alias_mapping.yaml
│   ├── business_conventions.yaml
│   ├── prompts/
│   │   ├── VERSION
│   │   ├── CHANGELOG.md
│   │   ├── system_prompt.md
│   │   ├── task_prompt_metric_query.md
│   │   ├── task_prompt_metric_diagnosis.md
│   │   ├── task_prompt_dashboard_query.md
│   │   ├── task_prompt_report_generate.md
│   │   └── task_prompt_follow_up.md
│   └── analysis_templates/
│       └── funnel_analysis.yaml
├── entry/__init__.py
├── entry/entry_handler.py
├── entry/schemas.py
├── intent/__init__.py
├── intent/intent_router.py
├── intent/schemas.py
├── semantic/__init__.py
├── semantic/entity_normalizer.py
├── semantic/metadata_adapter.py
├── semantic/semantic_validator.py
├── semantic/query_config_builder.py
├── semantic/date_parser.py
├── semantic/ambiguity_detector.py
├── session/__init__.py
├── session/session_state_manager.py
├── session/session_store.py
├── resolution/__init__.py
├── resolution/resolution_policy.py
├── resolution/schemas.py
├── agent_runtime/__init__.py
├── agent_runtime/agent_runtime_client.py
├── agent_runtime/claude_agent_client.py
├── agent_runtime/prompt_registry.py
├── reporting/__init__.py
├── reporting/claude_messages_client.py
├── reporting/report_context_builder.py
├── reporting/report_prompt_registry.py
├── reporting/report_formatter.py
├── tools/__init__.py
├── tools/tool_registry.py
├── tools/tool_adapter.py
├── tools/tool_executor.py
├── tools/schemas.py
├── tools/bdc_tools.py
├── harness/__init__.py
├── harness/validator.py
├── harness/permission_guard.py
├── harness/rate_limiter.py
├── harness/kill_switch.py
├── harness/output_guard.py
├── workflows/__init__.py
├── workflows/workflow_engine.py
├── workflows/workflow_registry.py
├── workflows/workflow_defs.py
├── analysis_templates/__init__.py
├── analysis_templates/template_registry.py
├── analysis_templates/template_validator.py
├── analysis_templates/self_service_analysis_adapter.py
├── analysis_templates/template_executor.py
├── execution/__init__.py
├── execution/bdc_backend_client.py
├── execution/bdc_execution_service.py
├── execution/schemas.py
├── evaluation/__init__.py
├── evaluation/evaluation_context.py
├── evaluation/evaluation_repository.py
├── evaluation/evaluated_step.py
├── fallback/__init__.py
├── fallback/fallback_manager.py
└── tests/
    ├── conftest.py
    ├── test_smoke.py
    └── fixtures/
```

## Rules

1. 不接真实 Claude API
2. 不接真实数据库
3. 所有模块只创建空壳（class 定义 + pass 或 raise NotImplementedError）
4. config/*.yaml 使用占位数据（最少 2 个项目、5 个指标）
5. app.py 只实现一个 POST /ask 端点，返回硬编码的最小响应

## Implementation Notes

### pyproject.toml

```toml
[project]
name = "bdc-ai-agent-service"
version = "0.1.0"
requires-python = ">=3.10"
dependencies = [
    "fastapi>=0.100.0",
    "uvicorn>=0.23.0",
    "pydantic>=2.0.0",
    "httpx>=0.24.0",
    "pyyaml>=6.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0.0",
    "pytest-asyncio>=0.21.0",
    "httpx>=0.24.0",
]

[build-system]
requires = ["setuptools>=68.0"]
build-backend = "setuptools.backends._legacy:_Backend"
```

### app.py 最小桩

```python
from fastapi import FastAPI
import uuid

app = FastAPI(title="BDC AI Agent Service")

@app.post("/ask")
async def ask(request: dict):
    return {
        "trace_id": str(uuid.uuid4()),
        "answer_status": "success",
        "execution_mode": "stub",
        "answer": {
            "what": "工程骨架已就绪，尚未实现业务逻辑。",
            "so_what": "",
            "why": "",
            "next": ""
        },
        "data_status": "valid",
        "data_version": "stub_v0",
        "warnings": [],
        "agent_steps": []
    }
```

### tests/test_smoke.py

```python
from fastapi.testclient import TestClient
from app import app

client = TestClient(app)

def test_ask_returns_trace_id():
    response = client.post("/ask", json={
        "user_id": "u001",
        "question": "test",
        "source": "test",
        "project_id": "canglan",
        "session_id": "s001"
    })
    assert response.status_code == 200
    data = response.json()
    assert "trace_id" in data
    assert data["trace_id"] is not None

def test_ask_returns_required_fields():
    response = client.post("/ask", json={
        "user_id": "u001",
        "question": "test",
        "source": "test",
        "project_id": "canglan",
        "session_id": "s001"
    })
    data = response.json()
    assert "answer_status" in data
    assert "data_status" in data
    assert "agent_steps" in data
```

## Acceptance

```bash
pip install -e ".[dev]"
uvicorn app:app --reload      # 可启动
pytest                        # 全绿
```
