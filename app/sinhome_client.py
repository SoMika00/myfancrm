from typing import Any, Dict, List, Optional

import requests


class SinhomeClientError(RuntimeError):
    pass


def _post(url: str, payload: Dict[str, Any], timeout_s: int = 60) -> str:
    try:
        resp = requests.post(url, json=payload, timeout=timeout_s)
    except requests.RequestException as e:
        raise SinhomeClientError(str(e)) from e

    if resp.status_code >= 400:
        raise SinhomeClientError(f"HTTP {resp.status_code}: {resp.text}")

    data = resp.json()
    if not isinstance(data, dict) or "response" not in data:
        raise SinhomeClientError(f"Unexpected response: {data}")
    return str(data["response"])


def personality_chat(
    api_base_url: str,
    session_id: Optional[str],
    message: str,
    history: List[Dict[str, Any]],
    persona_data: Dict[str, Any],
) -> str:
    return _post(
        f"{api_base_url.rstrip('/')}/personality_chat",
        {
            "session_id": session_id,
            "message": message,
            "history": history,
            "persona_data": persona_data,
        },
    )


def script_chat(
    api_base_url: str,
    session_id: Optional[str],
    message: str,
    history: List[Dict[str, Any]],
    persona_data: Dict[str, Any],
    script: str,
) -> str:
    return _post(
        f"{api_base_url.rstrip('/')}/script_chat",
        {
            "session_id": session_id,
            "message": message,
            "history": history,
            "persona_data": persona_data,
            "script": script,
        },
    )


def script_media(
    api_base_url: str,
    session_id: Optional[str],
    message: str,
    history: List[Dict[str, Any]],
    persona_data: Dict[str, Any],
    script: str,
    media: str,
) -> str:
    return _post(
        f"{api_base_url.rstrip('/')}/script_media",
        {
            "session_id": session_id,
            "message": message,
            "history": history,
            "persona_data": persona_data,
            "script": script,
            "media": media,
        },
    )


def unpersona_chat(
    api_base_url: str,
    session_id: Optional[str],
    message: str,
    history: List[Dict[str, Any]],
    persona_data: Optional[Dict[str, Any]] = None,
) -> str:
    return _post(
        f"{api_base_url.rstrip('/')}/unpersona_chat",
        {
            "session_id": session_id,
            "message": message,
            "history": history,
            "persona_data": persona_data,
        },
    )
