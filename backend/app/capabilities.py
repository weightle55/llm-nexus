"""사용자에게 보여줄 에이전트 기능 카탈로그 (정적 큐레이션).

도구를 추가하면 여기 한 곳만 갱신하면 된다. 프런트엔드는 새 대화를 열 때
이 카탈로그를 받아 '환영 메시지'로 렌더한다. (DB·LLM 컨텍스트에는 들어가지 않음)
"""

INTRO = (
    "안녕하세요! 저는 이 컴퓨터에서 작업을 대신 수행하는 로컬 에이전트예요. "
    "아래 일들을 시킬 수 있어요 — 무엇을 도와드릴까요?"
)

GROUPS = [
    {
        "title": "📁 파일 작업",
        "items": [
            {"label": "읽기 · 쓰기 · 목록", "desc": "워크스페이스 안의 파일을 읽고, 쓰고, 나열합니다.", "approval": False},
            {"label": "구조 보기 (트리)", "desc": "디렉터리 구조를 한눈에 파악합니다.", "approval": False},
            {"label": "내용 검색", "desc": "여러 파일의 내용에서 문자열을 찾습니다 (grep).", "approval": False},
            {"label": "생성 · 이동 · 이름변경", "desc": "폴더를 만들고, 파일을 옮기거나 이름을 바꿉니다.", "approval": False},
            {"label": "삭제", "desc": "파일을 지웁니다. 폴더(재귀) 삭제는 승인이 필요합니다.", "approval": True},
        ],
    },
    {
        "title": "🌐 웹",
        "items": [
            {"label": "웹페이지 가져오기", "desc": "공개 웹페이지 내용을 텍스트로 읽어옵니다 (문서 조사 등).", "approval": False},
        ],
    },
    {
        "title": "🧊 Blender",
        "items": [
            {"label": "Blender 문서 검색", "desc": "Blender 5.1 API·매뉴얼(오퍼레이터·노드·bpy)을 권위 있게 검색합니다.", "approval": False},
        ],
    },
    {
        "title": "💻 시스템",
        "items": [
            {"label": "셸 명령 실행", "desc": "시스템 명령을 실행합니다. 항상 승인이 필요합니다.", "approval": True},
        ],
    },
]

NOTE = (
    "모든 파일 작업은 워크스페이스 샌드박스 안에서만 이뤄지고, 위험한 작업은 "
    "실행 전에 승인 모달로 확인을 받습니다. 모든 도구 호출은 기록(audit)됩니다."
)


def get_capabilities() -> dict:
    return {"intro": INTRO, "groups": GROUPS, "note": NOTE}
