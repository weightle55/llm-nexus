# 📅 작업 로그 — 2026-05-25 (Phase 8)

> Phase 8 (마무리) — `.env.example`, 루트 README, `start-all.ps1`. Alembic 마이그레이션은 v1.x 로 보류.

---

## 1. 요약

저장소 클론 직후 시작 가능하도록 사용자용 진입점 정리. 4 스택(llama-server + Postgres + backend + frontend) 기동 순서, 환경변수, 안전 정책, 폴더 구조를 한 곳에. 일괄 기동 PowerShell 스크립트 추가.

---

## 2. 신규 / 변경

| 경로 | 종류 | 내용 |
|------|------|------|
| `.env.example` | 신규 | LLAMA_BASE_URL / LLAMA_MODEL / DATABASE_URL / WORKSPACE_DIR / OBSIDIAN_* / NEXT_PUBLIC_API_BASE 샘플값 |
| `README.md` | 신규 (루트) | 사전 준비 → 4 스택 기동 → 헬스체크 → 사용 → 안전 정책 → 폴더 구조 |
| `start-all.ps1` | 신규 | Postgres / 백엔드 / 프런트엔드 일괄 기동. `-NoBackend` / `-NoFrontend` 플래그. llama-server 는 GPU 점유라 별도 |
| `plan/2026-05-25-phase8-progress.md` | 신규 | 본 로그 |

---

## 3. 결정 사항

- **llama-server 는 자동 기동에서 제외** — GPU 점유 + 모델 경로 머신마다 다름. README/스크립트 모두 수동 안내.
- **`copy .env.example .env`** — `.env` 는 `.gitignore` 에 있고 OBSIDIAN_API_KEY 같은 secret 이 들어가는 곳. 예시는 secret 비워서 commit.
- **`start-all.ps1` 가 새 PowerShell 창을 띄움** — `Start-Process powershell -ArgumentList "-NoExit", ...`. 같은 창에서 백그라운드로 돌리면 로그 못 봄. 사용자가 창 닫으면 종료.
- **Alembic 도입 보류** — `Base.metadata.create_all()` 로 충분 (스키마 큰 변경 없음). v1.x 에서 스키마 마이그레이션 필요 시점에 도입.
- **테스트 자동화 보류** — 검증 엔드포인트(`/health/llm`, `/health/db`) + 수동 cURL 로 충분. pytest/Vitest 는 v1.x.

---

## 4. 검증

```powershell
# 1) .env.example → .env 복사 후 실행
copy .env.example .env
.\start-all.ps1

# 2) 4 스택 떠 있는지
curl http://localhost:8000/health        # status:ok
curl http://localhost:8000/health/llm    # status:ok (llama-server 떠 있을 때)
curl http://localhost:8000/health/db     # status:ok
# 프런트: http://localhost:3000
```

이번 세션에서는 이미 띄워둔 백엔드/프런트엔드 그대로 사용 (재기동 없음).

---

## 5. 남은 항목 (v1.x 이후)

- Alembic 마이그레이션
- pytest / Vitest 도입
- React ErrorBoundary, SSE 재연결 UX
- 모바일 레이아웃 (사이드바 collapse)
- 라이트 테마 토글
- 인증 / 다중 사용자
- RAG (Qdrant 컨테이너는 `docker-compose.yml` 에 주석으로 준비됨)
