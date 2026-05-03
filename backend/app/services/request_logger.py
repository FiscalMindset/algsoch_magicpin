"""Request Logger — tracks all API requests for the monitoring dashboard."""

import time
import json
import hashlib
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from collections import deque


class RequestLogEntry:
    """A single API request log entry."""

    __slots__ = [
        "id", "timestamp", "method", "path", "query", "status_code",
        "request_body", "response_body", "response_summary",
        "duration_ms", "ip", "user_agent", "error",
    ]

    def __init__(
        self, method: str, path: str, status_code: int,
        duration_ms: float, request_body: Optional[Dict] = None,
        response_body: Optional[Dict] = None, query: str = "",
        ip: str = "", user_agent: str = "", error: Optional[str] = None,
    ):
        now = datetime.now(timezone.utc)
        self.id = hashlib.md5(f"{now.isoformat()}{method}{path}{time.time()}".encode()).hexdigest()[:10]
        self.timestamp = now.isoformat()
        self.method = method
        self.path = path
        self.query = query
        self.status_code = status_code
        self.request_body = self._truncate(request_body)
        self.response_body = self._truncate(response_body)
        self.response_summary = self._summarize(response_body, status_code)
        self.duration_ms = round(duration_ms, 1)
        self.ip = ip
        self.user_agent = user_agent
        self.error = error

    @staticmethod
    def _truncate(data: Optional[Any], max_len: int = 2000) -> Optional[Any]:
        if data is None:
            return None
        s = json.dumps(data) if not isinstance(data, str) else data
        if len(s) > max_len:
            return s[:max_len] + '..."[truncated]'
        return data

    @staticmethod
    def _summarize(data: Optional[Dict], status_code: int) -> str:
        if data is None:
            return f"HTTP {status_code}"
        if isinstance(data, dict):
            if "action" in data:
                return f"action={data['action']}, body='{(data.get('body') or '')[:60]}'"
            if "actions" in data:
                return f"{len(data['actions'])} actions"
            if "accepted" in data:
                return f"accepted={data['accepted']}"
            if "uptime_seconds" in data:
                return f"uptime={data['uptime_seconds']}s"
            keys = ", ".join(list(data.keys())[:5])
            return f"keys: {keys}"
        return str(data)[:100]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "timestamp": self.timestamp,
            "method": self.method,
            "path": self.path,
            "query": self.query,
            "status_code": self.status_code,
            "request_body": self.request_body,
            "response_body": self.response_body,
            "response_summary": self.response_summary,
            "duration_ms": self.duration_ms,
            "ip": self.ip,
            "user_agent": self.user_agent,
            "error": self.error,
        }


class RequestLogger:
    """In-memory circular buffer for API request logs."""

    MAX_ENTRIES = 500

    def __init__(self):
        self._logs: deque = deque(maxlen=self.MAX_ENTRIES)

    def log(self, entry: RequestLogEntry):
        self._logs.appendleft(entry)

    def get_logs(
        self, limit: int = 100, offset: int = 0,
        method: Optional[str] = None, path: Optional[str] = None,
        status: Optional[int] = None, search: Optional[str] = None,
    ) -> Dict[str, Any]:
        logs = list(self._logs)

        if method:
            logs = [l for l in logs if l.method == method.upper()]
        if path:
            logs = [l for l in logs if path.lower() in l.path.lower()]
        if status:
            logs = [l for l in logs if l.status_code == status]
        if search:
            s = search.lower()
            logs = [l for l in logs if s in l.path.lower() or s in (l.response_summary or "").lower()
                    or s in json.dumps(l.request_body or "")[:200].lower()]

        total = len(logs)
        page = logs[offset:offset + limit]

        # Stats
        methods = {}
        status_codes = {}
        endpoints = {}
        total_time = 0
        error_count = 0
        for l in self._logs:
            methods[l.method] = methods.get(l.method, 0) + 1
            status_codes[l.status_code] = status_codes.get(l.status_code, 0) + 1
            endpoints[l.path] = endpoints.get(l.path, 0) + 1
            total_time += l.duration_ms
            if l.status_code >= 400:
                error_count += 1

        return {
            "total": total,
            "returned": len(page),
            "logs": [l.to_dict() for l in page],
            "stats": {
                "total_requests": len(self._logs),
                "avg_duration_ms": round(total_time / max(len(self._logs), 1), 1),
                "error_count": error_count,
                "error_rate": round(error_count / max(len(self._logs), 1) * 100, 1),
                "methods": methods,
                "status_codes": {str(k): v for k, v in sorted(status_codes.items())},
                "top_endpoints": dict(sorted(endpoints.items(), key=lambda x: x[1], reverse=True)[:10]),
            },
        }

    def clear(self):
        self._logs.clear()

    @property
    def count(self) -> int:
        return len(self._logs)


# Global singleton
request_logger = RequestLogger()
