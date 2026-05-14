"""
OpenClaw topic_research_report skill runtime.

This module is intentionally self-contained:
- No hard-coded user identity.
- Runtime defaults are defined in-code.
"""

import argparse
import asyncio
import base64
import json
import os
import re
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib import error as urllib_error
from urllib import request as urllib_request

EM_API_KEY = os.environ.get("EM_API_KEY", "").strip()
if not EM_API_KEY:
    raise ValueError("EM_API_KEY 环境变量未设置")
DEFAULT_OUTPUT_DIR = Path.cwd() / "miaoxiang" / "topic_research_report"
TIMEOUT_SECONDS = 1200
TOPIC_RESEARCH_URL = (
    "https://ai-saas.eastmoney.com/proxy/"
    "app-robo-advisor-api/assistant/write/thematic/research"
)


def _extract_error_message(body: str) -> str:
    body = (body or "").strip()
    if not body:
        return ""
    try:
        data = json.loads(body)
    except Exception:
        return body[:200]
    if isinstance(data, dict):
        for key in ("msg", "message", "error", "stack"):
            value = data.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return body[:200]


def _extract_content(raw: Dict[str, Any]) -> str:
    """
    Extract readable report body from API response.
    Prioritize data.content for this thematic research API.
    """
    if not isinstance(raw, dict):
        return ""

    data = raw.get("data")
    if isinstance(data, dict):
        for key in ("content", "displayData", "answer", "summary"):
            value = data.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
            if isinstance(value, (list, dict)):
                return json.dumps(value, ensure_ascii=False, indent=2)

    for key in ("content", "displayData", "answer", "summary"):
        value = raw.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
        if isinstance(value, (list, dict)):
            return json.dumps(value, ensure_ascii=False, indent=2)

    return json.dumps(raw, ensure_ascii=False, indent=2)


def _has_valid_report(raw: Dict[str, Any]) -> bool:
    """
    Determine whether API response contains a successful report payload.
    Used to avoid saving md files for unsupported/failed scenarios.
    """
    if not isinstance(raw, dict):
        return False

    code = raw.get("code")
    if code is not None and code != 200:
        return False

    status = raw.get("status")
    if status is not None and status != 200:
        return False

    data = raw.get("data")
    if not isinstance(data, dict):
        return False

    content = data.get("content")
    if isinstance(content, str):
        return bool(content.strip())
    if isinstance(content, list):
        return len(content) > 0
    if isinstance(content, dict):
        return len(content) > 0

    return False


def _safe_article_id(value: Any) -> str:
    article_id = ""
    if isinstance(value, str):
        article_id = value.strip()
    elif value is not None:
        article_id = str(value).strip()
    if not article_id:
        article_id = uuid.uuid4().hex
    return re.sub(r"[^a-zA-Z0-9_-]+", "_", article_id)


def _decode_attachment_base64(data: Dict[str, Any], output_dir: Path) -> List[Dict[str, str]]:
    attachments: List[Dict[str, str]] = []
    output_dir.mkdir(parents=True, exist_ok=True)

    file_map = [
        ("wordBase64", "docx", "DOCX"),
        ("pdfBase64", "pdf", "PDF"),
    ]
    safe_article_id = _safe_article_id(data.get("articleId"))

    for key, ext, ftype in file_map:
        b64_value = data.get(key)
        b64_str = b64_value.strip() if isinstance(b64_value, str) else ""
        if not b64_str:
            continue
        try:
            raw = base64.b64decode(b64_str)
        except Exception:
            continue
        file_name = "{0}_{1}.{2}".format(safe_article_id, ftype.lower(), ext)
        file_path = output_dir / file_name
        file_path.write_bytes(raw)
        attachments.append({"type": ftype, "path": str(file_path)})
    return attachments


def _http_call_topic_research(query: str) -> Dict[str, Any]:
    payload = {"query": query}
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib_request.Request(
        url=TOPIC_RESEARCH_URL,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "em_api_key": EM_API_KEY,
        },
    )

    try:
        with urllib_request.urlopen(req, timeout=TIMEOUT_SECONDS) as resp:
            raw_body = resp.read().decode("utf-8", errors="replace")
    except urllib_error.HTTPError as exc:
        err_body = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
        message = _extract_error_message(err_body) or "http status {0}".format(exc.code)
        raise RuntimeError("Topic research API request failed: {0}".format(message))
    except urllib_error.URLError as exc:
        raise RuntimeError("Topic research API request failed: {0}".format(exc.reason))

    try:
        parsed = json.loads(raw_body)
    except json.JSONDecodeError:
        raise RuntimeError("Topic research API returned invalid JSON response.")

    if isinstance(parsed, dict):
        return parsed
    return {"data": parsed}


async def generate_topic_research_report(
    query: str,
    output_dir: Optional[Path] = None,
    save_to_file: bool = True,
) -> Dict[str, Any]:
    query = (query or "").strip()
    if not query:
        return {
            "query": "",
            "title": "",
            "article_id": "",
            "share_url": "",
            "content": "",
            "attachments": [],
            "raw": None,
            "error": "query is empty",
        }

    out_dir = Path(output_dir or DEFAULT_OUTPUT_DIR)
    out_dir.mkdir(parents=True, exist_ok=True)

    result: Dict[str, Any] = {
        "query": query,
        "title": "",
        "article_id": "",
        "share_url": "",
        "content": "",
        "attachments": [],
        "raw": None,
    }

    try:
        loop = asyncio.get_event_loop()
        raw = await loop.run_in_executor(None, _http_call_topic_research, query)
    except Exception as exc:
        result["error"] = str(exc)
        return result

    result["raw"] = raw
    result["content"] = _extract_content(raw)

    data = raw.get("data") if isinstance(raw, dict) else None
    if isinstance(data, dict):
        title = data.get("title")
        article_id = data.get("articleId")
        share_url = data.get("shareUrl")
        if isinstance(title, str):
            result["title"] = title
        if isinstance(article_id, str):
            result["article_id"] = article_id
        if isinstance(share_url, str):
            result["share_url"] = share_url

        if _has_valid_report(raw):
            attachments = _decode_attachment_base64(data, out_dir)
            if attachments:
                result["attachments"] = attachments

    return result


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate thematic research report from natural language query."
    )
    parser.add_argument("--query", type=str, help="Natural language research query.")
    parser.add_argument("--no-save", action="store_true", help="Do not save result to local file.")
    return parser


def run_cli() -> None:
    parser = _build_arg_parser()
    args = parser.parse_args()

    query = (args.query or "").strip()
    if not query:
        import sys

        query = (sys.stdin.read() or "").strip()

    if not query:
        parser.print_help()
        raise SystemExit(1)

    async def _main() -> None:
        result = await generate_topic_research_report(query=query, save_to_file=not args.no_save)
        if "error" in result:
            print("Error: {0}".format(result["error"]))
            raise SystemExit(2)
        if result.get("title"):
            print("Title: {0}".format(result["title"]))
        if result.get("share_url"):
            print("ShareUrl: {0}".format(result["share_url"]))
        for attachment in result.get("attachments", []):
            atype = attachment.get("type", "")
            apath = attachment.get("path", "")
            if apath:
                print("{0}: {1}".format(atype, apath))
        print(result.get("content", ""))

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(_main())
    finally:
        loop.close()


if __name__ == "__main__":
    run_cli()
