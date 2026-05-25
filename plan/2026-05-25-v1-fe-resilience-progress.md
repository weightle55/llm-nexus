# 📅 작업 로그 — 2026-05-25 (v1.x #3: FE 견고성 + UX)

> 라이트 테마 토글 · 모바일 사이드바 collapse · Next App Router `error.tsx` 전역 에러 경계 · ChatView 재시도.

---

## 1. 요약

기존에 다크 단일 테마 + 데스크탑만 가정하던 UI 를 라이트/모바일/에러 시나리오까지 다루도록 확장. SSE 자동 재연결은 idempotency 위험 (사용자 메시지 중복 저장 가능) 때문에 의도적으로 도입하지 않고, 대신 **에러 발생 시 명시적 Retry 버튼** 노출 패턴으로 결정.

---

## 2. 신규 / 변경

| 경로 | 종류 | 내용 |
|------|------|------|
| `frontend/tailwind.config.ts` | 변경 | `darkMode: "class"` |
| `frontend/src/app/globals.css` | 변경 | `html` / `html.dark` 색상 분리. body 색상 클래스는 html 으로 이동 |
| `frontend/src/lib/theme.ts` | 신규 | `getStoredTheme` / `applyTheme` / `themeBootstrapScript` (SSR hydration 깜빡임 방지) |
| `frontend/src/components/ThemeToggle.tsx` | 신규 | localStorage 기반 dark/light 토글 |
| `frontend/src/app/layout.tsx` | 변경 | `<head>` 에 bootstrap script 주입, `suppressHydrationWarning` |
| `frontend/src/app/error.tsx` | 신규 | Next App Router 전역 ErrorBoundary (`reset()` 호출 가능) |
| `frontend/src/app/page.tsx` | 변경 | `sidebarOpen` 상태 + 모바일 햄버거 헤더 |
| `frontend/src/components/Sidebar.tsx` | 변경 | `isOpen`/`onClose` props, `fixed md:static` 슬라이드 드로어, 모달 backdrop, ThemeToggle 푸터 |
| `frontend/src/components/ChatView.tsx` | 변경 | `lastRunRef` (chat \| resume) + 에러 패널에 Retry / Dismiss 버튼 |
| `frontend/src/components/MessageList.tsx` | 변경 | 모든 bubble 색상 `dark:` variant |
| `frontend/src/components/Composer.tsx` | 변경 | textarea/border 라이트 variant |
| `frontend/src/components/ApprovalModal.tsx` | 변경 | 모달·코드 블록 라이트 variant |

---

## 3. 결정 사항

- **SSE 자동 재연결 없음** — `fetchEventSource` 의 `onerror` retry 는 같은 POST 를 재전송한다. `/chat/stream` 은 사용자 메시지를 매 호출에서 DB 에 새로 저장하므로 자동 재시도 시 중복 row 발생. 대신 ChatView 에 `lastRunRef` 두고 명시적 Retry 버튼 노출. Resume 케이스도 동일.
- **`error.tsx` (App Router) 채택** — class component 직접 작성 대신 Next 내장 ErrorBoundary 사용. 자동 등록 + `reset()` 콜백 제공.
- **테마 bootstrap inline script** — `<head>` 안에서 `localStorage` 읽고 `dark` 클래스 즉시 부착. React hydration 이전이라 SSR 깜빡임 없음. `suppressHydrationWarning` 으로 html 속성 차이 경고 회피.
- **모바일 사이드바: fixed + transform** — `display: none` 전환 대신 transform 슬라이드로 트랜지션 자연스럽게. 데스크탑(`md:`)에서는 `static` 으로 강제.
- **테마 default = dark** — 기존 동작 유지. localStorage 없을 때 dark.

---

## 4. 검증

- ✅ `next dev` 컴파일 통과 (modules 그대로, 컴파일 에러 없음, GET / 200)
- 🔲 브라우저 수동 확인 필요:
  - 사이드바 하단 ☀/🌙 버튼 → 즉시 토글 + 새로고침 시 유지
  - 모바일 viewport (Chrome DevTools, < 768px) → 햄버거 버튼, 사이드바 슬라이드 in/out, 오버레이 클릭 닫힘
  - 백엔드 종료 후 메시지 전송 → 에러 배너 + Retry 버튼 → 백엔드 복구 후 클릭 → 정상 동작
  - 의도적 throw 후 `error.tsx` 표시 (테스트 코드 작성 시점에 검증)

---

## 5. 미구현 (의도)

- **SSE 자동 재연결** — backend idempotency 보강 후 재검토 (예: `Idempotency-Key` 헤더 + redis dedupe)
- **시스템 테마 자동 감지** — `prefers-color-scheme` 감지는 v1.x #2 (테스트) 이후
- **에러 텔레메트리** — Sentry 등은 다중 사용자 / 인증 시점에
