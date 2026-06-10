from typing import Any
import httpx


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
        url = item.get("url") or item.get("link") or item.get("share_url") or item.get("shareUrl") or ""
        disk = item.get("disk_type") or item.get("type") or item.get("pan") or item.get("cloud") or "unknown"
        password = item.get("password") or item.get("pwd") or item.get("code") or ""
        if not url:
            continue
        items.append({
            "title": title,
            "url": url,
            "disk_type": str(disk).lower(),
            "password": password,
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
