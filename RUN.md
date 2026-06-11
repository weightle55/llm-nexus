# RUN.md — llm-nexus 실행 cheatsheet

저장소 클론 직후부터 채팅이 뜨기까지의 전 과정. README.md 가 narrative 라면 이 문서는 **command-first**.

---

## 0. 사전 준비 (한 번만)

| 도구 | 비고 |
|------|------|
| Python 3.11+ | `python --version` 으로 확인 |
| Node.js 20+ | v24 동작 확인 |
| Docker Desktop | Postgres 컨테이너용 |
| `llama-server.exe` (llama.cpp) | PATH 또는 프로젝트 루트에 둠 |
| GGUF 모델 | 예: `gemma-4-e4b-it-UD-Q4_K_XL.gguf` |

### 첫 셋업

```powershell
# 1) 저장소 진입
cd F:\development\llm-nexus

# 2) Python venv + backend 의존성
python -m venv .venv
.\.venv\Scripts\pip install -r backend\requirements.txt

# 3) Frontend 의존성
cd frontend
npm install
cd ..
# npm install 이 stuck 처럼 보이면 SSL 이슈 — NODE_EXTRA_CA_CERTS 설정 (memory: npm-ssl-windows)

# 4) 환경변수 파일
copy .env.example .env
# .env 열어서 LLAMA_MODEL 값, JWT_SECRET (랜덤 문자열로!) 채움
# JWT_SECRET 생성: python -c "import secrets; print(secrets.token_urlsafe(64))"
```

---

## 1. 매번 기동 — 자동 (권장)

```powershell
# llama-server 는 GPU 점유라 별도 터미널에서 직접 (1번 항목)
.\llama-server.exe `
  -m "F:\development\ai-models\gemma-4-e4b-it-UD-Q4_K_XL\gemma-4-e4b-it-UD-Q4_K_XL.gguf" `
  -ngl 99 -c 8192 --flash-attn on --port 11434

# 나머지 (Postgres + 백엔드 + 프런트엔드) 한 방에
.\start-all.ps1
```

`start-all.ps1` 은 내부에서 다음을 순서대로 실행:
1. `docker compose up -d postgres`
2. `cd backend; alembic upgrade head` — 마이그레이션 적용
3. 새 PowerShell 창에 `uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload`
4. 새 PowerShell 창에 `cd frontend; npm run dev`

플래그:
- `-NoBackend` — 백엔드 스킵
- `-NoFrontend` — 프런트엔드 스킵

---

## 2. 매번 기동 — 수동 (4 터미널)

```powershell
# 터미널 1 — llama-server
.\llama-server.exe -m <model.gguf> -ngl 99 -c 8192 --flash-attn on --port 11434

# 터미널 2 — Postgres
docker compose up -d postgres

# 터미널 3 — Backend
cd backend
..\.venv\Scripts\alembic.exe upgrade head    # 매 부팅마다 OK (멱등)
cd ..
.\.venv\Scripts\uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload

# 터미널 4 — Frontend
cd frontend
npm run dev
```

---

## 3. 헬스체크

```powershell
curl http://localhost:8000/health        # 정적 정보 (모델명, llama URL)
curl http://localhost:8000/health/llm    # llama-server /v1/models 핑
curl http://localhost:8000/health/db     # Postgres SELECT 1
```

세 개 모두 `{"status":"ok",...}` → 사용 준비 완료.

프런트엔드: <http://localhost:3000>

---

## 4. 사용

1. 첫 진입 시 자동으로 **`/login`** 으로 리다이렉트
2. **회원가입** (`/register`) — 첫 가입자는 owner 없는 기존 세션 모두 자동 귀속
3. 사이드바 **"+ New chat"** 으로 세션 생성
4. 메시지 입력 → SSE 토큰 스트리밍
5. `shell_exec` 같은 위험 도구 호출 시 **승인 모달** → Approve / Deny

사이드바 푸터:
- 사용자 이메일
- **로그아웃**
- **☀ Light / 🌙 Dark** 테마 토글

---

## 5. 종료

```powershell
# llama-server / uvicorn / next dev — 각 터미널에서 Ctrl+C
# Postgres — 컨테이너 유지 (다음 부팅 빠름)
docker compose stop postgres        # 또는 그대로 둬도 됨
```

데이터까지 날리고 싶을 때 (주의):
```powershell
docker compose down -v
Remove-Item postgres\data -Recurse -Force
```

---

## 6. 마이그레이션 작업

새 모델/컬럼 추가 시:

```powershell
cd backend
..\.venv\Scripts\alembic.exe revision --autogenerate -m "변경 설명"
# alembic/versions/ 에 생성된 파일을 반드시 리뷰 (autogenerate 가 누락하는 경우 있음)
..\.venv\Scripts\alembic.exe upgrade head
```

**기존 DB (Alembic 도입 전부터 있던 환경)** 는 첫 마이그레이션 전에 한 번:

```powershell
cd backend
..\.venv\Scripts\alembic.exe stamp head
```

---

## 7. 트러블슈팅

### `/health/db` 가 error
- `docker ps` 로 `gemma-postgres` 컨테이너 healthy 확인
- 컨테이너 stop 된 상태면 `docker compose up -d postgres`

### `/health/llm` 가 error
- llama-server 가 떠 있는지 (브라우저 `http://localhost:11434/v1/models` 200)
- `.env` 의 `LLAMA_BASE_URL`, `LLAMA_MODEL` 값이 실제와 일치하는지

### 채팅 시 401 / 로그아웃되는 현상
- JWT 만료 (기본 7일). 다시 로그인
- `.env` 의 `JWT_SECRET` 이 바뀌면 기존 토큰 무효화 — 다시 로그인

### `npm install` 이 stuck
- 십중팔구 SSL `UNABLE_TO_VERIFY_LEAF_SIGNATURE`
- `NODE_EXTRA_CA_CERTS` 에 시스템 root cert PEM 경로 지정 (memory: `npm-ssl-windows`)

### uvicorn `--reload` 가 잡혀서 hang
- 대부분 코드 변경 race. `Get-NetTCPConnection -LocalPort 8000 -State Listen` 으로 PID 확인 → `Stop-Process -Id <PID> -Force` 후 재기동
- `lifespan` 안에서 `alembic upgrade` 자동 호출 패턴은 hang 재현돼 제거됨 (`start-all.ps1` 가 명시적 호출)

### 알람빅 마이그레이션 직접 호출 vs 백엔드 자동
- 자동 안 함. 백엔드 기동 전에 `alembic upgrade head` 직접 호출 필요. `start-all.ps1` 가 자동으로 해줌

---

## 8. 폴더 — 어디에 뭐가 있나

```
llm-nexus/
├── backend/
│   ├── alembic/versions/          # DB 마이그레이션 (0001 baseline, 0002 users)
│   ├── alembic.ini
│   └── app/
│       ├── main.py                # FastAPI 엔트리, CORS, 라우터 마운트
│       ├── config.py              # .env 로드
│       ├── db.py                  # SQLAlchemy async engine
│       ├── models.py              # User / Session / Message / Approval / AuditLog
│       ├── auth.py                # bcrypt 해시 + JWT + get_current_user
│       ├── agent.py               # tool-calling 스트리밍 루프
│       ├── llm.py                 # OpenAI 호환 client (llama-server)
│       ├── tools/                 # fs, shell_exec, obsidian
│       └── routes/                # auth / sessions / chat / approvals / health
├── frontend/
│   └── src/
│       ├── app/
│       │   ├── layout.tsx, providers.tsx, page.tsx, error.tsx
│       │   ├── login/page.tsx, register/page.tsx
│       │   └── globals.css
│       ├── components/            # Sidebar / ChatView / MessageList / Composer / ApprovalModal / ThemeToggle
│       └── lib/                   # api.ts, stream.ts, auth.ts, theme.ts
├── plan/                          # 단계별 progress 로그
├── workspace/                     # 에이전트 R/W 샌드박스
├── docker-compose.yml             # postgres (qdrant 는 주석)
├── .env / .env.example
├── start-all.ps1                  # 일괄 기동
├── README.md                      # 시스템 개요 (narrative)
└── RUN.md                         # 본 문서 (command cheatsheet)
```
