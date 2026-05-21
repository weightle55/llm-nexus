import subprocess

DEFAULT_TIMEOUT = 30
OUTPUT_LIMIT = 4000


def shell_exec(command: str, cwd: str | None = None, timeout: int | None = None) -> dict:
    """승인 후 호출되는 실제 실행 함수. agent 루프는 직접 부르지 않음."""
    try:
        proc = subprocess.run(
            command,
            shell=True,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout or DEFAULT_TIMEOUT,
            encoding="utf-8",
            errors="replace",
        )
    except subprocess.TimeoutExpired as e:
        return {
            "command": command,
            "error": "timeout",
            "timeout": e.timeout,
        }
    return {
        "command": command,
        "exit_code": proc.returncode,
        "stdout": (proc.stdout or "")[-OUTPUT_LIMIT:],
        "stderr": (proc.stderr or "")[-OUTPUT_LIMIT:],
    }
