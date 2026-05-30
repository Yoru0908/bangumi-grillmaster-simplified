from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from http.cookies import SimpleCookie
from pathlib import Path
from urllib.parse import urlparse

from services.saas.api_service import ApiError, SaasApiService
from services.saas.auth import (
    AuthService,
    InvalidCredentials,
    AccountDisabled,
)


@dataclass(frozen=True)
class HttpResponse:
    status_code: int
    body: bytes
    headers: dict[str, str] = field(default_factory=dict)

    @property
    def json_body(self) -> dict:
        return json.loads(self.body.decode("utf-8"))


class SaasHttpApp:
    def __init__(
        self,
        conn,
        *,
        min_submit_credit_minutes: float = 10,
        metadata_fetcher=None,
        now=None,
        session_ttl_days: int = 30,
        static_root: Path | None = None,
    ):
        self.conn = conn
        self.now = now or _utc_now
        self.session_ttl_days = session_ttl_days
        self.static_root = static_root or Path(__file__).resolve().parents[2] / "web"
        self.api = SaasApiService(
            conn,
            min_submit_credit_minutes=min_submit_credit_minutes,
            metadata_fetcher=metadata_fetcher,
        )
        self.last_login_cookie = ""

    def handle(
        self,
        method: str,
        path: str,
        *,
        headers: dict[str, str],
        body: bytes,
    ) -> HttpResponse:
        origin = _header(headers, "origin")
        try:
            resp = self._handle(method.upper(), urlparse(path).path, headers, body)
        except ApiError as exc:
            resp = _json_response(
                exc.status_code,
                {"error": {"code": exc.code, "message": exc.message}},
            )
        except (InvalidCredentials, AccountDisabled) as exc:
            resp = _json_response(
                401,
                {"error": {"code": "AUTH_FAILED", "message": str(exc)}},
            )
        except json.JSONDecodeError:
            resp = _json_response(
                400,
                {"error": {"code": "INVALID_JSON", "message": "Invalid JSON body"}},
            )
        except KeyError as exc:
            resp = _json_response(
                400,
                {"error": {"code": "BAD_REQUEST", "message": f"Missing required field: {exc.args[0]}"}},
            )
        if origin:
            cors = _cors_headers(origin)
            if cors:
                resp.headers.update(cors)
        return resp

    def _handle(
        self,
        method: str,
        path: str,
        headers: dict[str, str],
        body: bytes,
    ) -> HttpResponse:
        now = self.now()
        if method == "OPTIONS":
            return _cors_preflight(_header(headers, "origin"))
        if method == "GET" and path == "/":
            return self._static_file("index.html", "text/html; charset=utf-8")
        if method == "GET" and path == "/app.js":
            return self._static_file("app.js", "text/javascript; charset=utf-8")
        if method == "GET" and path == "/styles.css":
            return self._static_file("styles.css", "text/css; charset=utf-8")
        if method == "GET" and path == "/static/app.js":
            return self._static_file("app.js", "text/javascript; charset=utf-8")
        if method == "GET" and path == "/static/styles.css":
            return self._static_file("styles.css", "text/css; charset=utf-8")
        if method == "GET" and path == "/healthz":
            self.conn.execute("SELECT 1").fetchone()
            return _json_response(200, {"ok": True, "database": "ok"})
        if method == "POST" and path == "/api/auth/login":
            return self._login(body, now=now)
        if method == "POST" and path == "/api/auth/logout":
            return self._logout(headers)
        if method == "GET" and path == "/api/auth/me":
            return self._me(headers, now=now)
        if method == "POST" and path == "/api/jobs":
            payload = _json_payload(body)
            return _json_response(
                200,
                self.api.submit_job(
                    session_id=_session_id(headers),
                    source_url=payload["source_url"],
                    now=now,
                ),
            )
        if method == "POST" and path == "/api/playground/jobs":
            payload = _json_payload(body)
            return _json_response(
                200,
                self.api.submit_playground_job_anonymous(
                    source_url=payload["source_url"],
                    now=now,
                ),
            )
        if method == "GET" and path == "/api/jobs":
            return _json_response(
                200,
                {"jobs": self.api.list_jobs(_session_id(headers), now=now)},
            )
        if method == "GET" and path == "/api/billing":
            return _json_response(
                200,
                self.api.get_billing_summary(_session_id(headers), now=now),
            )

        parts = [part for part in path.split("/") if part]
        if parts == ["api", "admin", "jobs"] and method == "GET":
            return _json_response(
                200,
                {
                    "jobs": self.api.admin_list_jobs(
                        admin_session_id=_session_id(headers),
                        now=now,
                    )
                },
            )
        if parts == ["api", "admin", "users"] and method == "GET":
            return _json_response(
                200,
                {
                    "users": self.api.admin_list_users(
                        admin_session_id=_session_id(headers),
                        now=now,
                    )
                },
            )
        if parts == ["api", "admin", "audit-logs"] and method == "GET":
            return _json_response(
                200,
                {
                    "audit_logs": self.api.admin_list_audit_logs(
                        admin_session_id=_session_id(headers),
                        now=now,
                    )
                },
            )
        if (
            len(parts) == 5
            and parts[:3] == ["api", "admin", "jobs"]
            and parts[4] == "retry"
            and method == "POST"
        ):
            return _json_response(
                200,
                self.api.admin_retry_job(
                    admin_session_id=_session_id(headers),
                    job_id=parts[3],
                    now=now,
                ),
            )
        if len(parts) == 4 and parts[:3] == ["api", "admin", "jobs"] and method == "DELETE":
            payload = _json_payload(body)
            return _json_response(
                200,
                self.api.admin_cancel_job(
                    admin_session_id=_session_id(headers),
                    job_id=parts[3],
                    reason=payload.get("reason", ""),
                    now=now,
                ),
            )
        if (
            len(parts) == 6
            and parts[:3] == ["api", "admin", "users"]
            and parts[4:] == ["credits", "adjust"]
            and method == "POST"
        ):
            payload = _json_payload(body)
            return _json_response(
                200,
                self.api.admin_adjust_credits(
                    admin_session_id=_session_id(headers),
                    target_user_id=parts[3],
                    minutes=float(payload["minutes"]),
                    reason=payload["reason"],
                    now=now,
                ),
            )
        if len(parts) == 3 and parts[:2] == ["api", "jobs"] and method == "GET":
            return _json_response(
                200,
                {"job": self.api.get_job(_session_id(headers), parts[2], now=now)},
            )
        if (
            len(parts) == 4
            and parts[:2] == ["api", "jobs"]
            and parts[3] == "events"
            and method == "GET"
        ):
            return _json_response(
                200,
                {
                    "events": self.api.get_job_events(
                        _session_id(headers),
                        parts[2],
                        now=now,
                    )
                },
            )
        if (
            len(parts) == 5
            and parts[:2] == ["api", "jobs"]
            and parts[3] == "download"
            and method == "GET"
        ):
            return self._download(_session_id(headers), parts[2], parts[4], now=now)

        if method == "POST" and path == "/api/billing/checkout":
            from services.saas.stripe_handler import create_checkout_session
            payload = _json_payload(body)
            user = self.api._require_user(_session_id(headers), now=now)
            url = create_checkout_session(
                plan_key=payload["plan"],
                user_email=user.email,
                user_id=user.id,
                base_url=payload.get("base_url", ""),
            )
            return _json_response(200, {"url": url})
        if method == "POST" and path == "/api/billing/webhook":
            from services.saas.stripe_handler import handle_webhook
            sig = _header(headers, "stripe-signature")
            result = handle_webhook(body, sig or "")
            if result.get("status") == "ok":
                self.api.grant_credits_from_stripe(result["user_id"], result["minutes"])
            return _json_response(200, result)

        return _json_response(
            404,
            {"error": {"code": "NOT_FOUND", "message": "Route not found"}},
        )

    def _static_file(self, name: str, content_type: str) -> HttpResponse:
        path = self.static_root / name
        if not path.is_file():
            return _json_response(
                404,
                {"error": {"code": "NOT_FOUND", "message": "Static asset not found"}},
            )
        return HttpResponse(
            200,
            path.read_bytes(),
            {
                "Content-Type": content_type,
                "Cache-Control": "no-store",
            },
        )

    def _login(self, body: bytes, *, now: str) -> HttpResponse:
        payload = _json_payload(body)
        result = AuthService(self.conn).login_with_password(
            email=payload["email"],
            password=payload["password"],
            now=now,
            session_expires_at=_days_after(now, self.session_ttl_days),
        )
        cookie = (
            f"session_id={result.session['id']}; Path=/; HttpOnly; "
            "SameSite=Lax"
        )
        self.last_login_cookie = cookie
        return _json_response(
            200,
            {"user": result.user},
            headers={"Set-Cookie": cookie},
        )

    def _logout(self, headers: dict[str, str]) -> HttpResponse:
        session_id = _session_id(headers)
        if session_id:
            AuthService(self.conn).logout(session_id)
        return _json_response(
            200,
            {"ok": True},
            headers={
                "Set-Cookie": "session_id=; Path=/; HttpOnly; SameSite=Lax; Max-Age=0"
            },
        )

    def _me(self, headers: dict[str, str], *, now: str) -> HttpResponse:
        session_id = _session_id(headers)
        if not session_id:
            raise ApiError(401, "AUTH_REQUIRED", "Authentication required")
        user = AuthService(self.conn).get_current_user(session_id, now=now)
        if user is None:
            raise ApiError(401, "AUTH_REQUIRED", "Authentication required")
        return _json_response(200, {"user": user})

    def _download(
        self,
        session_id: str | None,
        job_id: str,
        artifact: str,
        *,
        now: str,
    ) -> HttpResponse:
        path = Path(
            self.api.get_download_path(session_id, job_id, artifact, now=now)
        )
        if not path.exists():
            raise ApiError(404, "ARTIFACT_NOT_FOUND", f"artifact not found: {artifact}")
        # Use video title as download filename
        from urllib.parse import quote
        job = self.conn.execute("SELECT video_title FROM jobs WHERE id=?", (job_id,)).fetchone()
        title = (dict(job).get("video_title") or job_id)[:80] if job else job_id
        suffix_map = {"original.srt": " 原文.srt", "finalized.srt": " 译文.srt"}
        filename = title + suffix_map.get(artifact, ".srt")
        return HttpResponse(
            200,
            path.read_bytes(),
            {
                "Content-Type": "text/plain; charset=utf-8",
                "Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}",
            },
        )


def _cors_preflight(origin: str | None) -> HttpResponse:
    h = _cors_headers(origin)
    h.update({"Access-Control-Allow-Methods": "GET, POST, DELETE, OPTIONS",
              "Access-Control-Allow-Headers": "Content-Type",
              "Access-Control-Max-Age": "86400"})
    return HttpResponse(204, b"", h)


ALLOWED_ORIGINS = {"https://kotoba-forge.pages.dev", "https://kotoba.46log.com", "https://kotoba.sakamichi-tools.cfd"}


def _cors_headers(origin: str | None) -> dict:
    if origin and origin in ALLOWED_ORIGINS:
        return {
            "Access-Control-Allow-Origin": origin,
            "Access-Control-Allow-Credentials": "true",
        }
    return {}


def _json_payload(body: bytes) -> dict:
    return json.loads((body or b"{}").decode("utf-8"))


def _json_response(
    status_code: int,
    payload: dict,
    *,
    headers: dict[str, str] | None = None,
) -> HttpResponse:
    response_headers = {"Content-Type": "application/json; charset=utf-8"}
    if headers:
        response_headers.update(headers)
    return HttpResponse(
        status_code,
        json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        response_headers,
    )


def _session_id(headers: dict[str, str]) -> str | None:
    cookie_header = _header(headers, "cookie")
    if not cookie_header:
        return None
    cookie = SimpleCookie()
    cookie.load(cookie_header)
    morsel = cookie.get("session_id")
    return morsel.value if morsel else None


def _header(headers: dict[str, str], name: str) -> str | None:
    for key, value in headers.items():
        if key.lower() == name.lower():
            return value
    return None


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _days_after(value: str, days: int) -> str:
    base = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return (base + timedelta(days=days)).isoformat().replace("+00:00", "Z")