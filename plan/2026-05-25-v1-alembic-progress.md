# 📅 작업 로그 — 2026-05-25 (v1.x #1: Alembic)

> `Base.metadata.create_all()` → Alembic 마이그레이션. baseline + lifespan 자동 upgrade.

---

## 1. 요약

스키마 변경 이력을 코드로 남기기 위해 Alembic 도입. 백엔드 lifespan 이 기동 시마다 `alembic upgrade head` 를 자동 실행 — 신규 환경은 별도 명령 없이 작동, 이미 `create_all()` 로 만들어진 DB 는 `alembic stamp head` 한 번으로 baseline 표시 후 동일하게 진행.

---

## 2. 신규 / 변경

| 경로 | 종류 | 내용 |
|------|------|------|
| `backend/requirements.txt` | 변경 | `alembic>=1.13` 추가 |
| `backend/alembic.ini` | 신규 | `alembic init -t async` 산출물 (수정 없음) |
| `backend/alembic/env.py` | 신규/수정 | `settings.database_url` 사용, `Base.metadata` 를 target_metadata 로 |
| `backend/alembic/versions/0001_initial_schema.py` | 신규 | sessions / messages / audit_log / approvals + 인덱스 (수동 작성) |
| `backend/app/db.py` | 변경 | `init_db()` 가 `Base.metadata.create_all` 대신 `command.upgrade(cfg, "head")` 를 `asyncio.to_thread` 로 실행 |
| `README.md` | 변경 | "DB 마이그레이션" 섹션 추가, 폴더 구조에 `alembic/` 반영 |

---

## 3. 결정 사항

- **autogenerate 대신 baseline 수동 작성** — 기존 DB 에 모든 테이블이 이미 있어서 autogenerate 가 빈 결과를 냄. 신규 환경에서도 동작하는 baseline 이 필요해 수동으로 `op.create_table` 호출 작성.
- **lifespan 에서 자동 upgrade** — 로컬 단일 사용자 환경 가정. CI/CD/prod 가 생기면 환경변수로 toggle 화 (`AUTO_MIGRATE_ON_STARTUP=false` 등).
- **`asyncio.to_thread` 로 sync alembic 호출** — `command.upgrade` 내부에서 `asyncio.run` 을 호출 (env.py 의 `run_migrations_online`). 이미 동작 중인 event loop 안에서는 안 되므로 별도 스레드.
- **기존 DB 처리는 README 안내로** — `alembic stamp head` 1 회. lifespan 에서 자동 감지(테이블이 있는데 `alembic_version` 이 없으면 stamp) 같은 마법 회피.

---

## 4. 검증

```powershell
# 1) 기존 DB stamp + 현재 revision
cd backend; ..\.venv\Scripts\alembic.exe stamp head
..\.venv\Scripts\alembic.exe current
# → "0001 (head)"
# Postgres 확인: SELECT version_num FROM alembic_version; → "0001"

# 2) 신규 DB 에서 baseline 적용
docker exec gemma-postgres psql -U gemma -d gemma -c "CREATE DATABASE gemma_alembic_test;"
$env:DATABASE_URL = "postgresql+asyncpg://gemma:gemma@localhost:5432/gemma_alembic_test"
..\.venv\Scripts\alembic.exe upgrade head
# → "Running upgrade -> 0001"
# 테이블 5개 (alembic_version + 4 모델) 정상 생성
docker exec gemma-postgres psql -U gemma -d gemma -c "DROP DATABASE gemma_alembic_test;"

# 3) 백엔드 재기동 — lifespan 의 alembic upgrade 가 no-op
curl http://localhost:8000/health/db
# → {"status":"ok","result":1}
```

세 단계 모두 통과.

---

## 5. 다음 (v1.x #2~5)

- pytest + Vitest 베이스라인
- FE 견고성 + UX (ErrorBoundary / SSE 재연결 / 모바일 / 라이트 테마)
- 인증 / 다중 사용자
- RAG (Qdrant)
