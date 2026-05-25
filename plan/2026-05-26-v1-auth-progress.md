# 📅 작업 로그 — 2026-05-26 (v1.x #4: 인증 / 다중 사용자)

> Email + 비밀번호 + JWT. 첫 user 에게 기존 owner-less 세션 자동 귀속. lifespan 자동 alembic 은 hang 재현으로 제거.

---

## 1. 요약

`users` 테이블 + `sessions.owner_id` 추가. `/auth/register` / `/auth/login` / `/auth/me`. `get_current_user` 의존성으로 모든 sessions·chat·approvals 라우트에 인증 강제. 프런트엔드는 `/login` / `/register` 페이지 추가, `lib/auth.ts` 가 localStorage 토큰 관리, 모든 fetch + SSE 호출에 `Authorization` 헤더, TanStack Query 글로벌 401 핸들러로 토큰 만료 시 자동 로그아웃.

---

## 2. 신규 / 변경

### Backend
| 경로 | 종류 | 내용 |
|------|------|------|
| `backend/requirements.txt` | 변경 | bcrypt, PyJWT, email-validator 추가 (passlib 제거 — bcrypt 5 호환 이슈로 bcrypt 직접 사용) |
| `backend/app/config.py` | 변경 | `jwt_secret` / `jwt_algorithm` / `jwt_expire_minutes` |
| `backend/app/models.py` | 변경 | `User` 모델 + `Session.owner_id` (nullable FK → users) |
| `backend/app/auth.py` | 신규 | bcrypt 해시 + JWT 발급/검증 + `get_current_user` 의존성 |
| `backend/app/routes/auth.py` | 신규 | `/auth/register`, `/auth/login`, `/auth/me`. register 가 첫 user 일 경우 owner-less 세션 모두 귀속 |
| `backend/app/routes/sessions.py` | 변경 | 모든 핸들러에 `user = Depends(get_current_user)` + owner 필터 |
| `backend/app/routes/chat.py` | 변경 | 네 endpoint 전부 `_assert_owner` 호출 |
| `backend/app/routes/approvals.py` | 변경 | join Session + owner_id 필터, decide 도 owner 확인 |
| `backend/app/main.py` | 변경 | auth_router 마운트 |
| `backend/app/db.py` | **변경** | lifespan 의 alembic 자동 upgrade 제거 (환경적 hang 재현). `_run_alembic_upgrade` 헬퍼만 보존 |
| `backend/alembic/versions/0002_users_and_owner.py` | 신규 | users 테이블 + sessions.owner_id + 인덱스 |
| `.env.example` | 변경 | `JWT_SECRET`, `JWT_EXPIRE_MINUTES` 항목 추가 |
| `start-all.ps1` | 변경 | 백엔드 기동 직전 `alembic upgrade head` 호출 |
| `README.md` | 변경 | "DB 마이그레이션" 섹션 명시적 alembic 명령으로 수정 |

### Frontend
| 경로 | 종류 | 내용 |
|------|------|------|
| `frontend/src/lib/auth.ts` | 신규 | `getToken`/`setToken`/`clearToken`/`authHeader` (localStorage) |
| `frontend/src/lib/api.ts` | 변경 | `UnauthorizedError`, `register`/`login`/`me` 추가, 모든 호출에 `authHeader()` |
| `frontend/src/lib/stream.ts` | 변경 | fetchEventSource 헤더에 `authHeader()` 추가 |
| `frontend/src/app/login/page.tsx` | 신규 | 로그인 폼 |
| `frontend/src/app/register/page.tsx` | 신규 | 회원가입 폼 (6자 이상 검증) |
| `frontend/src/app/page.tsx` | 변경 | `/auth/me` 검증 → 미인증 시 `/login` redirect, user/로그아웃 prop 전달 |
| `frontend/src/components/Sidebar.tsx` | 변경 | user 이메일 + 로그아웃 버튼 (테마 토글 위에) |
| `frontend/src/app/providers.tsx` | 변경 | QueryCache + MutationCache 의 `onError` 에서 `UnauthorizedError` 잡아 토큰 제거 + `/login` 리다이렉트 |

---

## 3. 결정 사항

- **lifespan 자동 alembic upgrade 제거** — v1.x #1 에서 `asyncio.to_thread(_run_alembic_upgrade)` 로 도입했지만, 0002 migration 추가 후 uvicorn reload 와 동시 호출 시 startup 이 hang 하는 현상 두 번 재현. 단독 호출(`python -c "..."`)은 정상 동작. asyncio.to_thread + alembic env.py 의 `asyncio.run()` + SQLAlchemy async engine 의 race 가능성. **`start-all.ps1`** 가 백엔드 기동 직전 명시적으로 `alembic upgrade head` 를 호출하도록 이동. lifespan 은 ORM 매퍼 등록만.
- **passlib 제거, bcrypt 직접 호출** — passlib 1.7.4 가 bcrypt 5.x 와 `__about__` API 호환 안 됨 (잘 알려진 이슈). bcrypt 만 직접 import 해서 hashpw / checkpw.
- **첫 user 자동 귀속** — `register` 핸들러가 user 생성 직후 `SELECT count(*) FROM users` 가 1 이면 owner_id NULL 인 모든 sessions 를 본인에게 update. 두 번째 user 가 등록되어도 이미 누군가에게 귀속됐기 때문에 leak 없음.
- **JWT 만료 = 7 일 (default)** — 단일 사용자 로컬 가정. 환경변수로 조정.
- **글로벌 401 → 로그아웃** — QueryCache/MutationCache 의 `onError` 에서 처리. router 가 아닌 `window.location.href` 사용 — providers 가 router context 밖에서 호출될 수도 있어서.

---

## 4. 검증

Backend (cURL):
- ✅ `POST /auth/register {email, password}` → 200 + access_token
- ✅ `POST /auth/login` (동일 자격) → 200 + access_token
- ✅ `GET /auth/me` with `Authorization: Bearer <token>` → user info
- ✅ `GET /sessions` (토큰 없음) → 401
- ✅ `GET /sessions` (토큰) → **12 개 기존 세션 모두 반환** (첫 register 의 자동 귀속 로직 동작 확인)

Frontend (스모크):
- ✅ `next dev` Compiled, GET / / /login / /register 모두 200

브라우저 직접 확인 필요:
- 🔲 토큰 없이 / 접속 → /login 으로 redirect
- 🔲 회원가입 → / 로 이동 + Sidebar 에 email + 세션 목록
- 🔲 로그아웃 → /login
- 🔲 토큰 만료 시뮬레이션 (localStorage 의 token 손상) → 자동 로그아웃

---

## 5. 함정 / 메모

- bcrypt 5 + passlib 1.7.4 호환 불가 — 향후 다른 프로젝트도 영향 가능. requirements 고정 시 주의.
- lifespan 안에서 무거운 sync 호출(asyncio.to_thread 안에서 또 asyncio.run 호출하는 패턴) 은 지양. uvicorn reload 와 race 위험.
- Token 은 localStorage. XSS 시 탈취 가능 (단일 사용자 로컬 가정이라 수용). 다중 사용자 운영 환경에선 httpOnly cookie 권장.

---

## 6. 다음

- v1.x #2 — pytest + Vitest (사용자 요청 시점에)
- v1.x #5 — RAG (Qdrant)
