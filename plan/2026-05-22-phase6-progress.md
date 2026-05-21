# 📅 작업 로그 — 2026-05-22 (Phase 6)

> Phase 6 (SSE 스트리밍) 완료

---

## 1. 요약

`/chat` / `/chat/resume` 와 동등한 동작을 SSE 로 노출 (`/chat/stream`, `/chat/resume/stream`). LLM 토큰을 받는 즉시 클라이언트로 흘려보내고, 도구 호출 / 결과 / 승인 요청 / 종료를 별도 이벤트로 emit. 비스트리밍 라우트는 그대로 유지 (디버깅·테스트용).

---

## 2. 이벤트 스키마

SSE `event:` 필드로 종류를 구분, `data:` 는 JSON.

| event | payload | 시점 |
|-------|---------|------|
| `token` | `{"delta": str}` | LLM 토큰 청크 |
| `tool_call` | `{"id", "type":"function", "function":{"name","arguments"}}` | 한 도구 호출이 스트림에서 완성된 시점 |
| `tool_result` | `{"tool_call_id", "name", "content"}` | 자동 도구 실행 직후 (승인 도구는 resume 후 emit) |
| `approval_required` | `{"approvals": [Approval, ...]}` | 승인 큐잉됨, 사용자 결정 대기 |
| `done` | `{"status": "ok"\|"pending_approval"\|"stopped", "reply"?: str}` | 한 턴 종료 |
| `error` | `{"detail": str}` | 예외 처리 (404 등은 stream 진입 전이라 별도) |

---

## 3. 신규 / 변경

### 변경
- **`backend/app/llm.py`** — `chat()` 에 `stream=False` 파라미터 추가. True 면 `client.chat.completions.create(stream=True)` 를 반환 (AsyncStream)
- **`backend/app/agent.py`** — 핵심 루프를 async generator 중심으로 재설계:
  - `_stream_completion(convo, out)` — LLM 스트림을 소비하면서 `('token', ...)` yield, `delta.tool_calls` 청크는 `index` 별로 누적해서 완성된 `tool_calls` 를 `out` 딕셔너리에 저장
  - `_run_auto_tool` / `_queue_approval` — _execute_or_defer 를 두 함수로 분리 (generator 안에서 가독성 좋게)
  - `_loop_stream(db, session_id, convo)` — 메인 루프. tool_call 완성마다 `tool_call` 이벤트, 자동 도구면 실행 후 `tool_result`, 승인 도구면 큐잉만. 사이클 끝에 deferred 있으면 `approval_required` + `done(pending_approval)` 로 종료
  - `run_turn_stream` / `resume_turn_stream` — public async generator. 라우터가 그대로 SSE 직렬화에 사용
  - `run_turn` / `resume_turn` — `_drain()` 으로 generator 를 다 소비하면서 마지막 `done` / `approval_required` 만 합산해 비스트리밍 응답 dict 반환. 코드 중복 없음
- **`backend/app/routes/chat.py`**:
  - `_format_sse(event, payload)` — `event: <name>\ndata: <json>\n\n` 바이트 인코딩
  - `_to_sse(gen)` — agent generator 를 SSE 바이트 스트림으로 감싸고, `ValueError` / 일반 `Exception` 은 `event: error` 로 흘림
  - `POST /chat/stream`, `POST /chat/resume/stream` — `StreamingResponse(_to_sse(gen), media_type="text/event-stream", headers={"Cache-Control":"no-cache","X-Accel-Buffering":"no"})`

신규 파일 없음, 의존성 추가 없음 (`sse-starlette` 미사용 — `StreamingResponse` 로 충분).

---

## 4. 검증 시나리오 (수동, end-to-end)

llama-server (네이티브, `owned_by: llamacpp`) + Postgres + 백엔드 띄운 상태에서:

1. **텍스트만 응답** — `/chat/stream` 에 `"Say hello in one sentence."` → `event: token` 2회 ("Hello", "!") + `event: done {status:"ok", reply:"Hello!"}`
2. **자동 도구** — `"Create workspace/sse-test.txt with the text 'streamed via sse'."` → `tool_call(fs_write)` → `tool_result(ok, bytes:16)` → `token` 17개 (어시스턴트 확인 응답) → `done(ok)`
3. **승인 도구 (pending 단계)** — `"Run the shell command 'echo hello sse'."` → `tool_call(shell_exec)` → `approval_required([...])` → `done(pending_approval)`. HTTP 연결은 정상 종료
4. **승인 후 resume/stream** — approval decide(approve) 후 `/chat/resume/stream` → `tool_result(shell_exec, exit_code:0, stdout:"hello sse\n")` → `token` 14개 → `done(ok)`
5. **비스트리밍 회귀** — `/chat` 호출 시 동일 응답 모델 (`{status, reply, approvals}`) 그대로

---

## 5. 설계 결정

- **단일 generator 가 진실, 비스트리밍은 drain wrapper** — `_loop_stream` 만 유지하고 `run_turn` / `resume_turn` 은 `_drain()` 으로 마지막 이벤트만 추출. tool 실행 흐름 / 승인 분기 / max iteration 한 곳에서만 관리됨 → 두 갈래로 갈라진 코드 유지 비용 없음
- **`POST + SSE`** (GET 아님) — body 가 필요 (session_id, message). 표준 EventSource 는 못 쓰지만, 브라우저에서는 fetch + ReadableStream / `@microsoft/fetch-event-source` 로 받음. Phase 7 에서 처리
- **`tool_call_id` 누적 처리** — llama-server 의 tool_call delta 는 `id` 가 첫 청크에만 오고 `function.arguments` 가 여러 청크로 쪼개져 옴. `index` 키로 슬롯을 만들어 누적. 완성 후 한 번에 `tool_call` 이벤트 emit (부분 인자 노출 안 함 — UI 가 파싱하기 쉽게)
- **에러 처리** — 라우트 진입 전 검증 실패 (세션 없음 등) 는 HTTP 404 — 하지만 stream 라우트는 generator 진입 전이라 4xx 가 안 됨. `_to_sse` 가 `ValueError` 를 잡아서 `event: error` 로 흘림. UX 일관성 위해 stream 도 200 + error event 정책
- **버퍼링 방지 헤더** — `Cache-Control: no-cache`, `X-Accel-Buffering: no` (nginx 등 리버스프록시 대비). uvicorn 단독으로도 chunked encoding 으로 즉시 흐름

---

## 6. 도중 만난 함정 / 소소한 것

- **PowerShell 에서 curl 로 JSON body 보내기** — `-d '{"..."}'` 가 그대로 안 들어감 (PS 의 quoting 으로 깨짐). 임시 파일에 UTF-8 (BOM 없음) 으로 저장 후 `--data-binary "@$file"` 로 해결. 그 외엔 깔끔
- **chunk.choices 가 비어있는 경우** — llama-server 가 마지막에 빈 chunk 를 보낼 수 있음. `if not chunk.choices: continue` 로 가드

---

## 7. 다음 단계 — Phase 7 (Next.js 프런트)

| 작업 | 내용 |
|------|------|
| 스캐폴딩 | `frontend/` 에 Next.js (App Router) + Tailwind + TanStack Query |
| 채팅 UI | 메시지 리스트 + 입력창, 토큰 단위 점진 렌더 (`fetch-event-source` 또는 fetch + ReadableStream) |
| 승인 모달 | `approval_required` 이벤트 받으면 모달 → `POST /approvals/{id}/decide` → `POST /chat/resume/stream` |
| 세션 사이드바 | `GET /sessions` 목록, 클릭 시 `GET /sessions/{id}/messages` |

이후 Phase 8 (`.env.example`, README, 실행 스크립트).

---

## 8. 메모 / 결정 보류

- **toolcalls 의 `index` 가 인접하지 않을 가능성** — sorted(tc_buf) 로 안전. 현재 llama-server 는 0,1,2,... 로 옴
- **stream 도중 클라이언트 끊김** — generator 가 GeneratorExit. AsyncSession 은 자동 close, 커밋 안 된 변경은 롤백. 별도 처리 안 함 (안전한 디폴트 동작)
- **`/chat/stream` 의 OpenAPI 응답 모델** — 현재 StreamingResponse 라 swagger 에 스키마 안 나타남. `responses=` 어노테이션으로 명세 추가 검토 가능
