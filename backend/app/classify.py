import re

CATEGORIES = [
    "动画电影",
    "华语电影",
    "外语电影",
    "国产剧",
    "欧美剧",
    "日韩剧",
    "国漫",
    "日番",
    "纪录片",
    "儿童",
    "综艺",
    "未分类",
]

MOVIE_CATEGORIES = ["动画电影", "华语电影", "外语电影"]
TV_CATEGORIES = ["国产剧", "欧美剧", "日韩剧", "国漫", "日番", "纪录片", "儿童", "综艺", "未分类"]


def _text(value: str) -> str:
    return (value or "").lower()


def classify_resource(title: str = "", note: str = "", source: str = "") -> dict:
    raw = f"{title} {note} {source}"
    text = _text(raw)

    is_tv = bool(re.search(r"(s\d{1,2}|第\s*\d+\s*[集季]|全\s*\d+\s*集|ep\s*\d+|e\d{1,3}|season|complete series)", text))
    is_movie = bool(re.search(r"(电影|4k|remux|bdrip|bluray|web-dl|hdr|2160p|1080p|蓝光|原盘|\(19\d{2}\)|\(20\d{2}\)|（19\d{2}）|（20\d{2}）)", text))

    # 明确电影关键词优先
    known_cn_movies = ["流浪地球", "长津湖", "满江红", "红海行动", "唐人街探案", "哪吒", "封神", "战狼"]
    if any(k in text for k in known_cn_movies):
        return {"media_type": "电影", "category": "华语电影", "confidence": 90}

    if any(k in text for k in ["纪录片", "documentary", "docu"]):
        return {"media_type": "电视剧", "category": "纪录片", "confidence": 90}

    if any(k in text for k in ["综艺", "真人秀", "脱口秀", "晚会", "演唱会", "variety"]):
        return {"media_type": "电视剧", "category": "综艺", "confidence": 85}

    if any(k in text for k in ["儿童", "少儿", "亲子", "kids", "kid"]):
        return {"media_type": "电视剧", "category": "儿童", "confidence": 80}

    if any(k in text for k in ["国漫", "国产动画", "中国动画"]):
        return {"media_type": "电视剧", "category": "国漫", "confidence": 85}

    if any(k in text for k in ["日番", "新番", "日本动画", "anime", "bangumi"]):
        return {"media_type": "电视剧", "category": "日番", "confidence": 85}

    if any(k in text for k in ["剧场版", "动画电影", "动漫电影"]):
        return {"media_type": "电影", "category": "动画电影", "confidence": 85}

    if any(k in text for k in ["美剧", "英剧", "欧美剧", "netflix", "hbo", "disney", "prime video"]):
        return {"media_type": "电视剧", "category": "欧美剧", "confidence": 85}

    if any(k in text for k in ["韩剧", "日剧", "日韩剧", "韩国剧", "日本剧"]):
        return {"media_type": "电视剧", "category": "日韩剧", "confidence": 85}

    if any(k in text for k in ["国产剧", "大陆剧", "内地剧", "华语剧"]):
        return {"media_type": "电视剧", "category": "国产剧", "confidence": 85}

    if is_tv:
        if any(k in text for k in ["大陆", "内地", "国语", "国产", "中国"]):
            return {"media_type": "电视剧", "category": "国产剧", "confidence": 70}
        if any(k in text for k in ["韩国", "日本", "日语", "韩语"]):
            return {"media_type": "电视剧", "category": "日韩剧", "confidence": 70}
        if any(k in text for k in ["美国", "英国", "英语", "欧美"]):
            return {"media_type": "电视剧", "category": "欧美剧", "confidence": 70}
        return {"media_type": "电视剧", "category": "未分类", "confidence": 50}

    if any(k in text for k in ["动画", "动漫", "cartoon", "animation"]):
        return {"media_type": "电影", "category": "动画电影", "confidence": 70}

    if is_movie:
        if any(k in text for k in ["国语", "华语", "大陆", "内地", "中国", "香港", "台湾", "粤语"]):
            return {"media_type": "电影", "category": "华语电影", "confidence": 70}
        return {"media_type": "电影", "category": "外语电影", "confidence": 60}

    return {"media_type": "电视剧", "category": "未分类", "confidence": 30}
