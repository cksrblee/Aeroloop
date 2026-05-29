# AeroLoop

**AeroLoop**는 eVTOL / UAM 항공기의 개념 설계 자동화 및 시뮬레이션 검증을 위한 멀티 에이전트 플랫폼입니다.

자연어 임무 입력 → 요구도 분석 → 규정 검토 → 형상 설계 → 3D 비행 시뮬레이션 → Runtime Requirement Verification 전 과정을 AI 에이전트 파이프라인으로 자동화합니다.

---

## 환경 설정

```bash
conda activate aero
pip install -e .
```

환경 변수 설정:

```bash
conda env config vars set OPENAI_API_KEY="sk-..."
conda deactivate && conda activate aero
```

---

## Langfuse Prompt Registration

`scripts/register_prompts.py` registers the default prompts used by AeroLoop agents.

Required Langfuse environment variables:

```bash
conda env config vars set LANGFUSE_PUBLIC_KEY="pk-lf-..."
conda env config vars set LANGFUSE_SECRET_KEY="sk-lf-..."
conda env config vars set LANGFUSE_HOST="https://cloud.langfuse.com"
conda deactivate && conda activate aero
```

Register prompts from the `aero` conda environment:

```bash
conda activate aero
python scripts/register_prompts.py
```

To verify the registration payload without calling Langfuse:

```bash
python scripts/register_prompts.py --dry-run
```

Registered prompt names:

| Prompt | Label |
|---|---|
| `aeroloop/mission-parsing-agent` | `staging` |
| `aeroloop/customer-requirement-agent` | `staging` |

Use `--label <label>` to register a different Langfuse label.

---

## CLI: `aero-run`

각 에이전트를 개별적으로 실행하고 결과를 `.agents/` 디렉토리에 저장합니다.

### MissionParsingAgent 실행

자연어 임무 설명을 구조화된 Mission Profile로 변환합니다.

```bash
aero-run mission "건국대 캠퍼스 안에서 2명이 탑승하는 eVTOL을 기숙사에서 도서관까지 운항하고 싶다. 고도는 120m 이하로 유지하고, 건물과는 최소 10m 이상 떨어져야 한다. 소음은 최대한 줄였으면 좋겠고, 배터리는 도착 시 20% 이상 남아야 한다."
```

**출력 예시:**

```
--- Summary ---
Mission ID: mission_20260514_170737
Operation Area: 건국대 캠퍼스
Origin -> Destination: 기숙사 -> 도서관
Explicit Constraints: 3
Missing Fields: 0

Output saved to: .agents/mission_parsing_result_mission_20260514_170737.json
```

결과 JSON에는 다음이 포함됩니다:

| 항목 | 설명 |
|---|---|
| `mission_profile` | 운항 지역, 출발/목적지, 탑승 인원, 고도/속도 조건 등 |
| `explicit_constraints` | 원문 근거, 연산자, SI 단위 정규화 값 포함 |
| `implicit_constraint_candidates` | 명시되지 않았지만 추론 가능한 제약 후보 |
| `missing_fields` | 누락된 필수 정보 및 보완 질문 |
| `ambiguities` | 수치화되지 않은 모호한 표현 |
| `evidence_spans` | 각 필드의 원문 출처 (Traceability) |
| `requirement_seed_candidates` | 다음 에이전트(CustomerReq, Airspace 등)로 전달할 요구도 씨앗 |
| `runtime_monitoring_candidates` | 시뮬레이션 Runtime Verification에서 감시할 조건 |

---

## 에이전트 파이프라인 (Bidirectional LangGraph)

AeroLoop는 단순 선형적인 파이프라인이 아닌 **양방향 상태 기반 그래프(StateGraph)** 구조를 채택하고 있습니다. 
`Orchestrator Agent`가 중앙 라우터(Hub) 역할을 수행하여, 각 에이전트의 실행 결과를 평가하고 다음 실행할 노드(Agent)를 결정합니다. 정보가 누락되거나 제약조건이 충돌하는 경우 이전 단계로 돌아가서(예: 요구도 분석 -> 임무 분석) 문제를 스스로 해결하는 피드백 루프를 지원합니다.

```text
자연어 임무 입력
       ↓
    [START]
       ↓
+-------------------+
| Orchestrator (Hub)| <----+
+-------------------+      | (상태 평가 및 라우팅 / 건너뛰기, 되돌아가기 지원)
  |   |   |   |   |        |
  v   v   v   v   v        |
 [Mission Parsing] --------+
 [Customer Req]    --------+
 [Certification]   --------+
 [Config Design]   --------+
 [Simulation]      --------+
       ↓
     [END]
```

### Workflow 실행

새로 도입된 `workflow` 명령어를 통해 전체 양방향 그래프를 실행할 수 있습니다:

```bash
aero-run workflow "건국대 캠퍼스 안에서 2명이 탑승하는 eVTOL..."
# 또는
aero-run workflow "demo"
```

---

## 프로젝트 구조

```
src/aeroloop/
├── agents/           # 에이전트 구현
│   ├── base_agent.py
│   ├── mission_parsing_agent.py
│   ├── customer_requirement_agent.py
│   └── ...
├── cli/              # aero-run CLI
│   └── run.py
├── llm/              # LLM 어댑터
│   ├── base.py
│   ├── adapters.py
│   └── factory.py
├── schemas/          # Pydantic 데이터 모델
│   ├── common.py
│   ├── mission.py
│   └── ...
└── utils/
    └── prompt_provider.py

.agents/              # CLI 실행 결과 (gitignore)
Agent-Requirements-Specification/  # 에이전트 요구사항 문서
```
