"""Read and write dashboard JSON documents in a Supabase Storage bucket."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlparse
from urllib.request import Request, urlopen

import streamlit as st
from streamlit.errors import StreamlitSecretNotFoundError


@dataclass(frozen=True)
class StorageConfig:
    url: str
    service_key: str
    bucket: str


def load_storage_config() -> StorageConfig | None:
    try:
        settings = st.secrets["supabase"]
    except (StreamlitSecretNotFoundError, KeyError):
        return None

    if not hasattr(settings, "get"):
        raise ValueError("The [supabase] Streamlit secrets section must be a table.")

    values = {
        "url": str(settings.get("url", "")).strip().rstrip("/"),
        "service_key": str(settings.get("service_key", "")).strip(),
        "bucket": str(settings.get("bucket", "")).strip(),
    }
    if not any(values.values()):
        return None
    missing = [key for key, value in values.items() if not value]
    if missing:
        raise ValueError(
            "Supabase Storage settings are incomplete. Missing: "
            + ", ".join(missing)
            + "."
        )

    parsed_url = urlparse(values["url"])
    if parsed_url.scheme != "https" or not parsed_url.hostname:
        raise ValueError(
            "Supabase Storage URL must use HTTPS and include a valid project host."
        )
    if parsed_url.hostname.endswith(".storage.supabase.co"):
        project_ref = parsed_url.hostname.removesuffix(".storage.supabase.co")
        if not project_ref or parsed_url.path not in ("", "/", "/storage/v1/s3"):
            raise ValueError("The Supabase S3 endpoint URL is not in a recognized format.")
        values["url"] = f"https://{project_ref}.supabase.co"
    elif parsed_url.hostname.endswith(".supabase.co") and parsed_url.path in ("", "/"):
        values["url"] = f"https://{parsed_url.hostname}"
    else:
        raise ValueError(
            "Supabase Storage URL must be the project API URL "
            "or its Supabase S3 endpoint."
        )
    return StorageConfig(**values)


def _request_url(config: StorageConfig, object_path: str) -> str:
    bucket = quote(config.bucket, safe="")
    path = quote(object_path.lstrip("/"), safe="/")
    return f"{config.url}/storage/v1/object/{bucket}/{path}"


def verify_bucket(config: StorageConfig) -> None:
    bucket = quote(config.bucket, safe="")
    request = Request(
        f"{config.url}/storage/v1/bucket/{bucket}",
        headers={
            "apikey": config.service_key,
            "Authorization": f"Bearer {config.service_key}",
        },
        method="GET",
    )
    try:
        with urlopen(request, timeout=15):
            return
    except HTTPError as exc:
        if exc.code == 404:
            raise RuntimeError(
                f"Supabase bucket '{config.bucket}' was not found or is not accessible."
            ) from exc
        raise RuntimeError(
            f"Supabase Storage connection failed with HTTP {exc.code}."
        ) from exc
    except URLError as exc:
        raise RuntimeError("Could not reach Supabase Storage.") from exc


def read_document(config: StorageConfig, object_path: str) -> Any | None:
    request = Request(
        _request_url(config, object_path),
        headers={
            "apikey": config.service_key,
            "Authorization": f"Bearer {config.service_key}",
        },
        method="GET",
    )
    try:
        with urlopen(request, timeout=15) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        if exc.code == 404:
            return None
        raise RuntimeError(
            f"Supabase Storage read failed with HTTP {exc.code}."
        ) from exc
    except URLError as exc:
        raise RuntimeError("Could not reach Supabase Storage.") from exc
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(
            f"Supabase object '{object_path}' does not contain valid JSON."
        ) from exc


def write_document(config: StorageConfig, object_path: str, payload: Any) -> None:
    body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
    request = Request(
        _request_url(config, object_path),
        data=body,
        headers={
            "apikey": config.service_key,
            "Authorization": f"Bearer {config.service_key}",
            "Content-Type": "application/json",
            "x-upsert": "true",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=15):
            return
    except HTTPError as exc:
        raise RuntimeError(
            f"Supabase Storage write failed with HTTP {exc.code}."
        ) from exc
    except URLError as exc:
        raise RuntimeError("Could not reach Supabase Storage.") from exc
