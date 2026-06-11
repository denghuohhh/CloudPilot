from typing import Any
import httpx
import re
from .classify import classify_resource

DISK_ALIASES = {
    "夸克": "quark",
    "夸克网盘": "quark",
    "quark": "quark",
    "uc": "uc",
    "uc网盘": "uc",
    "115": "115",
    "115网盘": "115",
    "阿里": "aliyun",
    "阿里云盘": "aliyun",
    "alipan": "aliyun",
    "aliyun": "aliyun",
    "百度": "baidu",
    "百度网盘": "baidu",
    "baidupan": "baidu",
    "天翼": "tianyi",
    "天翼云盘": "tianyi",
    "迅雷": "xunlei",
    "迅雷云盘": "xunlei",
    "移动": "mobile",
    "移动云盘": "mobile",
    "123": "123",
    "123云盘": "123",
}

URL_RE = re.compile(r"https?://[^\s，,。)）\]}】>]+", re.I)
CODE_RE = re.compile(r"(?:提取码|访问码|密码|code|pwd)[:：\s]*([A-Za-z0-9]{4,8})", re.I)

def _normalize_disk(value: Any, text: str = "") -> str:
    raw = str(value or "").strip().lower()
    if raw in DISK_ALIASES:
        return DISK_ALIASES[raw]
    probe = f"{raw} {text}".lower()
    for key, disk in DISK_ALIASES.items():
        if key.lower() in probe:
            return disk
    return raw or "unknown"

def _first_url(*values: Any) -> str:
    for value in values:
        text = str(value or "")
        if text.startswith(("http://", "https://")):
            return text.strip()
        m = URL_RE.search(text)
        if m:
            return m.group(0).strip()
    return ""

def _first_code(*values: Any) -> str:
    for value in values:
        text = str(value or "")
        if not text:
            continue
        m = CODE_RE.search(text)
        if m:
            return m.group(1).strip()
    return ""

def _normalize_items(data: Any) -> list[dict]:
    raw_items = []

    if isinstance(data, list):
        raw_items = [x for x in data if isinstance(x, dict)]

    elif isinstance(data, dict):
        for key in ("items", "results", "list"):
            val = data.get(key)
            if isinstance(val, list):
                raw_items = [x for x in val if isinstance(x, dict)]
                break

        if not raw_items and isinstance(data.get("data"), list):
            raw_items = [x for x in data["data"] if isinstance(x, dict)]

        if not raw_items and isinstance(data.get("data"), dict):
            inner = data["data"]

            merged = inner.get("merged_by_type")
            if isinstance(merged, dict):
                for disk_type, group in merged.items():
                    if isinstance(group, list):
                        for item in group:
                            if isinstance(item, dict):
                                item = dict(item)
                                item.setdefault("disk_type", disk_type)
                                raw_items.append(item)

            if not raw_items:
                for disk_type, group in inner.items():
                    if isinstance(group, list):
                        for item in group:
                            if isinstance(item, dict):
                                item = dict(item)
                                item.setdefault("disk_type", disk_type)
                                raw_items.append(item)

    items = []
    for item in raw_items:
        title = item.get("title") or item.get("name") or item.get("subject") or item.get("note") or "未命名资源"
        note = item.get("note") or item.get("content") or item.get("description") or ""
        url = _first_url(item.get("url"), item.get("link"), item.get("share_url"), item.get("shareUrl"), note, title)
        disk = _normalize_disk(item.get("disk_type") or item.get("type") or item.get("pan") or item.get("cloud"), f"{title} {note} {url}")
        password = item.get("password") or item.get("pwd") or item.get("code") or item.get("share_code") or _first_code(note, title)
        if not url:
            continue
        cls = classify_resource(
            title=title,
            note=note,
            source=item.get("source") or "",
        )
        items.append({
            "title": title,
            "url": url,
            "disk_type": str(disk).lower(),
            "password": password,
            "media_type": cls["media_type"],
            "category": cls["category"],
            "confidence": cls["confidence"],
            "raw": item,
        })
    return items


async def search_pansou(base_url: str, keyword: str, timeout: int = 20) -> list[dict]:
    provider = PanSouProvider(base_url=base_url, timeout=timeout)
    return await provider.search(keyword)


class PanSouProvider:
    def __init__(self, base_url: str, timeout: int = 20):
        self.base_url = (base_url or "").rstrip("/")
        self.timeout = timeout

    async def search(self, keyword: str) -> list[dict]:
        if not self.base_url.startswith(("http://", "https://")):
            raise RuntimeError("PanSou API 地址必须以 http:// 或 https:// 开头")

        candidates = [
            ("GET", "/api/search", {"kw": keyword}),
            ("GET", "/api/search", {"q": keyword}),
            ("GET", "/search", {"kw": keyword}),
            ("GET", "/search", {"q": keyword}),
            ("POST", "/api/search", {"kw": keyword}),
            ("POST", "/api/search", {"q": keyword}),
            ("POST", "/api/search", {"keyword": keyword}),
        ]

        errors = []
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            for method, path, payload in candidates:
                try:
                    url = self.base_url + path
                    if method == "GET":
                        resp = await client.get(url, params=payload)
                    else:
                        resp = await client.post(url, json=payload)

                    if resp.status_code >= 400:
                        errors.append(f"{path}: {resp.status_code} {resp.text[:120]}")
                        continue

                    items = _normalize_items(resp.json())
                    return items
                except Exception as e:
                    errors.append(f"{path}: {e}")

        raise RuntimeError("PanSou 搜索失败：" + " | ".join(errors[-3:]))
