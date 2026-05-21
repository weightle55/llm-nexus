# 📅 작업 로그 — 2026-05-22 (Phase 7)

> Phase 7 (Next.js 프런트엔드) — 코드/설정 작성 완료, `npm install` 은 사용자 환경에서 실행 필요

---

## 1. 요약

`frontend/` 를 Next.js 15 (App Router) + TypeScript + Tailwind 로 스캐폴딩. 백엔드의 `/sessions`, `/chat/stream`, `/chat/resume/stream`, `/approvals` 를 소비하는 채팅 UI. 토큰 스트리밍 + 승인 모달 + 세션 사이드바를 한 페이지에 묶음. 백엔드에 CORS 미들웨어 추가.

> **주의**: 이 환경에서 npm registry 응답이 단발 30 초+ 라 `create-next-app` / `npm install` 양쪽 모두 stuck. 코드와 설정은 모두 작성·검토 완료 — 사용자 환경에서 `cd frontend && npm install && npm run dev` 로 동작 확인 필요.

---

## 2. 신규 / 변경

### 백엔드
- **`backend/app/main.py`** — `CORSMiddleware` 추가. `localhost:3000` / `127.0.0.1:3000` 만 허용, credentials 포함

### 프런트엔드 (모두 신규)
```
frontend/
├── package.json              # next, react, @tanstack/react-query, @microsoft/fetch-event-source, tailwind
├── tsconfig.json             # strict, @/* → ./src/*
├── next.config.mjs           # strictMode 만
├── tailwind.config.ts        # content: src/**/*.{ts,tsx}
├── postcss.config.js         # tailwind + autoprefixer
├── next-env.d.ts
├── .gitignore                # node_modules, .next, .env.local
├── README.md                 # 설치·실행·구조·흐름 정리
└── src/
    ├── app/
    │   ├── globals.css       # Tailwind base/components/utilities + 다크 배경
    │   ├── layout.tsx        # RootLayout + Providers
    │   ├── page.tsx          # Sidebar + ChatView 합성
    │   └── providers.tsx     # TanStack Query (refetchOnWindowFocus=false, staleTime=5s)
    ├── components/
    │   ├── Sidebar.tsx       # GET /sessions, POST /sessions ("New chat")
    │   ├── ChatView.tsx      # 메시지 fetch + SSE 구독 + approval 처리 (핵심)
    │   ├── MessageList.tsx   # 메시지 버블 + 스트리밍 커서
    │   ├── Composer.tsx      # textarea (Enter 송신, Shift+Enter 줄바꿈)
    │   └── ApprovalModal.tsx # pending approvals 모달 (approve/deny, optional reason)
    └── lib/
        ├── api.ts            # REST 래퍼 (Session, ChatMessage, Approval 타입 포함)
        └── stream.ts         # @microsoft/fetch-event-source 기반 SSE 구독
```

---

## 3. 핵심 동작

### 자동 도구 흐름
1. 사용자 입력 → `POST /chat/stream` 시작 (낙관적 user 메시지 즉시 추가)
2. `token` 이벤트로 점진 렌더 (assistant 버블에 ▍ 커서 표시)
3. `tool_call` / `tool_result` 은 시스템·툴 버블로
4. `done` 시 `messages` 쿼리 invalidate → 서버 상태로 reconcile

### 승인 도구 흐름 (shell_exec)
1. `tool_call` (shell_exec) → `approval_required` 이벤트 → `ApprovalModal` 표시 (Composer 비활성화)
2. Approve / Deny + (옵션) reason → `POST /approvals/{id}/decide`
3. 모든 approval 결정 끝나면 자동으로 `POST /chat/resume/stream` 호출 (사용자 추가 액션 없이)
4. 이어서 `tool_result` (실행 결과 또는 `denied by user`) → `token` → `done`

### 초기 진입 시 미해결 approval 복구
- 세션 선택 시 `GET /approvals?session_id=...&status=pending` 한 번 호출
- pending 이 있으면 모달 즉시 표시 (이전 세션에서 결정 안 끝난 경우)

---

## 4. 설계 결정

- **수동 최소 스캐폴딩** — `create-next-app` 이 30 초+ 의 registry 지연 때문에 stalled. 우리 needs (5 컴포넌트, 2 lib, page+layout+providers) 에 맞춘 직접 작성이 더 빠르고 의존성도 더 명시적. 트레이드오프: ESLint·테스트 도구 등 기본 스캐폴딩이 빠진 상태 (Phase 8 에서 필요시 추가)
- **SSE: `@microsoft/fetch-event-source`** — 표준 `EventSource` 는 GET only, 우리는 POST + body 가 필요. 라이브러리가 abort/재연결/visibility 처리까지 다 해줌
- **TanStack Query 사용 범위** — 세션·메시지·approvals 의 캐시·invalidation 용으로만. 스트리밍 토큰은 직접 `setState` 로 관리 (Query 캐시에 매 토큰 쓰면 React 트리 전체 리렌더 비용 큼). `done` 시점에 한 번 invalidate 해서 서버 상태로 reconcile
- **낙관적 user 메시지** — `POST /chat/stream` 시작 시점에 `messages` 쿼리에 임시 user row 추가. SSE 완료 후 invalidate 로 실제 서버 row 로 교체. 즉각적인 UI 피드백
- **다크 테마 단일** — 추가 토글 안 함. 라이트 모드는 Phase 8 이후로
- **CORS allow_origins 화이트리스트** — `*` 대신 명시. `credentials: true` 라 wildcard 사용 불가능하기도 함

---

## 5. 도중 만난 함정

- **`npx create-next-app` 7 분 stuck** — 최근 시작된 node 프로세스가 CPU 1 초만 쓰고 idle. registry 단발 응답 시간 측정해보니 30 초+. 환경적 latency 문제로 결론, 수동 스캐폴딩으로 전환
- **PowerShell Tee-Object 의 출력 버퍼링** — npm 같은 외부 프로세스 stdout 이 종료 후에야 flush. 진행 상태 추적이 어려움. 별 도리 없어 그냥 인내, 결국 환경 문제라 더 빠르게 포기 결정

---

## 6. 검증 필요 사항 (사용자 환경)

이 환경에서 `npm install` 을 못 끝낸 상태라 다음은 사용자가 확인 필요:

```powershell
cd frontend
npm install
npm run dev
# → http://localhost:3000 접속
```

확인 포인트:
1. **빌드 통과** — TypeScript strict 모드, `next dev` 가 컴파일 에러 없이 뜸
2. **세션 생성** — "New chat" 클릭 → 사이드바에 row 추가
3. **자동 도구** — "Create workspace/test.txt with 'hello'" → 스트리밍 토큰 보이고 파일 생성됨
4. **승인 도구** — "Run shell command 'echo hello'" → 모달 뜸 → Approve → 결과 표시
5. **Deny 흐름** — 같은 메시지 → Deny + reason → 어시스턴트가 거부 사유 자연어로 응답

문제 발생 시 우선순위:
- CORS 에러 → 백엔드 재기동 필요 (main.py 변경됨)
- `fetch-event-source` import 에러 → npm install 재시도
- TS strict 에러 → 그 자리에서 fix

---

## 7. 다음 단계 — Phase 8 (마무리)

| 작업 | 내용 |
|------|------|
| `.env.example` | 모든 환경변수 샘플값 |
| 루트 README | 전체 시스템 개요, 4 스택 (llama-server + Docker + backend + frontend) 기동 순서 |
| 실행 스크립트 | PowerShell 1-shot — `start-all.ps1` 같은 것 (선택) |
| Alembic 마이그레이션 | `create_all()` → Alembic 으로 전환 검토 (또는 v1.x 까지 보류) |

---

## 8. 메모 / 결정 보류

- **테스트 / Lint** — pytest, ESLint 설정 안 함. Phase 8 또는 v1.x 시점
- **에러 경계** — React ErrorBoundary 미사용. SSE 에러는 ChatView 의 setState 로 노출. 더 견고한 UX 는 후순위
- **모바일 레이아웃** — 데스크탑만 고려. 사이드바 collapse / 모바일 햄버거 메뉴는 v1.x
- **메시지 사이드바 ↔ 라이브 스트림 reconciliation** — `done` 후 invalidate 가 깜빡임 유발 가능 (낙관적 user 메시지가 잠시 사라지고 새로 옴). 실측 후 조정
