"""Tiny httpx2 compatibility subset for Starlette's TestClient in tests."""

from __future__ import annotations

import json as _json
from types import SimpleNamespace
from urllib.parse import urljoin, urlsplit

USE_CLIENT_DEFAULT = object()
_client = SimpleNamespace(USE_CLIENT_DEFAULT=USE_CLIENT_DEFAULT, UseClientDefault=object)
_types = SimpleNamespace(
    CookieTypes=object, URLTypes=object, RequestContent=object, RequestFiles=object,
    QueryParamTypes=object, HeaderTypes=object, AuthTypes=object, TimeoutTypes=object,
)

class ByteStream:
    def __init__(self, content: bytes):
        self.content = content

class Headers(dict):
    def multi_items(self):
        return list(self.items())

class URL:
    def __init__(self, url: str):
        self.raw = str(url)
        parts = urlsplit(self.raw)
        self.scheme = parts.scheme or "http"
        self.netloc = parts.netloc.encode("ascii")
        self.path = parts.path or "/"
        self.raw_path = self.path.encode("ascii") + (("?" + parts.query).encode("ascii") if parts.query else b"")
        self.query = parts.query.encode("ascii")

    def __str__(self):
        return self.raw

class Request:
    def __init__(self, method: str, url: str, *, headers=None, content: bytes = b""):
        self.method = method.upper()
        self.url = URL(url)
        self.headers = Headers(headers or {})
        self._content = content
    def read(self):
        return self._content

class Response:
    def __init__(self, status_code: int, headers=None, content: bytes | None = None, stream: ByteStream | None = None, request: Request | None = None):
        self.status_code = status_code
        self.headers = Headers(dict(headers or {}))
        self.content = content if content is not None else (stream.content if stream else b"")
        self.request = request
    def json(self):
        return _json.loads(self.content.decode("utf-8"))
    @property
    def text(self):
        return self.content.decode("utf-8")

class BaseTransport:
    def handle_request(self, request: Request) -> Response:
        raise NotImplementedError

class Client:
    def __init__(self, *, base_url: str = "", headers=None, transport: BaseTransport | None = None, **kwargs):
        self.base_url = base_url
        self.headers = Headers(headers or {})
        self._transport = transport
    def _merge_url(self, url):
        return urljoin(self.base_url.rstrip("/") + "/", str(url).lstrip("/"))
    def request(self, method, url, *, content=None, data=None, json=None, params=None, headers=None, **kwargs):
        body = content if content is not None else b""
        merged_headers = Headers(self.headers.copy())
        if headers:
            merged_headers.update(headers)
        if json is not None:
            body = _json.dumps(json).encode("utf-8")
            merged_headers.setdefault("content-type", "application/json")
        elif isinstance(data, dict):
            body = "&".join(f"{k}={v}" for k, v in data.items()).encode()
        elif isinstance(data, (bytes, str)):
            body = data.encode() if isinstance(data, str) else data
        if params:
            sep = "&" if "?" in str(url) else "?"
            url = str(url) + sep + "&".join(f"{k}={v}" for k, v in dict(params).items())
        request = Request(method, str(url), headers=merged_headers, content=body)
        if self._transport is None:
            raise RuntimeError("No transport configured")
        return self._transport.handle_request(request)
    def get(self, url, **kwargs): return self.request("GET", url, **kwargs)
    def post(self, url, **kwargs): return self.request("POST", url, **kwargs)
    def put(self, url, **kwargs): return self.request("PUT", url, **kwargs)
    def patch(self, url, **kwargs): return self.request("PATCH", url, **kwargs)
    def delete(self, url, **kwargs): return self.request("DELETE", url, **kwargs)
    def options(self, url, **kwargs): return self.request("OPTIONS", url, **kwargs)
    def head(self, url, **kwargs): return self.request("HEAD", url, **kwargs)
