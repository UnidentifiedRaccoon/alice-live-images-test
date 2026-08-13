#!/usr/bin/env python3
"""Collect untouched PromoPages article originals.

The public article HTML embeds the editor state and the MDS image catalogue in
``window._data``.  The editor state is the source of truth for content order;
the catalogue is the source of truth for the ``orig`` URL and dimensions.
No displayed resize is ever used as a fallback for a missing original.

With no command-line overrides this still collects the original
PROMOPAGES-9857 dataset.  Other tickets can provide a JSON article list and a
single safe dataset prefix below the same output root.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Any, Iterable, Sequence

from PIL import Image


@dataclass(frozen=True)
class Article:
    number: int
    label: str
    folder: str
    url: str


ARTICLES = (
    Article(
        1,
        "Pharmocean — Магия магния",
        "01-pharmocean-magiia-magniia",
        "https://pharmocean.promo.page/media/"
        "magiia-magniia-68f5ff4f55f9e8662bdfb1d4_0_0",
    ),
    Article(
        2,
        "Nanoplast — Как унимать боль в суставах",
        "02-nanoplast-kak-unimat-bol",
        "https://nanoplast.promo.page/media/"
        "kak-unimat-bol-v-sustavah-sovety-pojilym-i-ne-tolko-"
        "68651c9aadaa5933d5c0ef41_0_0",
    ),
    Article(
        3,
        "ZOV — Решения для кухни",
        "03-zov-resheniia-dlia-kuhni",
        "https://zovofficial.promo.page/media/"
        "5-reshenii-dlia-kuhni-kotoraia-raduet-kajdyi-den-"
        "68c2d0acf583c90deb8abb8e_0_0",
    ),
    Article(
        4,
        "Graceface — Антивозрастная сыворотка",
        "04-graceface-antivozrastnaia-syvorotka",
        "https://graceface.promo.page/media/"
        "nashla-luchshuiu-antivozrastnuiu-syvorotku-za-smeshnye-dengi-"
        "682b55d20cfd5f4e6d52b586_0_0",
    ),
    Article(
        5,
        "Пятёрочка — Жалоба на магазин",
        "05-5ka-zhaloba-na-magazin",
        "https://5ka.promo.page/zabota/"
        "vot-chto-budet-esli-pojalovatsia-na-magazin-piaterochka-"
        "68aaa2155c24bb23a680ea99_0_0",
    ),
    Article(
        6,
        "Четыре лапы — Наполнитель для кошачьего туалета",
        "06-4lapy-koshachii-napolnitel",
        "https://4lapy.promo.page/media/"
        "kak-ubrat-zapah-koshachego-tualeta-vybiraem-napolnitel-"
        "6718c349d809026a62687d57_0_0",
    ),
    Article(
        7,
        "Аквадетрим — Дефицит витамина D",
        "07-aquadetrim-deficit-vitamina-d",
        "https://aquadetrim.promo.page/rzxno/"
        "deficit-vitamina-d-kratkii-cheklist-"
        "676433d3bd7a2a17f1c526c6_0_0",
    ),
    Article(
        8,
        "Точка — ООО или ИП",
        "08-tochka-ooo-ili-ip",
        "https://tochka.promo.page/media/"
        "3-situacii-kogda-nujno-otkryvat-ooo-a-ne-ip-"
        "619f4103009a9c67ed302d24_2_2",
    ),
    Article(
        9,
        "Остров мечты — Семейные выходные",
        "09-dream-island-semeinye-vyhodnye",
        "https://dreamisland.promo.page/media/"
        "kak-provesti-vyhodnye-semei-vybiraiu-ostrov-mechty-"
        "66fbec544897e5618d148b84_0_0",
    ),
    Article(
        10,
        "EXEED — Факты об EXEED RX",
        "10-exeed-rx",
        "https://exeed.promo.page/media/"
        "7-faktov-ob-exeed-rx-v-kotorom-produmany-vse-detali-"
        "6807aec162bbbf0750cbbaf0_0_0",
    ),
    Article(
        11,
        "O’STIN — Весенняя капсула",
        "11-ostin-vesenniaia-kapsula",
        "https://ostin.promo.page/media/"
        "cheklist-sobiraem-stilnuiu-vesenniuiu-kapsulu-v-ostin-"
        "6602c684a25fc4344f7e4264_0_0",
    ),
    Article(
        12,
        "Mars — Подарки на 8 Марта",
        "12-mars-podarki-na-8-marta",
        "https://mars.promo.page/media/"
        "20-variantov-podarkov-na-8-marta-dlia-samyh-raznyh-jenscin-"
        "67ab5ad5f48e856173fdbea2_9_1",
    ),
    Article(
        13,
        "ЖК «Ильинка 3/8» — Элитный ЖК напротив Кремля",
        "13-ilinka-elitnyi-zhk",
        "https://r1864.promo.page/media/"
        "pokazyvaem-chto-za-elitnyi-jk-stroiat-naprotiv-kremlia-"
        "648b2ca27e930436a8c7d0ff_6_4",
    ),
    Article(
        14,
        "MIUZ Diamonds — Модные серьги",
        "14-miuz-modnye-sergi",
        "https://miuz.promo.page/promo/"
        "top5-samyh-modnyh-serejek-etogo-sezona-"
        "64f3617597d2ee3498b5576a_3_2",
    ),
    Article(
        15,
        "Ozon — Грузоперевозки с предсказуемым доходом",
        "15-ozon-gruzoperevozki",
        "https://ozon.promo.page/media/"
        "gruzoperevozki-s-predskazuemym-dohodom-chto-da-"
        "698c849610b7882d19814653_0_0",
    ),
    Article(
        16,
        "Ekonika — Пять трендов сезона",
        "16-ekonika-letnie-trendy",
        "https://ekonika.promo.page/media/"
        "na-letnih-kanikulah-5-trendov-sezona-"
        "68122cd631af7c4297e554bd_0_0",
    ),
    Article(
        17,
        "Level Мичуринский — Трёхсторонняя квартира",
        "17-level-michurinskiy-kvartira",
        "https://level.promo.page/michurinskiy/"
        "trehstoronniaia-kvartira-unikalnyi-vid-iz-kajdoi-komnaty-"
        "689321d24ca9367d4afa0eff_0_0",
    ),
    Article(
        18,
        "Dalan — Правда и мифы о средствах для волос",
        "18-dalan-sredstva-dlia-volos",
        "https://dalan.promo.page/media/"
        "pravda-i-mify-o-tureckih-sredstvah-dlia-volos-"
        "68dd15f114a62125e8c2ea23_0_0",
    ),
    Article(
        19,
        "Level.Travel — Отпуск в Турции",
        "19-level-travel-otpusk-v-turcii",
        "https://level-travel.promo.page/media/"
        "planiruem-otpusk-v-turcii-5-laifhakov-ot-leveltravel-"
        "6819e3e1ea1b0b7bc375fe75_0_0",
    ),
    Article(
        20,
        "Сравни — Как повысить кредитный рейтинг",
        "20-sravni-kreditnyi-reiting",
        "https://sravni.promo.page/media/"
        "kak-povysit-kreditnyi-reiting-uznaite-na-sravni-"
        "65f160d13bba425fc5fa82cc_0_0",
    ),
    Article(
        21,
        "Марина Майер — Ваше золотое время после 35",
        "21-maier-doctor-zolotoe-vremia",
        "https://maier-doctor.promo.page/media/"
        "35-vashe-zolotoe-vremia-chtoby-sohranit-molodost-"
        "6a6328e396062011505ab621_0_0",
    ),
)

FORMAT_EXTENSIONS = {
    "JPEG": "jpeg",
    "JPG": "jpeg",
    "PNG": "png",
    "WEBP": "webp",
    "GIF": "gif",
    "AVIF": "avif",
}

GRAPHIC_PRIMARY_CLASS = "text_interface_collage"
GRAPHIC_KIND_VALUES = (
    "banner",
    "ui_screenshot",
    "floor_plan",
    "map",
    "table",
    "chart",
    "diagram",
    "text_document",
    "collage",
)


def _safe_path_component(value: str, field: str) -> str:
    """Return one traversal-safe relative path component."""

    if not isinstance(value, str) or not value:
        raise ValueError(f"{field} must be a non-empty string")
    if value in {".", ".."} or "/" in value or "\\" in value:
        raise ValueError(f"{field} must be one relative path component: {value!r}")
    if value != value.strip() or any(
        not (character.isalnum() or character in "._-") for character in value
    ):
        raise ValueError(f"{field} contains unsafe characters: {value!r}")
    return value


def normalize_dataset_prefix(value: str | None) -> str:
    """Validate an optional single-directory dataset namespace."""

    if value is None or value == "":
        return ""
    return _safe_path_component(value, "dataset prefix")


def load_articles(
    path: Path,
    exclude_article_numbers: Sequence[int] = (),
) -> tuple[Article, ...]:
    """Load and validate an external JSON array of article definitions."""

    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, list) or not value:
        raise ValueError(f"Article list must be a non-empty JSON array: {path}")

    articles: list[Article] = []
    for index, item in enumerate(value, 1):
        if not isinstance(item, dict):
            raise ValueError(f"Article {index} must be an object")
        number = item.get("number")
        if isinstance(number, bool) or not isinstance(number, int) or number < 1:
            raise ValueError(f"Article {index} number must be a positive integer")
        label = item.get("label")
        url = item.get("url")
        if not isinstance(label, str) or not label.strip():
            raise ValueError(f"Article {index} label must be a non-empty string")
        if not isinstance(url, str) or not url.strip():
            raise ValueError(f"Article {index} url must be a non-empty string")
        folder = _safe_path_component(item.get("folder"), f"article {index} folder")
        articles.append(Article(number, label, folder, url))

    articles.sort(key=lambda article: article.number)
    numbers = [article.number for article in articles]
    if len(numbers) != len(set(numbers)):
        raise ValueError(f"Article numbers must be unique: {numbers}")
    folders = [article.folder for article in articles]
    if len(folders) != len(set(folders)):
        raise ValueError("Article folders must be unique")

    exclusions = list(exclude_article_numbers)
    if any(
        isinstance(number, bool) or not isinstance(number, int) or number < 1
        for number in exclusions
    ):
        raise ValueError("Excluded article numbers must be positive integers")
    if len(exclusions) != len(set(exclusions)):
        raise ValueError("Excluded article numbers must be unique")
    missing_exclusions = sorted(set(exclusions) - set(numbers))
    if missing_exclusions:
        raise ValueError(
            "Excluded article numbers are absent from the article list: "
            f"{missing_exclusions}"
        )
    filtered = [article for article in articles if article.number not in exclusions]
    if not filtered:
        raise ValueError("Article exclusions removed every article")
    return tuple(filtered)


MANIFEST_FIELDS = (
    "article_number",
    "article_label",
    "article_url",
    "image_number",
    "image_role",
    "block_index",
    "gallery_index",
    "image_id",
    "page_variant_url",
    "orig_url",
    "file_path",
    "orig_format",
    "orig_width",
    "orig_height",
    "actual_format",
    "actual_width",
    "actual_height",
    "byte_size",
    "sha256",
    "download_status",
    "exception_note",
    "duplicate_of",
    "primary_class",
    "graphic_kind",
    "graphic_kinds",
    "scene_tags",
    "scene_description",
    "motion_cues",
    "risk_notes",
)


def fetch(url: str, retries: int = 3) -> tuple[bytes, str, str]:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 PromoPagesDataset/1.0"
            ),
            "Accept-Encoding": "identity",
        },
    )
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(request, timeout=90) as response:
                content_type = response.headers.get_content_type()
                return response.read(), content_type, response.geturl()
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            last_error = error
            if attempt + 1 < retries:
                time.sleep(1.5 * (attempt + 1))
    assert last_error is not None
    raise last_error


def extract_page_data(html: bytes) -> dict[str, Any]:
    text = html.decode("utf-8")
    marker = "w._data = "
    start = text.find(marker)
    if start < 0:
        raise ValueError("window._data marker is missing")
    data, _ = json.JSONDecoder().raw_decode(text, start + len(marker))
    if not isinstance(data, dict):
        raise ValueError("window._data is not a JSON object")
    return data


def image_occurrences(page_data: dict[str, Any]) -> list[dict[str, Any]]:
    publication = page_data["publication"]
    occurrences: list[dict[str, Any]] = []

    head_image = publication.get("headImage") or {}
    desktop = head_image.get("imageDesktop") or {}
    mobile = head_image.get("imageMobile") or {}
    design = head_image.get("design") or {}
    cover_disabled = isinstance(design, dict) and design.get("id") == "0"
    if not cover_disabled and desktop.get("id"):
        occurrences.append(
            {
                "image_id": desktop["id"],
                "role": "cover",
                "block_index": "",
                "gallery_index": "",
            }
        )
    if (
        not cover_disabled
        and mobile.get("id")
        and mobile.get("id") != desktop.get("id")
    ):
        occurrences.append(
            {
                "image_id": mobile["id"],
                "role": "cover_mobile",
                "block_index": "",
                "gallery_index": "",
            }
        )

    content_state = json.loads(
        publication["content"]["articleContent"]["contentState"]
    )["draftJsState"]
    for block_index, block in enumerate(content_state["blocks"]):
        if not block.get("type", "").startswith("atomic:image"):
            continue
        block_data = block.get("data") or {}
        if "images" in block_data:
            image_refs = block_data["images"]
            role = "gallery_image"
            if not isinstance(image_refs, list) or not image_refs:
                raise ValueError(
                    f"atomic image gallery at block {block_index} has no images"
                )
        else:
            image_ref = block_data.get("image")
            if not isinstance(image_ref, dict) or not image_ref.get("id"):
                raise ValueError(
                    f"atomic image at block {block_index} has no valid image"
                )
            image_refs = [image_ref]
            role = "article_image"
        for gallery_index, image_ref in enumerate(image_refs):
            if not isinstance(image_ref, dict) or not image_ref.get("id"):
                raise ValueError(
                    "atomic image reference has no id: "
                    f"block={block_index}, gallery_index={gallery_index}"
                )
            occurrences.append(
                {
                    "image_id": image_ref["id"],
                    "role": role,
                    "block_index": block_index,
                    "gallery_index": gallery_index if role == "gallery_image" else "",
                }
            )
    return occurrences


def image_urls(image_meta: dict[str, Any]) -> tuple[str, str]:
    base = (
        "https://avatars.mds.yandex.net/"
        f"get-{image_meta['namespace']}/{image_meta['groupId']}/"
        f"{image_meta['imageName']}"
    )
    sizes = image_meta.get("sizes") or {}
    preferred_sizes = (
        "scale_1200",
        "scale_2400",
        "scale_720",
        "scale_600",
        "post_crop_big_1080",
    )
    page_size = next((size for size in preferred_sizes if size in sizes), None)
    if page_size is None:
        page_size = next((size for size in sizes if size != "orig"), "orig")
    return f"{base}/{page_size}", f"{base}/orig"


def inspect_image(payload: bytes) -> tuple[str, int, int, str]:
    digest = hashlib.sha256(payload).hexdigest()
    with Image.open(BytesIO(payload)) as image:
        actual_format = (image.format or "").upper()
        width, height = image.size
        image.verify()
    return actual_format, width, height, digest


def load_annotations(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Annotations must be an object: {path}")
    invalid_ids = [
        image_id
        for image_id, annotation in value.items()
        if not isinstance(annotation, dict)
    ]
    if invalid_ids:
        raise ValueError(f"Annotations must contain objects: {invalid_ids}")
    return value


def serialize_graphic_routing(annotation: dict[str, Any]) -> tuple[str, str]:
    primary_class = annotation.get("primary_class")
    active_kind = annotation.get("graphic_kind", "")
    kinds = annotation.get("graphic_kinds", [])

    if not annotation:
        return "", ""
    if primary_class != GRAPHIC_PRIMARY_CLASS:
        if active_kind or kinds:
            raise ValueError(
                "graphic routing is only valid for "
                f"{GRAPHIC_PRIMARY_CLASS}, got {primary_class!r}"
            )
        return "", ""
    if not isinstance(active_kind, str) or not active_kind:
        raise ValueError("text_interface_collage annotation has no graphic_kind")
    if not isinstance(kinds, list) or not kinds:
        raise ValueError("text_interface_collage annotation has no graphic_kinds")
    if any(not isinstance(kind, str) or not kind for kind in kinds):
        raise ValueError("graphic_kinds must contain non-empty strings")
    if len(kinds) != len(set(kinds)):
        raise ValueError("graphic_kinds contains duplicates")
    unknown = [kind for kind in kinds if kind not in GRAPHIC_KIND_VALUES]
    if unknown or active_kind not in GRAPHIC_KIND_VALUES:
        raise ValueError(
            f"unknown graphic routing: active={active_kind!r}, kinds={unknown}"
        )
    if kinds[0] != active_kind:
        raise ValueError("active graphic_kind must be first in graphic_kinds")
    return active_kind, "; ".join(kinds)


def collect(
    output_root: Path,
    annotations_path: Path,
    *,
    articles: Iterable[Article] = ARTICLES,
    dataset_prefix: str = "",
) -> list[dict[str, Any]]:
    dataset_prefix = normalize_dataset_prefix(dataset_prefix)
    articles = tuple(articles)
    if not articles:
        raise ValueError("Article collection must not be empty")
    article_numbers = [article.number for article in articles]
    if any(
        isinstance(number, bool) or not isinstance(number, int) or number < 1
        for number in article_numbers
    ):
        raise ValueError("Article numbers must be positive integers")
    if len(article_numbers) != len(set(article_numbers)):
        raise ValueError(f"Article numbers must be unique: {article_numbers}")
    article_folders = [
        _safe_path_component(article.folder, "article folder") for article in articles
    ]
    if len(article_folders) != len(set(article_folders)):
        raise ValueError("Article folders must be unique")
    relative_articles_root = (
        Path(dataset_prefix) / "articles" if dataset_prefix else Path("articles")
    )
    articles_root = output_root / relative_articles_root
    articles_root.mkdir(parents=True, exist_ok=True)
    annotations = load_annotations(annotations_path)
    rows: list[dict[str, Any]] = []
    downloaded: dict[str, dict[str, Any]] = {}
    first_occurrence: dict[str, str] = {}

    for article in articles:
        print(
            f"[{article.number:02d}/{len(articles):02d}] {article.label}",
            flush=True,
        )
        page_html, _, _ = fetch(article.url)
        page_data = extract_page_data(page_html)
        image_catalogue = page_data.get("images") or {}
        occurrences = image_occurrences(page_data)
        article_dir = articles_root / article.folder
        article_dir.mkdir(parents=True, exist_ok=True)

        for image_number, occurrence in enumerate(occurrences, 1):
            image_id = occurrence["image_id"]
            image_meta = image_catalogue.get(image_id)
            annotation = annotations.get(image_id, {})
            graphic_kind, graphic_kinds = serialize_graphic_routing(annotation)
            row: dict[str, Any] = {
                "article_number": f"{article.number:02d}",
                "article_label": article.label,
                "article_url": article.url,
                "image_number": f"{image_number:02d}",
                "image_role": occurrence["role"],
                "block_index": occurrence["block_index"],
                "gallery_index": occurrence["gallery_index"],
                "image_id": image_id,
                "page_variant_url": "",
                "orig_url": "",
                "file_path": "",
                "orig_format": "",
                "orig_width": "",
                "orig_height": "",
                "actual_format": "",
                "actual_width": "",
                "actual_height": "",
                "byte_size": "",
                "sha256": "",
                "download_status": "orig_unavailable",
                "exception_note": "",
                "duplicate_of": first_occurrence.get(image_id, ""),
                "primary_class": annotation.get("primary_class", ""),
                "graphic_kind": graphic_kind,
                "graphic_kinds": graphic_kinds,
                "scene_tags": annotation.get("scene_tags", ""),
                "scene_description": annotation.get("scene_description", ""),
                "motion_cues": annotation.get("motion_cues", ""),
                "risk_notes": annotation.get("risk_notes", ""),
            }
            occurrence_key = f"{article.number:02d}/{image_number:02d}"
            first_occurrence.setdefault(image_id, occurrence_key)

            if image_meta is None:
                row["exception_note"] = "image metadata is missing from page catalogue"
                rows.append(row)
                continue

            declared_format = str((image_meta.get("meta") or {}).get("origFormat", ""))
            extension = FORMAT_EXTENSIONS.get(declared_format.upper())
            orig_size = (image_meta.get("sizes") or {}).get("orig") or {}
            page_url, orig_url = image_urls(image_meta)
            row.update(
                {
                    "page_variant_url": page_url,
                    "orig_url": orig_url,
                    "orig_format": declared_format.upper(),
                    "orig_width": orig_size.get("width", ""),
                    "orig_height": orig_size.get("height", ""),
                }
            )
            if extension is None:
                row["exception_note"] = f"unsupported orig format: {declared_format!r}"
                rows.append(row)
                continue

            relative_path = (
                relative_articles_root
                / article.folder
                / f"{image_number:02d}.{extension}"
            )
            target_path = output_root / relative_path
            row["file_path"] = relative_path.as_posix()

            try:
                if orig_url in downloaded:
                    source = Path(downloaded[orig_url]["path"])
                    shutil.copyfile(source, target_path)
                    payload = target_path.read_bytes()
                    content_type = downloaded[orig_url]["content_type"]
                else:
                    payload, content_type, _ = fetch(orig_url)
                    target_path.write_bytes(payload)
                    downloaded[orig_url] = {
                        "path": str(target_path),
                        "content_type": content_type,
                    }
                actual_format, width, height, digest = inspect_image(payload)
                expected_format = "JPEG" if declared_format.upper() == "JPG" else declared_format.upper()
                if actual_format != expected_format:
                    raise ValueError(
                        f"format mismatch: metadata={expected_format}, file={actual_format}, "
                        f"content-type={content_type}"
                    )
                if (width, height) != (
                    orig_size.get("width"),
                    orig_size.get("height"),
                ):
                    raise ValueError(
                        "dimension mismatch: "
                        f"metadata={orig_size.get('width')}x{orig_size.get('height')}, "
                        f"file={width}x{height}"
                    )
                row.update(
                    {
                        "actual_format": actual_format,
                        "actual_width": width,
                        "actual_height": height,
                        "byte_size": len(payload),
                        "sha256": digest,
                        "download_status": "ok",
                    }
                )
            except Exception as error:  # Keep the exception in the manifest; never use a resize.
                if target_path.exists():
                    target_path.unlink()
                row["file_path"] = ""
                row["exception_note"] = f"{type(error).__name__}: {error}"
            rows.append(row)

    manifest_path = articles_root / "manifest.csv"
    with manifest_path.open("w", encoding="utf-8", newline="") as output:
        writer = csv.DictWriter(
            output,
            fieldnames=MANIFEST_FIELDS,
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path("PROMOPAGES-9857"),
        help="Directory that will contain articles/ (default: PROMOPAGES-9857)",
    )
    parser.add_argument(
        "--annotations",
        type=Path,
        default=Path("PROMOPAGES-9857/classifications.json"),
        help="Optional image-id keyed classification JSON",
    )
    parser.add_argument(
        "--articles",
        "--articles-json",
        dest="articles_path",
        type=Path,
        help=(
            "JSON array of article objects with number, label, folder, and url; "
            "defaults to the built-in PROMOPAGES-9857 list"
        ),
    )
    parser.add_argument(
        "--dataset-prefix",
        default="",
        help=(
            "Optional safe directory name below --output-root, for example "
            "PROMOPAGES-10060"
        ),
    )
    parser.add_argument(
        "--exclude-article-number",
        type=int,
        action="append",
        default=[],
        help=(
            "Article number to omit from an external list without renumbering; "
            "repeat for multiple exclusions"
        ),
    )
    args = parser.parse_args()
    if args.exclude_article_number and not args.articles_path:
        parser.error("--exclude-article-number requires --articles")
    articles = (
        load_articles(args.articles_path, args.exclude_article_number)
        if args.articles_path
        else ARTICLES
    )
    dataset_prefix = normalize_dataset_prefix(args.dataset_prefix)
    rows = collect(
        args.output_root,
        args.annotations,
        articles=articles,
        dataset_prefix=dataset_prefix,
    )
    ok = sum(row["download_status"] == "ok" for row in rows)
    exceptions = len(rows) - ok
    print(
        f"Collected {ok}/{len(rows)} image occurrences; "
        f"orig exceptions: {exceptions}; "
        "manifest: "
        f"{args.output_root / dataset_prefix / 'articles' / 'manifest.csv'}"
    )
    return 0 if exceptions == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
