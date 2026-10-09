import json
import re
from decimal import Decimal
from urllib.error import URLError
from urllib.request import Request, urlopen

from slugify import slugify

from app.db.session import SessionLocal
from app.models import User, Category, Product, Cart
from app.core.security import hash_password
from app.recommendations import product_category

FAKE_STORE_PRODUCTS_URL = "https://fakestoreapi.com/products"
DUMMYJSON_LED_SEARCH_URL = "https://dummyjson.com/products/search?q=LED&limit=100"


def category_id_for(db, categories, source_category, name, description):
    category_name, category_slug = product_category(source_category, name, description)
    if category_slug not in categories:
        category = db.query(Category).filter_by(slug=category_slug).first()
        if not category:
            category = Category(name=category_name, slug=category_slug)
            db.add(category)
            db.flush()
        categories[category_slug] = category
    return categories[category_slug].id


def reclassify_existing_products():
    with SessionLocal() as db:
        categories = {}
        products = db.query(Product, Category).join(
            Category, Product.category_id == Category.id
        ).all()
        for product, category in products:
            source_category = category.slug
            if source_category.startswith("mens-"):
                source_category = "men's clothing"
            elif source_category.startswith("womens-"):
                source_category = "women's clothing"
            elif source_category == "accessories" and product.slug.startswith("fakestore-"):
                source_category = "jewelery"

            product.category_id = category_id_for(
                db,
                categories,
                source_category,
                product.name,
                product.description,
            )
        db.commit()
        return len(products)


def fetch_products():
    request = Request(FAKE_STORE_PRODUCTS_URL, headers={"User-Agent": "ShopSphere/1.0"})
    try:
        with urlopen(request, timeout=20) as response:
            products = json.load(response)
    except (URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Could not fetch product data from {FAKE_STORE_PRODUCTS_URL}") from exc
    if not isinstance(products, list):
        raise RuntimeError("Fake Store API returned an invalid product list")
    return products


def fetch_led_products():
    request = Request(DUMMYJSON_LED_SEARCH_URL, headers={"User-Agent": "ShopSphere/1.0"})
    try:
        with urlopen(request, timeout=20) as response:
            payload = json.load(response)
    except (URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Could not fetch LED product data from {DUMMYJSON_LED_SEARCH_URL}") from exc
    products = payload.get("products") if isinstance(payload, dict) else None
    if not isinstance(products, list):
        raise RuntimeError("DummyJSON returned an invalid product list")
    return [
        item for item in products
        if isinstance(item, dict)
        and isinstance(item.get("title"), str)
        and re.search(r"\bled\b", f"{item['title']} {item.get('description', '')}", re.IGNORECASE)
    ]


def seed():
    external_products = [
        (item, "fakestore")
        for item in fetch_products()
    ] + [
        (item, "dummyjson")
        for item in fetch_led_products()
    ]
    db = SessionLocal()
    cats = {}
    for name, slug in [("Electronics","electronics"),("Fashion","fashion"),("Home","home"),("Accessories","accessories")]:
        c = db.query(Category).filter_by(slug=slug).first()
        if not c:
            c = Category(name=name, slug=slug); db.add(c); db.flush()
        cats[slug] = c

    for item, source in external_products:
        name = item["title"].strip()
        description = item.get("description", "")
        category_id = category_id_for(db, cats, item["category"], name, description)
        product_slug = f"{source}-{item['id']}-{slugify(name)}"
        product = db.query(Product).filter_by(slug=product_slug).first()
        if product:
            product.category_id = category_id
        else:
            images = item.get("images", [])
            db.add(Product(
                name=name,
                slug=product_slug,
                description=description,
                price=Decimal(str(item["price"])),
                image_url=item.get("image") or item.get("thumbnail") or (images[0] if images else ""),
                stock=int(item.get("stock", 10)),
                category_id=category_id,
                is_featured=False,
            ))

    data = [
        ("Wireless Headphones","Noise-cancelling wireless headphones.",129.99,"https://images.unsplash.com/photo-1505740420928-5e560c06d30e?auto=format&fit=crop&w=900&q=80",25,"electronics"),
        ("Smart Watch","Fitness and productivity smartwatch.",89.99,"https://images.unsplash.com/photo-1523275335684-37898b6baf30?auto=format&fit=crop&w=900&q=80",30,"electronics"),
        ("Classic Sneakers","Comfortable everyday sneakers.",74.99,"https://images.unsplash.com/photo-1542291026-7eec264c27ff?auto=format&fit=crop&w=900&q=80",40,"fashion"),
        ("Minimal Backpack","Water-resistant everyday backpack.",54.99,"https://images.unsplash.com/photo-1553062407-98eeb64c6a62?auto=format&fit=crop&w=900&q=80",18,"accessories"),
        ("Desk Lamp","Adjustable LED desk lamp.",39.99,"https://images.unsplash.com/photo-1507473885765-e6ed057f782c?auto=format&fit=crop&w=900&q=80",20,"home"),
        ("Premium Sunglasses","Polarized classic sunglasses.",49.99,"https://images.unsplash.com/photo-1511499767150-a48a237f0083?auto=format&fit=crop&w=900&q=80",15,"accessories")
    ]
    for name,desc,price,img,stock,cat in data:
        category_id = category_id_for(db, cats, cat, name, desc)
        product = db.query(Product).filter_by(name=name).first()
        if product:
            product.category_id = category_id
        else:
            db.add(Product(name=name,slug=name.lower().replace(" ","-"),description=desc,price=price,image_url=img,
                           stock=stock,category_id=category_id,is_featured=True))
    if not db.query(User).filter_by(email="admin@shopsphere.local").first():
        u = User(name="Admin",email="admin@shopsphere.local",password_hash=hash_password("Admin123!"),is_admin=True)
        db.add(u); db.flush(); db.add(Cart(user_id=u.id))
    db.commit(); db.close(); print("Seed complete")

if __name__ == "__main__": seed()
