import ipaddress
import socket
import ssl
from html.parser import HTMLParser
from urllib.parse import urlparse

import httpx


class WebError(Exception):
    """web_fetch 정책 위반 또는 네트워크 오류."""


def _build_ssl_context() -> ssl.SSLContext:
    """OS 신뢰 저장소(Windows schannel 등) 기반 컨텍스트. truststore 없으면 기본 certifi."""
    try:
        import truststore

        return truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    except ImportError:
        return ssl.create_default_context()


_SSL_CONTEXT = _build_ssl_context()


# 본문에서 통째로 제거할 태그 (스크립트/스타일 등)
_SKIP_TAGS = {"script", "style", "noscript", "head", "template"}
_MAX_BYTES = 2_000_000  # 2MB 응답 상한
_MAX_TEXT = 20_000  # 추출 텍스트 문자 상한


def _guard_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise WebError(f"unsupported scheme: {parsed.scheme!r} (http/https only)")
    host = parsed.hostname
    if not host:
        raise WebError("missing host in URL")
    # 호스트명을 IP 로 해석해 localhost/사설/링크로컬/예약 대역 차단 (SSRF 방지)
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror as e:
        raise WebError(f"cannot resolve host {host!r}: {e}") from e
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if (
            ip.is_loopback
            or ip.is_private
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
            or ip.is_unspecified
        ):
            raise WebError(f"blocked internal address for host {host!r}: {ip}")
    return url


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._skip = 0
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: object) -> None:
        if tag in _SKIP_TAGS:
            self._skip += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in _SKIP_TAGS and self._skip > 0:
            self._skip -= 1

    def handle_data(self, data: str) -> None:
        if self._skip == 0:
            stripped = data.strip()
            if stripped:
                self.parts.append(stripped)


def _html_to_text(html: str) -> str:
    parser = _TextExtractor()
    parser.feed(html)
    return "\n".join(parser.parts)


def web_fetch(url: str, timeout: int = 20) -> dict:
    _guard_url(url)
    timeout = max(1, min(timeout, 60))
    try:
        with httpx.Client(
            follow_redirects=True,
            timeout=timeout,
            max_redirects=5,
            verify=_SSL_CONTEXT,
        ) as client:
            resp = client.get(url, headers={"User-Agent": "llm-nexus-agent/1.0"})
    except httpx.HTTPError as e:
        raise WebError(f"fetch failed: {e}") from e

    content_type = resp.headers.get("content-type", "").split(";")[0].strip()
    raw = resp.content[:_MAX_BYTES]
    body = raw.decode(resp.encoding or "utf-8", errors="replace")

    if "html" in content_type:
        text = _html_to_text(body)
    else:
        text = body
    truncated = len(text) > _MAX_TEXT

    return {
        "url": str(resp.url),
        "status": resp.status_code,
        "content_type": content_type,
        "text": text[:_MAX_TEXT],
        "truncated": truncated,
    }
