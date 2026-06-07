from __future__ import annotations

import base64
import hashlib
import html
import json
import re
import shutil
import subprocess
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from PIL import Image, ImageDraw, ImageFont, UnidentifiedImageError


USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125 Safari/537.36"
BING_IMAGES_URL = "https://www.bing.com/images/search"
WIKIMEDIA_API = "https://commons.wikimedia.org/w/api.php"
DEFAULT_CACHE_DIR = Path.home() / ".vectorcraft_py" / "asset_cache"
_TAG_RE = re.compile(r"<[^>]+>")
_BING_ITEM_RE = re.compile(r'class="iusc"[^>]+m="([^"]+)"')
_SUPPORTED_RASTER_MIMES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
_SUPPORTED_VECTOR_MIMES = {"image/svg+xml"}
_BING_GRAPHIC_SUFFIX = "图标 矢量 示意图 透明 png icon vector illustration diagram transparent png"
_CJK_GRAPHIC_TERMS = (
    ("流程图", "flowchart"),
    ("流程", "flowchart"),
    ("树形图", "tree diagram"),
    ("树形", "tree diagram"),
    ("组织结构", "organization chart"),
    ("组织", "organization chart"),
    ("电路", "circuit diagram"),
    ("数据库", "database icon"),
    ("坐标", "coordinate system"),
    ("三维", "3d geometry"),
    ("示意", "diagram"),
    ("图标", "icon"),
    ("矢量", "vector"),
    ("箭头", "arrow"),
    ("矩形", "rectangle"),
    ("圆形", "circle"),
    ("圆", "circle"),
    ("椭圆", "ellipse"),
    ("菱形", "diamond"),
    ("三角", "triangle"),
    ("文档", "document icon"),
    ("开始", "start icon"),
    ("结束", "end icon"),
    ("树", "tree"),
)


@dataclass(frozen=True)
class AssetResult:
    title: str
    image_url: str
    thumb_url: str
    page_url: str
    source: str = "在线图形库"
    license: str = ""
    author: str = ""
    mime: str = ""
    width: int = 0
    height: int = 0


@dataclass(frozen=True)
class CachedAsset:
    path: Path
    data: str
    mime: str
    width: int
    height: int


def search_assets(query: str, limit: int = 18, timeout: float = 6.0) -> list[AssetResult]:
    query = query.strip()
    if not query:
        return []

    search_query = _expand_graphic_query(query)
    searchers = (
        (_search_bing_graphics, _search_wikimedia_graphics)
        if _contains_cjk(search_query)
        else (_search_wikimedia_graphics, _search_bing_graphics)
    )
    for searcher in searchers:
        try:
            results = searcher(search_query, limit=limit, timeout=timeout)
        except Exception:
            results = []
        if results:
            return results
    return []


def load_thumbnail(result: AssetResult, size: tuple[int, int] = (168, 112), timeout: float = 5.0) -> Image.Image:
    cache_dir = DEFAULT_CACHE_DIR / "thumbs"
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = cache_dir / f"{_url_hash(result.thumb_url or result.image_url)}.png"
    if cache_path.exists():
        return Image.open(cache_path).convert("RGBA")

    raw = _fetch_bytes(result.thumb_url or result.image_url, timeout=timeout, max_bytes=4_000_000)
    image = Image.open(BytesIO(raw)).convert("RGBA")
    thumb = _letterbox(image, size)
    thumb.save(cache_path, "PNG", optimize=True)
    return thumb


def placeholder_thumbnail(title: str, size: tuple[int, int] = (168, 112)) -> Image.Image:
    image = Image.new("RGBA", size, (241, 245, 249, 255))
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, size[0] - 1, size[1] - 1), outline=(148, 163, 184, 255), width=1)
    text = (title or "No preview")[:12]
    try:
        font = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 18)
    except Exception:
        font = ImageFont.load_default()
    box = draw.textbbox((0, 0), text, font=font)
    draw.text(((size[0] - (box[2] - box[0])) / 2, (size[1] - (box[3] - box[1])) / 2), text, fill=(71, 85, 105), font=font)
    return image


def download_asset(
    result: AssetResult,
    cache_dir: Path | None = None,
    max_size: tuple[int, int] = (1200, 1200),
    timeout: float = 8.0,
) -> CachedAsset:
    cache_dir = cache_dir or DEFAULT_CACHE_DIR / "images"
    cache_dir.mkdir(parents=True, exist_ok=True)
    urls = [url for url in [result.thumb_url, result.image_url] if url]
    errors: list[str] = []

    for download_url in urls:
        try:
            raw = _fetch_bytes(download_url, timeout=timeout, max_bytes=10_000_000)
            return _cache_image(raw, download_url, result.mime, cache_dir, max_size)
        except Exception as exc:
            errors.append(str(exc))
            continue
    raise RuntimeError(errors[-1] if errors else "图形下载失败")


def _search_bing_graphics(query: str, limit: int, timeout: float) -> list[AssetResult]:
    params = {"q": f"{query} {_BING_GRAPHIC_SUFFIX}", "form": "HDRSC2", "first": "1", "tsc": "ImageBasicHover"}
    raw = _fetch_bytes(f"{BING_IMAGES_URL}?{urlencode(params)}", timeout=timeout, max_bytes=1_500_000)
    text = raw.decode("utf-8", errors="ignore")
    results: list[AssetResult] = []
    seen: set[str] = set()
    for match in _BING_ITEM_RE.finditer(text):
        try:
            item = json.loads(html.unescape(match.group(1)))
        except json.JSONDecodeError:
            continue
        image_url = item.get("murl", "")
        thumb_url = item.get("turl", "") or image_url
        if not image_url or not thumb_url or image_url in seen:
            continue
        if _looks_like_svg(image_url) or _looks_like_svg(thumb_url):
            continue
        seen.add(image_url)
        title = html.unescape(item.get("t") or item.get("desc") or query).strip()
        results.append(
            AssetResult(
                title=title,
                image_url=image_url,
                thumb_url=thumb_url,
                page_url=item.get("purl", ""),
                source="Bing 图形搜索",
                mime=_mime_from_url(image_url),
            )
        )
        if len(results) >= limit:
            break
    return results


def _search_wikimedia_graphics(query: str, limit: int, timeout: float) -> list[AssetResult]:
    search_terms = [
        f"{query} filetype:svg",
        f"{query} icon filetype:svg",
        f"{query} diagram filetype:svg",
        f"{query} clipart filetype:svg",
    ]
    results: list[AssetResult] = []
    seen: set[str] = set()

    for term in search_terms:
        for result in _search_wikimedia(term, limit=limit, timeout=timeout):
            key = result.page_url or result.image_url
            if key in seen:
                continue
            seen.add(key)
            results.append(result)
            if len(results) >= limit:
                return results
    return results


def _search_wikimedia(search_term: str, limit: int, timeout: float) -> list[AssetResult]:
    params = {
        "action": "query",
        "generator": "search",
        "gsrsearch": search_term,
        "gsrnamespace": "6",
        "gsrlimit": str(max(limit * 2, limit)),
        "prop": "imageinfo",
        "iiprop": "url|mime|size|extmetadata",
        "iiurlwidth": "900",
        "format": "json",
        "formatversion": "2",
        "origin": "*",
    }
    payload = _fetch_json(f"{WIKIMEDIA_API}?{urlencode(params)}", timeout=timeout)
    pages = sorted(payload.get("query", {}).get("pages", []), key=lambda page: page.get("index", 9999))

    results: list[AssetResult] = []
    for page in pages:
        info_items = page.get("imageinfo") or []
        if not info_items:
            continue
        info = info_items[0]
        mime = info.get("mime", "")
        original_url = info.get("url", "")
        thumb_url = info.get("thumburl") or ""
        if mime in _SUPPORTED_VECTOR_MIMES:
            if not thumb_url:
                continue
            image_url = thumb_url
            asset_mime = "image/png"
        elif mime in _SUPPORTED_RASTER_MIMES:
            if not original_url or _looks_like_svg(original_url):
                continue
            image_url = original_url
            thumb_url = thumb_url or image_url
            asset_mime = mime
        else:
            continue
        if not image_url:
            continue
        meta = info.get("extmetadata") or {}
        title = page.get("title", "").replace("File:", "", 1)
        results.append(
            AssetResult(
                title=title,
                image_url=image_url,
                thumb_url=thumb_url,
                page_url=info.get("descriptionurl", ""),
                source="Wikimedia Commons 图形库",
                license=_metadata_value(meta, "LicenseShortName") or _metadata_value(meta, "UsageTerms"),
                author=_metadata_value(meta, "Artist") or _metadata_value(meta, "Credit"),
                mime=asset_mime,
                width=int(info.get("thumbwidth") or info.get("width") or 0),
                height=int(info.get("thumbheight") or info.get("height") or 0),
            )
        )
        if len(results) >= limit:
            break
    return results


def _cache_image(raw: bytes, download_url: str, declared_mime: str, cache_dir: Path, max_size: tuple[int, int]) -> CachedAsset:
    try:
        source = Image.open(BytesIO(raw))
        source.load()
    except UnidentifiedImageError as exc:
        raise RuntimeError("无法识别下载的图形文件格式") from exc

    source.thumbnail(max_size, Image.Resampling.LANCZOS)
    image_rgba = source.convert("RGBA")
    has_alpha = image_rgba.getchannel("A").getextrema()[0] < 255

    digest = hashlib.sha256(raw + download_url.encode("utf-8", errors="ignore")).hexdigest()[:24]
    if has_alpha or declared_mime == "image/png":
        path = cache_dir / f"{digest}.png"
        image_rgba.save(path, "PNG", optimize=True)
        mime = "image/png"
    else:
        path = cache_dir / f"{digest}.jpg"
        image_rgba.convert("RGB").save(path, "JPEG", quality=86, optimize=True)
        mime = "image/jpeg"

    data = base64.b64encode(path.read_bytes()).decode("ascii")
    with Image.open(path) as saved:
        width, height = saved.size
    return CachedAsset(path=path, data=data, mime=mime, width=width, height=height)


def _letterbox(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    image.thumbnail(size, Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", size, (255, 255, 255, 255))
    x = (size[0] - image.width) // 2
    y = (size[1] - image.height) // 2
    canvas.alpha_composite(image, (x, y))
    return canvas


def _fetch_json(url: str, timeout: float) -> dict:
    raw = _fetch_bytes(url, timeout=timeout, max_bytes=3_000_000)
    return json.loads(raw.decode("utf-8"))


def _fetch_bytes(url: str, timeout: float, max_bytes: int) -> bytes:
    request = Request(url, headers={"User-Agent": USER_AGENT, "Referer": _referer_for(url)})
    try:
        with urlopen(request, timeout=timeout) as response:
            data = response.read(max_bytes + 1)
    except (TimeoutError, URLError, OSError):
        data = _fetch_bytes_with_curl(url, timeout, max_bytes)
    if len(data) > max_bytes:
        raise RuntimeError("下载的图形过大")
    return data


def _fetch_bytes_with_curl(url: str, timeout: float, max_bytes: int) -> bytes:
    curl = shutil.which("curl.exe") or shutil.which("curl")
    if not curl:
        raise RuntimeError("网络请求失败，且找不到 curl 兜底下载工具")
    command = [
        curl,
        "-L",
        "--silent",
        "--show-error",
        "--max-time",
        str(max(3, int(timeout))),
        "--header",
        f"User-Agent: {USER_AGENT}",
        "--header",
        f"Referer: {_referer_for(url)}",
        url,
    ]
    completed = subprocess.run(command, capture_output=True, check=False, timeout=timeout + 3)
    if completed.returncode != 0:
        message = completed.stderr.decode("utf-8", errors="ignore").strip() or "网络请求失败"
        raise RuntimeError(message)
    if len(completed.stdout) > max_bytes:
        raise RuntimeError("下载的图形过大")
    return completed.stdout


def _metadata_value(metadata: dict, key: str) -> str:
    item = metadata.get(key) or {}
    value = item.get("value", "") if isinstance(item, dict) else ""
    value = html.unescape(_TAG_RE.sub("", value)).strip()
    return " ".join(value.split())


def _looks_like_svg(url: str) -> bool:
    return ".svg" in url.lower()


def _mime_from_url(url: str) -> str:
    lower = url.lower().split("?", 1)[0]
    if lower.endswith(".png"):
        return "image/png"
    if lower.endswith(".webp"):
        return "image/webp"
    if lower.endswith(".gif"):
        return "image/gif"
    return "image/jpeg"


def _referer_for(url: str) -> str:
    lower = url.lower()
    if "bing.com" in lower:
        return "https://www.bing.com/"
    if "wikimedia.org" in lower or "wikipedia.org" in lower:
        return "https://commons.wikimedia.org/"
    return "https://commons.wikimedia.org/"


def _contains_cjk(text: str) -> bool:
    return any("\u4e00" <= char <= "\u9fff" for char in text)


def _expand_graphic_query(query: str) -> str:
    if not _contains_cjk(query):
        return query
    hints: list[str] = []
    for needle, term in _CJK_GRAPHIC_TERMS:
        if needle in query and term not in hints:
            hints.append(term)
    return " ".join(hints) if hints else query


def _url_hash(url: str) -> str:
    return hashlib.sha256(url.encode("utf-8", errors="ignore")).hexdigest()[:24]
