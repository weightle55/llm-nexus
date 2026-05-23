# frontend

llm-nexus 의 Next.js (App Router) UI. 백엔드 (`backend/`) 의 `/sessions`, `/chat/stream`, `/approvals` 를 소비한다.

## 사전 조건

- Node.js 20+ (개발은 v24 에서 검증)
- 백엔드가 `:8000` 에서 기동 중 (CORS 는 `localhost:3000` 만 허용)
- llama-server (`:11434`) + Postgres (`:5432`) 도 함께 떠있어야 채팅이 동작

## 설치 & 실행

```powershell
cd frontend
npm install
npm run dev          # http://localhost:3000
```

`NEXT_PUBLIC_API_BASE` 환경변수로 백엔드 주소를 덮어쓸 수 있다 (기본 `http://127.0.0.1:8000`).

## 구조

```
src/
├── app/
│   ├── globals.css         # Tailwind v3
│   ├── layout.tsx          # RootLayout + Providers
│   ├── page.tsx            # Sidebar + ChatView 합성
│   └── providers.tsx       # TanStack Query
├── components/
│   ├── Sidebar.tsx         # 세션 목록 + "New chat"
│   ├── ChatView.tsx        # 메시지 fetch + SSE 구독 + approval 처리
│   ├── MessageList.tsx     # 메시지 버블 + 스트리밍 커서
│   ├── Composer.tsx        # 입력창 (Enter 송신, Shift+Enter 줄바꿈)
│   └── ApprovalModal.tsx   # pending approval 모달 (approve/deny)
└── lib/
    ├── api.ts              # REST 래퍼 (sessions, messages, approvals)
    └── stream.ts           # @microsoft/fetch-event-source 기반 SSE 구독
```

## 흐름

1. **자동 도구**: 사용자가 메시지 입력 → `POST /chat/stream` 구독 → `token` 이벤트로 점진 렌더 → `tool_call`/`tool_result` 는 시스템·툴 버블로 → `done` 시 메시지 새로고침
2. **승인 도구 (shell_exec)**: 같은 흐름이지만 `approval_required` 이벤트가 오면 모달이 떠서 입력을 막음 → Approve/Deny 결정 → `POST /approvals/{id}/decide` → 마지막 결정 후 자동으로 `POST /chat/resume/stream` 으로 재개

## 메모

- SSE 라이브러리는 `@microsoft/fetch-event-source`. 표준 `EventSource` 는 GET only 라 POST + body 가 필요한 우리 흐름에 안 맞음.
- TanStack Query 는 세션·메시지·approvals 의 캐시·invalidation 용. 스트리밍 토큰은 직접 setState 로 관리 (Query 캐시에 매 토큰 쓰면 과한 리렌더).
- 인증 / 다중 사용자는 v1 범위 밖.
