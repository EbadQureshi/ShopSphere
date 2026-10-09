import re
from typing import Iterable

from app.models import Category, Product

CATEGORY_MAP = {
    "electronics": ("Electronics", "electronics"),
    "men's clothing": ("Men's Clothing", "mens-clothing"),
    "women's clothing": ("Women's Clothing", "womens-clothing"),
    "jewelery": ("Jewelry", "jewelry"),
}

PRODUCT_TYPE_RULES = (
    ("Backpacks & Bags", "backpacks", r"\bbackpacks?\b|\brucksacks?\b|\bluggage\b"),
    ("SSD Storage", "ssd-storage", r"\bssd\b|solid[- ]state"),
    ("Hard Drives", "hard-drives", r"hard drives?|hdd|external drives?"),
    ("LED Lighting", "led-lighting", r"\bled\b"),
    ("Headphones", "headphones", r"headphones?|headsets?|earbuds?"),
    ("Computer Monitors", "monitors", r"\bmonitors?\b|ultrawide|computer display|\bips\b.*display"),
    ("Smart Watches", "smart-watches", r"smart ?watch(?:es)?"),
    ("Smartphones", "smartphones", r"\bsmartphones?\b|\biphones?\b|\bgalaxy s\d+\b"),
    ("Tablets", "tablets", r"\btablets?\b|\bipad\b"),
    ("Laptops", "laptops", r"\blaptops?\b|notebooks?"),
    ("Cameras", "cameras", r"\bcameras?\b|camcorders?"),
    ("Keyboards", "keyboards", r"\bkeyboards?\b"),
    ("Computer Mice", "computer-mice", r"\bcomputer mice\b|\bmouse\b"),
    ("Printers", "printers", r"\bprinters?\b"),
    ("Televisions", "televisions", r"\btvs?\b|televisions?"),
    ("Gaming Consoles", "gaming-consoles", r"playstation|xbox|nintendo switch"),
    ("Sunglasses", "sunglasses", r"sunglasses"),
    ("Bracelets", "bracelets", r"bracelets?"),
    ("Earrings", "earrings", r"earrings?|pierced owl"),
    ("Necklaces", "necklaces", r"necklaces?|chains?"),
    ("Rings", "rings", r"\brings?\b|micropave|solitaire|engagement"),
)

TECH_CATEGORIES = {
    "electronics",
    "ssd-storage",
    "hard-drives",
    "led-lighting",
    "headphones",
    "monitors",
    "smart-watches",
    "smartphones",
    "tablets",
    "laptops",
    "cameras",
    "keyboards",
    "computer-mice",
    "printers",
    "televisions",
    "gaming-consoles",
}
JEWELRY_CATEGORIES = {"jewelry", "bracelets", "earrings", "necklaces", "rings"}
STOP_WORDS = {
    "and", "the", "for", "with", "from", "this", "that", "your", "you",
    "new", "best", "great", "premium", "classic", "casual", "style",
    "fit", "fits", "inch", "inches", "gb", "tb", "usb", "plus",
    "men", "mens", "man", "women", "womens", "woman",
    "product", "products",
}
SIMILARITY_ANCHORS = {
    "backpack", "boot", "bracelet", "camera", "coat", "console", "drive",
    "earring", "headphone", "jacket", "keyboard", "lamp", "laptop", "monitor",
    "mouse", "necklace", "printer", "ring", "shoe", "shirt", "sneaker",
    "slim", "smartphone", "ssd", "tablet", "television",
}


def product_category(source_category: str, name: str, description: str):
    source = source_category.strip().lower()
    searchable = f"{name} {description}".lower()

    for category_name, category_slug, pattern in PRODUCT_TYPE_RULES:
        if re.search(pattern, searchable):
            return category_name, category_slug

    if source in {"men's clothing", "mens-clothing"}:
        if re.search(r"\b(sneakers?|shoes|boots)\b", name, re.IGNORECASE):
            return "Men's Footwear", "mens-footwear"
        if re.search(r"\b(jackets?|coats?|hoodies?)\b", name, re.IGNORECASE):
            return "Men's Jackets", "mens-jackets"
        if re.search(
            r"\b(t-?shirts?|shirts?|tops?|short sleeve|boat neck|v[- ]?neck|sleeveless)\b",
            name,
            re.IGNORECASE,
        ):
            return "Men's Tops", "mens-tops"
        return CATEGORY_MAP["men's clothing"]

    if source in {"women's clothing", "womens-clothing"}:
        if re.search(r"\b(sneakers?|shoes|boots)\b", name, re.IGNORECASE):
            return "Women's Footwear", "womens-footwear"
        if re.search(r"\b(jackets?|coats?|hoodies?)\b", name, re.IGNORECASE):
            return "Women's Jackets", "womens-jackets"
        if re.search(
            r"\b(t-?shirts?|shirts?|tops?|short sleeve|boat neck|v[- ]?neck|sleeveless)\b",
            name,
            re.IGNORECASE,
        ):
            return "Women's Tops", "womens-tops"
        return CATEGORY_MAP["women's clothing"]

    if re.search(r"\b(sneakers?|shoes|boots)\b", name, re.IGNORECASE):
        return "Footwear", "footwear"

    if source == "jewelery":
        return CATEGORY_MAP["jewelery"]

    return CATEGORY_MAP.get(
        source,
        (source_category.title(), re.sub(r"[^a-z0-9]+", "-", source).strip("-")),
    )


def category_family(category_slug: str) -> str:
    if category_slug.startswith("mens-"):
        return "mens-clothing"
    if category_slug.startswith("womens-"):
        return "womens-clothing"
    if category_slug == "footwear":
        return "footwear"
    if category_slug in TECH_CATEGORIES:
        return "electronics"
    if category_slug in JEWELRY_CATEGORIES:
        return "jewelry"
    if category_slug in {"backpacks", "bags"}:
        return "bags"
    return category_slug


def _name_tokens(value: str) -> set[str]:
    tokens = set()
    for token in re.findall(r"[a-z0-9]+", value.lower()):
        if token.endswith("ies") and len(token) > 4:
            token = token[:-3] + "y"
        elif token.endswith("ches") and len(token) > 5:
            token = token[:-2]
        elif token.endswith("s") and not token.endswith("ss") and len(token) > 3:
            token = token[:-1]
        if len(token) > 2 and not token.isdigit() and token not in STOP_WORDS:
            tokens.add(token)
    return tokens


def rank_related_products(
    selected: Product,
    candidates: Iterable[Product],
    categories: dict[int, Category],
    limit: int = 6,
) -> list[Product]:
    selected_category = categories.get(selected.category_id) if selected.category_id else None
    if selected_category is None:
        return []

    selected_family = category_family(selected_category.slug)
    selected_tokens = _name_tokens(selected.name)
    ranked = []
    for candidate in candidates:
        if candidate.id == selected.id or candidate.category_id is None:
            continue
        category = categories.get(candidate.category_id)
        if category is None or category_family(category.slug) != selected_family:
            continue

        same_category = category.id == selected_category.id
        shared_tokens = selected_tokens & _name_tokens(candidate.name)
        if not same_category and not (
            shared_tokens & SIMILARITY_ANCHORS or len(shared_tokens) >= 2
        ):
            continue

        price_gap = abs(float(selected.price) - float(candidate.price))
        price_similarity = 1 / (1 + price_gap / max(float(selected.price), 1))
        ranked.append((
            (
                int(same_category),
                len(shared_tokens),
                int(candidate.stock > 0),
                price_similarity,
                int(candidate.is_featured),
                -candidate.id,
            ),
            candidate,
        ))

    ranked.sort(key=lambda item: item[0], reverse=True)
    return [product for _, product in ranked[:limit]]
