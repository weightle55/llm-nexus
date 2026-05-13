# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 개요

로컬 LLM(llama-server + Gemma 4)을 웹에서 명령해 컴퓨터 작업을 수행하는 agent 시스템.

> **현재 진척도**: Phase 2 완료 (FastAPI 골격 + 헬스체크). 다음은 Phase 3 (DB 연결 — SQLAlchemy async + ORM). 단계별 로드맵과 일간 로그는 `plan/plan.md`, `plan/*-progress.md` 참고.

## 스택

- **LLM**: llama-server (네이티브 실행, :8080, OpenAI 호환 API)
- **Backend**: FastAPI + 단일 agent + tool-calling 루프 (`backend/`)
- **Frontend**: Next.js (App Router) + Tailwind + TanStack Query (`frontend/`)
- **DB**: PostgreSQL 17 (Docker, :5432) — 세션·메시지·audit 저장

## 실행 명령

```powershell
# 1. LLM 서버 (네이티브)
.\llama-server.exe -m "F:\development\ai-models\gemma-4-e4b-it-UD-Q4_K_XL\gemma-4-e4b-it-UD-Q4_K_XL.gguf" -ngl 99 -c 8192 --flash-attn on --port 8080

# 2. PostgreSQL (Docker)
docker compose up -d postgres

# 3. Backend (FastAPI)
.venv\Scripts\pip install -r backend\requirements.txt
.venv\Scripts\uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload

# 4. Frontend (Next.js) — 아직 스캐폴드 안 됨 (Phase 7)
cd frontend
npm install
npm run dev
```

## 검증 엔드포인트

백엔드 변경 후 빠른 확인:

- `GET http://localhost:8000/health` — 정적 정보 (모델명, llama base URL)
- `GET http://localhost:8000/health/llm` — llama-server `/v1/models` 실제 호출. llama-server 미기동 시 `{"status":"error", ...}` 200 반환이 정상 (예외 대신 메시지)

테스트 스위트는 아직 없음 (Phase 8 마무리 단계 예정). 신규 백엔드 코드 검증은 위 엔드포인트와 수동 cURL/REPL로 진행.

## 설정 규약

`backend/app/config.py`는 `pydantic-settings` 기반이고 `.env`를 **프로젝트 루트**에서 읽음. `WORKSPACE_DIR` 같은 경로 설정은 `PROJECT_ROOT` 기준으로 자동 절대화됨 (`_resolve_workspace` validator 참고). 새 경로 설정 추가 시 동일 패턴을 따를 것.

## 안전 정책 (Tool Permission)

- `workspace/` 내 파일 R/W: 자동
- `workspace/` 외 파일 접근: 차단
- 시스템 명령 실행: **승인 모달 필수**
- 옵시디언 읽기/검색: 자동, 쓰기/수정: **승인 모달 필수**
- 모든 도구 호출은 `audit_log` 테이블에 기록

## 폴더 구조

```
gemma-ai-structure/
├── backend/          # FastAPI 서버
├── frontend/         # Next.js UI
├── workspace/        # agent 작업 샌드박스
├── docker-compose.yml
├── .env
└── plan/plan.md      # 설계 결정 기록
```

자세한 설계 결정 및 로드맵은 `plan/plan.md` 참고.
