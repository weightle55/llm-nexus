# llm-nexus

로컬 LLM(llama-server + Gemma 4)을 웹 채팅으로 명령해 컴퓨터 작업을 수행하는 단일-에이전트 시스템.

- **Backend**: FastAPI + SQLAlchemy async + OpenAI tool-calling 루프 (`backend/`)
- **Frontend**: Next.js 15 (App Router) + Tailwind + TanStack Query (`frontend/`)
- **LLM**: llama-server (네이티브, OpenAI 호환)
- **DB**: PostgreSQL 17 (Docker)

세션·메시지·승인·도구 호출 audit 까지 모두 DB 에 저장. SSE 로 토큰 스트리밍, `shell_exec` 같은 위험 도구는 승인 모달을 거쳐서만 실행.

> 📒 단계별 설계 로그는 [`plan/plan.md`](plan/plan.md), 일자별 작업 기록은 [`plan/2026-*-progress.md`](plan/).

---

## 빠른 시작

### 0. 사전 준비

| 도구 | 비고 |
|------|------|
| Python 3.11+ | `.venv` 권장 |
| Node.js 20+ | (v24 에서 동작 확인) |
| Docker Desktop | Postgres 용 |
| llama-server (llama.cpp 빌드) | `llama-server.exe` 가 PATH 또는 프로젝트 루트에 |
| GGUF 모델 | 예: `gemma-4-e4b-it-UD-Q4_K_XL.gguf` |

```powershell
# 1) 가상환경
python -m venv .venv
.\.venv\Scripts\pip install -r backend\requirements.txt

# 2) 프런트엔드 의존성
cd frontend
npm install
cd ..

# 3) 환경변수
copy .env.example .env
# 필요한 값(LLAMA_MODEL, 모델 경로 등) 채우기
```

### 1. 네 스택 기동

4 개 스택을 각각 별도 터미널에서 (또는 `start-all.ps1` 한 방으로) 띄움.

```powershell
# (1) llama-server — GPU 점유, 별도 터미널 권장
.\llama-server.exe `
  -m "F:\development\ai-models\gemma-4-e4b-it-UD-Q4_K_XL\gemma-4-e4b-it-UD-Q4_K_XL.gguf" `
  -ngl 99 -c 8192 --flash-attn on --port 11434

# (2) PostgreSQL
docker compose up -d postgres

# (3) FastAPI 백엔드
.\.venv\Scripts\uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload

# (4) Next.js 프런트엔드
cd frontend
npm run dev          # http://localhost:3000
```

또는 한 방에:

```powershell
.\start-all.ps1      # llama-server 는 직접, 나머지 3 개 자동
```

### 2. 헬스체크

```powershell
curl http://localhost:8000/health        # 정적 정보
curl http://localhost:8000/health/llm    # llama-server /v1/models 핑
curl http://localhost:8000/health/db     # Postgres SELECT 1
```

세 개 모두 `{"status":"ok",...}` 면 사용 준비 완료.

### 3. 사용

브라우저 → http://localhost:3000

1. 사이드바 "New chat" → 세션 생성
2. 메시지 입력 → SSE 로 토큰 스트리밍
3. `shell_exec` 같은 승인 도구 호출 시 모달이 떠서 Approve/Deny 결정 → 자동으로 resume

---

## 안전 정책

| 동작 | 권한 |
|------|------|
| `workspace/` 내부 R/W | 자동 허용 |
| `workspace/` 외부 접근 | **차단** |
| 시스템 명령 (`shell_exec`) | **승인 모달 필수** |
| 옵시디언 읽기·검색 | 자동 |
| 옵시디언 쓰기·수정 | **승인 모달 필수** |
| 모든 도구 호출 | `audit_log` 테이블 기록 |

자세한 룰: [`backend/app/tools/`](backend/app/tools/).

---

## 폴더 구조

```
llm-nexus/
├── backend/                # FastAPI (Python)
│   ├── alembic/            # DB 마이그레이션 (env.py + versions/)
│   ├── alembic.ini
│   └── app/
│       ├── main.py         # 엔트리, CORS, 라우터 마운트
│       ├── config.py       # pydantic-settings, .env 로드
│       ├── db.py           # SQLAlchemy async engine + lifespan 자동 alembic upgrade
│       ├── models.py       # Session/Message/Approval/AuditLog
│       ├── agent.py        # tool-calling 스트리밍 루프
│       ├── llm.py          # OpenAI 클라이언트 (llama-server)
│       ├── tools/          # fs, shell_exec, obsidian
│       └── routes/         # /chat, /sessions, /approvals, /health
├── frontend/               # Next.js (TypeScript)
│   └── src/
│       ├── app/            # App Router (layout, page, providers)
│       ├── components/     # ChatView, ApprovalModal, ...
│       └── lib/            # api.ts (REST), stream.ts (SSE)
├── plan/                   # 설계 결정 / 일자별 진행 로그
├── workspace/              # 에이전트 R/W 샌드박스
├── docker-compose.yml      # Postgres
├── .env.example
├── start-all.ps1           # PowerShell 일괄 기동 스크립트
└── README.md
```

---

## DB 마이그레이션

스키마 변경은 **Alembic** 으로 관리한다. 백엔드 lifespan 이 기동 때마다 `alembic upgrade head` 를 자동으로 실행하므로 신규 환경에서는 별도 명령이 필요 없다.

기존에 `Base.metadata.create_all()` 로 만들어진 DB 가 이미 있다면 **한 번만** 수동으로 baseline 을 표시한다:

```powershell
cd backend
..\.venv\Scripts\alembic.exe stamp head
cd ..
```

새 마이그레이션이 필요할 때:

```powershell
cd backend
..\.venv\Scripts\alembic.exe revision --autogenerate -m "변경 설명"
# alembic/versions/ 에 생성된 파일 리뷰
..\.venv\Scripts\alembic.exe upgrade head    # 또는 백엔드 재기동
```

## 약속

- 커밋 메시지·PR 본문은 **한글** (`feat:`, `fix:` 같은 접두사는 영문)
- 테스트·Lint 자동화는 미설정 (수동 cURL + 검증 엔드포인트).
