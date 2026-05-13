# 🤖 Gemma Local Agent — Project Plan

> 2026-05-13 결정사항 기록

---

## 1. 목적

로컬 LLM(llama-server + Gemma 4)을 웹에서 명령해 컴퓨터 작업을 수행하는 agent 시스템 구축. 일상적 작업(파일 정리, 코드 작성, 옵시디언 노트 관리 등)을 위임하는 것이 목표.

---

## 2. 핵심 스택

| Layer | 선택 | 비고 |
|-------|------|------|
| LLM Server | `llama-server.exe` (네이티브, :8080) | OpenAI 호환 API |
| Model | `gemma-4-e4b-it-UD-Q4_K_XL.gguf` | `-ngl 99 -c 8192 --flash-attn on` |
| Backend | FastAPI | 단일 agent + tool-calling 루프 |
| Frontend | Next.js (App Router) + Tailwind + TanStack Query | 모노레포 `frontend/` |
| DB | PostgreSQL 17 (Docker) | 세션·메시지·audit 저장 |
| Migration | `create_all()` (v1) → Alembic (운영 단계) | 초기 단계 |

**제외:** CrewAI(다중 에이전트 과한 오버헤드), Chainlit(전환), Ollama(llama-server로 대체).

---

## 3. 안전 정책 (Tool Permission)

| 도구 | 정책 |
|------|------|
| `workspace/` 내 파일 R/W/목록 | ✅ 자동 |
| `workspace/` 외 파일 접근 | 🚫 차단 |
| 시스템 명령 실행 (shell) | 🔒 승인 모달 필수 |
| 옵시디언 읽기/검색/목록 | ✅ 자동 |
| 옵시디언 쓰기/수정 | 🔒 승인 모달 |
| 모든 호출 | 📋 `audit_log` 기록 |

향후 신뢰 누적 시 명령 실행을 화이트리스트 자동화로 완화 가능.

---

## 4. 아키텍처

```
┌──────────────┐    HTTP/SSE     ┌────────────────────┐
│  Next.js UI  │ ──────────────▶ │  FastAPI Backend   │
│  (frontend/) │ ◀────────────── │  :8000             │
└──────────────┘                 └──┬───────┬──────┬──┘
                                    │       │      │
                          ┌─────────┘       │      └─────────┐
                          ▼                 ▼                ▼
                  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
                  │ llama-server │  │  PostgreSQL  │  │  Tools       │
                  │ :8080 (native)│  │  :5432 (docker)│  │ fs/shell/obs│
                  └──────────────┘  └──────────────┘  └──────────────┘
```

---

## 5. DB 스키마 (v1)

```sql
sessions(
  id          UUID PRIMARY KEY,
  title       TEXT,
  created_at  TIMESTAMPTZ,
  updated_at  TIMESTAMPTZ
)

messages(
  id          UUID PRIMARY KEY,
  session_id  UUID REFERENCES sessions(id) ON DELETE CASCADE,
  role        TEXT,        -- user | assistant | tool
  content     TEXT,
  tool_calls  JSONB,       -- OpenAI tool_calls 포맷 그대로
  created_at  TIMESTAMPTZ
)

audit_log(
  id          UUID PRIMARY KEY,
  session_id  UUID REFERENCES sessions(id) ON DELETE SET NULL,
  event_type  TEXT,        -- tool_call | approval | error
  payload     JSONB,
  created_at  TIMESTAMPTZ
)
```

---

## 6. 폴더 구조

```
gemma-ai-structure/
├── docker-compose.yml       # postgres (qdrant 코멘트)
├── .env                     # LLAMA_BASE_URL, DB_URL, WORKSPACE_DIR, OBSIDIAN_*
├── CLAUDE.md
├── workspace/               # agent 샌드박스
├── backend/
│   ├── requirements.txt
│   └── app/
│       ├── main.py
│       ├── config.py
│       ├── db.py            # SQLAlchemy async
│       ├── models.py        # ORM
│       ├── llm.py           # llama-server (OpenAI 호환) 클라이언트
│       ├── agent.py         # tool-calling 루프
│       ├── tools/
│       │   ├── registry.py
│       │   ├── fs.py
│       │   ├── shell.py     # 승인 큐 연동
│       │   └── obsidian.py
│       └── routes/
│           ├── chat.py
│           ├── approvals.py
│           └── sessions.py
└── frontend/                # Next.js App Router
    ├── package.json
    ├── app/
    ├── components/
    └── lib/
```

---

## 7. 환경변수 (`.env`)

```ini
# LLM
LLAMA_BASE_URL=http://localhost:8080/v1
LLAMA_MODEL=gemma-4-e4b-it

# DB
DATABASE_URL=postgresql+asyncpg://gemma:gemma@localhost:5432/gemma

# Agent
WORKSPACE_DIR=./workspace

# Obsidian (옵션)
OBSIDIAN_API_KEY=...
OBSIDIAN_HOST=127.0.0.1
OBSIDIAN_PORT=27124
```

---

## 8. 단계별 로드맵

| Phase | 내용 | 산출물 |
|-------|------|--------|
| **0. 정리** | 옛 파일 삭제, `backend/`·`frontend/` 생성, `.env`/`CLAUDE.md`/`docker-compose.yml` 갱신 | clean slate |
| **1. 인프라** | docker-compose에 postgres 추가, 기동 확인 | DB 컨테이너 |
| **2. 백엔드 골격** | FastAPI + `/health` + llama-server 핑 | 서버 동작 |
| **3. DB 연결** | SQLAlchemy 세팅, `create_all()` | 테이블 생성 |
| **4. Agent 루프** | tool-calling 기본 동작, fs 도구만 우선 | 단순 채팅 + 파일 조작 |
| **5. 승인 시스템** | shell 도구 + 승인 큐 + 승인 라우트 | 안전한 명령 실행 |
| **6. SSE 스트리밍** | 토큰/도구호출/승인요청 이벤트 emit | 실시간 UI 가능 |
| **7. 프런트엔드** | Next.js 스캐폴딩, 채팅 UI + 승인 모달 | 통합 데모 |
| **8. 마무리** | `.env.example`, README, 실행 스크립트 | 재현 가능 |

---

## 9. 미결 / 향후 검토

- **장기 기억 (RAG)**: Qdrant 도입 시점 (현재 docker-compose에 코멘트로 보존)
- **인증**: 로컬 단독 사용 가정 → v1 생략, 외부 노출 시 도입
- **명령 화이트리스트**: 신뢰 누적 후 도입
- **Alembic**: 스키마 안정화 시점에 도입
