# CLAUDE.md

이 파일은 Claude Code (claude.ai/code)가 이 저장소에서 작업할 때 참고할 가이드입니다.

## 개요

로컬 LLM(llama-server + Gemma 4)을 웹에서 명령해 컴퓨터 작업을 수행하는 agent 시스템.

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

# 4. Frontend (Next.js)
cd frontend
npm install
npm run dev
```

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
