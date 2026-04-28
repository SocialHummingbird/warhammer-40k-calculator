from __future__ import annotations

import argparse
import json
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import parse_qs, urlparse

from . import web_api as web_api_service
from .web_calculation import calculate_from_payload
from .web_state import AppState, WEB_ROOT


def create_handler(state: AppState) -> type[SimpleHTTPRequestHandler]:
    class WarhammerHandler(SimpleHTTPRequestHandler):
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            super().__init__(*args, directory=str(WEB_ROOT), **kwargs)

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path == "/api/health":
                self._send_json(web_api_service.health_payload(state))
                return
            if parsed.path == "/api/data-review":
                query = parse_qs(parsed.query)
                try:
                    payload = web_api_service.data_review_payload_from_query(query, state=state)
                except ValueError as exc:
                    self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
                    return
                self._send_json(payload)
                return
            if parsed.path.startswith("/api/review-files/"):
                try:
                    path, content_type = web_api_service.review_file_download(parsed.path, state=state)
                except ValueError as exc:
                    self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
                    return
                except web_api_service.WebApiNotFound as exc:
                    self._send_error(HTTPStatus.NOT_FOUND, str(exc))
                    return
                self._send_file(path, content_type)
                return
            if parsed.path.startswith("/api/ml-model-files/"):
                try:
                    path, content_type = web_api_service.model_file_download(parsed.path, state=state)
                except ValueError as exc:
                    self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
                    return
                except web_api_service.WebApiNotFound as exc:
                    self._send_error(HTTPStatus.NOT_FOUND, str(exc))
                    return
                self._send_file(path, content_type)
                return
            if parsed.path == "/api/units":
                query = parse_qs(parsed.query)
                try:
                    payload = web_api_service.units_payload_from_query(query, state=state)
                except ValueError as exc:
                    self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
                    return
                self._send_json(payload)
                return
            if parsed.path == "/api/unit":
                query = parse_qs(parsed.query)
                try:
                    payload = web_api_service.unit_payload_from_query(query, state=state)
                except ValueError as exc:
                    self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
                    return
                except web_api_service.WebApiNotFound as exc:
                    self._send_error(HTTPStatus.NOT_FOUND, str(exc))
                    return
                self._send_json(payload)
                return
            if parsed.path == "/api/battlefield/templates":
                self._send_json(web_api_service.battlefield_templates_payload())
                return
            if parsed.path in {"", "/"}:
                self.path = "/index.html"
            return super().do_GET()

        def do_POST(self) -> None:
            parsed = urlparse(self.path)
            battlefield_routes = {
                "/api/army/validate": web_api_service.battlefield_validate_army_payload,
                "/api/battlefield/state/validate": web_api_service.battlefield_validate_state_payload,
                "/api/battlefield/actions": web_api_service.battlefield_actions_payload,
                "/api/battlefield/resolve": web_api_service.battlefield_resolve_payload,
                "/api/battlefield/phase/next": web_api_service.battlefield_advance_phase_payload,
                "/api/battlefield/ai-plan": web_api_service.battlefield_ai_plan_payload,
                "/api/battlefield/autoplay": web_api_service.battlefield_autoplay_payload,
                "/api/battlefield/state/new": web_api_service.battlefield_new_state_payload,
            }
            if parsed.path != "/api/calculate" and parsed.path not in battlefield_routes:
                self._send_error(HTTPStatus.NOT_FOUND, "Unknown endpoint")
                return

            try:
                payload = self._read_json()
                if parsed.path == "/api/calculate":
                    result_payload = calculate_from_payload(payload, state=state)
                else:
                    result_payload = battlefield_routes[parsed.path](payload, state=state)
            except KeyError as exc:
                self._send_error(HTTPStatus.NOT_FOUND, f"Unknown unit: {exc.args[0]}")
                return
            except (ValueError, json.JSONDecodeError) as exc:
                self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
                return
            self._send_json(result_payload)

        def _read_json(self) -> Dict[str, Any]:
            length = int(self.headers.get("Content-Length") or "0")
            raw = self.rfile.read(length)
            if not raw:
                return {}
            payload = json.loads(raw.decode("utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("Expected a JSON object")
            return payload

        def _send_json(self, payload: Dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _send_error(self, status: HTTPStatus, message: str) -> None:
            self._send_json({"error": message}, status=status)

        def _send_file(self, path: Path, content_type: str) -> None:
            try:
                body = path.read_bytes()
            except OSError:
                self._send_error(HTTPStatus.NOT_FOUND, "Review file not found")
                return
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Disposition", f'attachment; filename="{path.name}"')
            self.end_headers()
            self.wfile.write(body)

    return WarhammerHandler


def run_server(*, host: str, port: int, csv_dir: Optional[Path], json_path: Optional[Path], model_path: Optional[Path] = None) -> None:
    state = AppState(csv_dir=csv_dir, json_path=json_path, model_path=model_path)
    handler = create_handler(state)
    server = ThreadingHTTPServer((host, port), handler)
    print(f"Loaded {len(state.units)} units from {state.source}")
    print(f"Open http://{host}:{port}/")
    server.serve_forever()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the local Warhammer 40K calculator web UI")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--csv-dir", type=Path)
    parser.add_argument("--data", type=Path, help="Path to units.json")
    parser.add_argument("--model", type=Path, help="ML model JSON to load for the active edition")
    args = parser.parse_args()
    run_server(host=args.host, port=args.port, csv_dir=args.csv_dir, json_path=args.data, model_path=args.model)


if __name__ == "__main__":
    main()
