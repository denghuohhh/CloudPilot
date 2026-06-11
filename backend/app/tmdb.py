import re
import httpx

TMDB_IMAGE_BASE = "https://image.tmdb.org/t/p/w300"

KIDS_WORDS = ["小猪佩奇", "peppa", "汪汪队", "paw patrol", "海底小纵队", "超级飞侠", "天线宝宝", "朵拉", "小马宝莉", "巴巴爸爸"]
CN_ANIME_WORDS = ["熊出没", "喜羊羊", "猪猪侠", "斗罗大陆", "完美世界", "吞噬星空", "凡人修仙传"]
JP_ANIME_WORDS = ["海贼王", "火影", "死神", "名侦探柯南", "咒术回战", "鬼灭之刃", "进击的巨人"]


def clean_title(title: str) -> str:
    s = title or ""
    s = re.sub(r"https?://\S+", " ", s)
    s = re.sub(r"\[[^\]]+\]|【[^】]+】", " ", s)
    s = re.sub(r"(4k|1080p|2160p|hdr|dv|remux|bluray|web-dl|bdrip|x265|h265|h264|中字|字幕|国英双语|内封|高码率|蓝光|原盘|合集|系列|web|imax|gb)", " ", s, flags=re.I)
    s = re.sub(r"\s+", " ", s).strip()
    return s[:60]


def year_from_text(text: str):
    m = re.search(r"(19\d{2}|20\d{2})", text or "")
    return m.group(1) if m else None


def classify_tmdb(item: dict, raw_title: str = "") -> dict:
    media_type = item.get("media_type")
    lang = item.get("original_language") or ""
    genres = [str(g).lower() for g in item.get("genre_names", [])]
    countries = [str(c).upper() for c in item.get("origin_country", [])]
    text = f"{raw_title} {item.get('tmdb_title','')} {item.get('tmdb_original_title','')}".lower()

    # 电影
    if media_type == "movie":
        if "animation" in genres or "动画" in genres:
            return {"media_type": "电影", "category": "动画电影", "confidence": 95}
        if lang in ("zh", "cn", "bo", "za") or any(c in countries for c in ["CN", "HK", "TW"]):
            return {"media_type": "电影", "category": "华语电影", "confidence": 95}
        return {"media_type": "电影", "category": "外语电影", "confidence": 90}

    # 电视剧：按 MP 逻辑，特殊类型优先
    if media_type == "tv":
        if any(w.lower() in text for w in KIDS_WORDS):
            return {"media_type": "电视剧", "category": "儿童", "confidence": 98}

        if "kids" in genres or "儿童" in genres or "family" in genres or "家庭" in genres:
            return {"media_type": "电视剧", "category": "儿童", "confidence": 95}

        if "documentary" in genres or "纪录" in genres:
            return {"media_type": "电视剧", "category": "纪录片", "confidence": 95}

        if "reality" in genres or "talk" in genres or "真人秀" in genres or "脱口秀" in genres:
            return {"media_type": "电视剧", "category": "综艺", "confidence": 90}

        if any(w.lower() in text for w in CN_ANIME_WORDS):
            return {"media_type": "电视剧", "category": "国漫", "confidence": 98}

        if any(w.lower() in text for w in JP_ANIME_WORDS):
            return {"media_type": "电视剧", "category": "日番", "confidence": 98}

        if "animation" in genres or "动画" in genres:
            if lang == "ja" or "JP" in countries:
                return {"media_type": "电视剧", "category": "日番", "confidence": 95}
            if lang in ("zh", "cn") or any(c in countries for c in ["CN", "HK", "TW"]):
                return {"media_type": "电视剧", "category": "国漫", "confidence": 95}
            # 欧美动画默认不再直接进欧美剧；低龄优先儿童，成人动画才欧美剧
            return {"media_type": "电视剧", "category": "儿童", "confidence": 80}

        if lang in ("zh", "cn") or any(c in countries for c in ["CN", "HK", "TW"]):
            return {"media_type": "电视剧", "category": "国产剧", "confidence": 90}

        if lang in ("ja", "ko") or any(c in countries for c in ["JP", "KR"]):
            return {"media_type": "电视剧", "category": "日韩剧", "confidence": 90}

        return {"media_type": "电视剧", "category": "欧美剧", "confidence": 85}

    return {"media_type": "电视剧", "category": "未分类", "confidence": 30}


class TMDBClient:
    def __init__(self, api_key: str = "", language: str = "zh-CN"):
        self.api_key = api_key or ""
        self.language = language

    async def _get_genres(self, client):
        genres = {}
        for media in ("movie", "tv"):
            r = await client.get(
                f"https://api.themoviedb.org/3/genre/{media}/list",
                params={"api_key": self.api_key, "language": self.language}
            )
            if r.status_code == 200:
                for g in r.json().get("genres", []):
                    genres[g["id"]] = g["name"]
        return genres

    async def search_best(self, title: str) -> dict | None:
        if not self.api_key:
            return None

        query = clean_title(title)
        year = year_from_text(title)

        async with httpx.AsyncClient(timeout=15) as client:
            genres = await self._get_genres(client)

            params = {
                "api_key": self.api_key,
                "language": self.language,
                "query": query,
                "include_adult": "false"
            }
            if year:
                params["year"] = year

            r = await client.get("https://api.themoviedb.org/3/search/multi", params=params)
            if r.status_code != 200:
                return None

            results = [x for x in r.json().get("results", []) if x.get("media_type") in ("movie", "tv")]
            if not results:
                return None

            best = sorted(results, key=lambda x: x.get("popularity", 0), reverse=True)[0]

            genre_names = [genres.get(gid, str(gid)) for gid in best.get("genre_ids", [])]
            date = best.get("release_date") or best.get("first_air_date") or ""
            poster_path = best.get("poster_path") or ""

            data = {
                "tmdb_id": best.get("id"),
                "tmdb_title": best.get("title") or best.get("name") or "",
                "tmdb_original_title": best.get("original_title") or best.get("original_name") or "",
                "tmdb_year": date[:4] if date else "",
                "tmdb_overview": best.get("overview") or "",
                "tmdb_rating": best.get("vote_average") or 0,
                "tmdb_poster": TMDB_IMAGE_BASE + poster_path if poster_path else "",
                "media_type": best.get("media_type"),
                "original_language": best.get("original_language") or "",
                "origin_country": best.get("origin_country") or [],
                "genre_names": genre_names,
            }
            data.update(classify_tmdb(data, raw_title=title))
            return data
