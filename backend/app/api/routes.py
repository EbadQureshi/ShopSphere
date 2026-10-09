from decimal import Decimal
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from groq import GroqError
from jose import jwt, JWTError
from slugify import slugify
from sqlalchemy import func, select, or_
from sqlalchemy.orm import Session, joinedload
from app.core.config import settings
from app.core.security import hash_password, verify_password, token_for
from app.db.session import get_db
from app.models import User, Category, Product, Cart, CartItem, Order, OrderItem, ChatMessage, ChatSession
from app.recommendations import category_family, rank_related_products
from app.schemas import *
from app.chatbot import (
    generate_answer,
    retrieval_query,
    retrieve_products,
    sync_product_index,
)

router = APIRouter(prefix="/api/v1")
bearer = HTTPBearer()

def current_user(creds: HTTPAuthorizationCredentials = Depends(bearer), db: Session = Depends(get_db)):
    try:
        payload = jwt.decode(creds.credentials, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        user = db.get(User, int(payload["sub"]))
    except (JWTError, ValueError, KeyError):
        user = None
    if not user:
        raise HTTPException(401, "Invalid authentication")
    return user

def admin(user: User = Depends(current_user)):
    if not user.is_admin:
        raise HTTPException(403, "Admin access required")
    return user

def cart_for(user: User, db: Session):
    cart = db.scalar(select(Cart).where(Cart.user_id == user.id))
    if not cart:
        cart = Cart(user_id=user.id)
        db.add(cart); db.commit(); db.refresh(cart)
    return cart

def cart_out(cart: Cart):
    items, total = [], Decimal("0")
    for x in cart.items:
        subtotal = x.product.price * x.quantity
        total += subtotal
        items.append(CartItemOut(product_id=x.product_id, name=x.product.name, price=x.product.price,
                                 image_url=x.product.image_url, quantity=x.quantity, subtotal=subtotal))
    return CartOut(items=items, total=total)

@router.post("/auth/register", response_model=TokenOut)
def register(data: Register, db: Session = Depends(get_db)):
    if db.scalar(select(User).where(User.email == data.email)):
        raise HTTPException(409, "Email already registered")
    user = User(name=data.name, email=data.email, password_hash=hash_password(data.password))
    db.add(user); db.flush(); db.add(Cart(user_id=user.id)); db.commit(); db.refresh(user)
    return TokenOut(access_token=token_for(user.id), user=user)

@router.post("/auth/login", response_model=TokenOut)
def login(data: Login, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == data.email))
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(401, "Invalid email or password")
    return TokenOut(access_token=token_for(user.id), user=user)

@router.get("/auth/me", response_model=UserOut)
def me(user: User = Depends(current_user)): return user

@router.get("/chat/history", response_model=ChatHistoryOut)
def chat_history(user: User = Depends(current_user), db: Session = Depends(get_db)):
    chat_session = db.scalar(
        select(ChatSession)
        .where(ChatSession.user_id == user.id)
        .order_by(ChatSession.created_at.desc(), ChatSession.id.desc())
    )
    return ChatHistoryOut(messages=chat_session.messages if chat_session else [])

@router.post("/chat/sessions", response_model=ChatSessionOut)
def create_chat_session(user: User = Depends(current_user), db: Session = Depends(get_db)):
    chat_session = ChatSession(user_id=user.id)
    db.add(chat_session)
    db.commit()
    db.refresh(chat_session)
    return ChatSessionOut(id=chat_session.id)

@router.get("/chat/sessions", response_model=list[ChatSessionSummaryOut])
def chat_sessions(user: User = Depends(current_user), db: Session = Depends(get_db)):
    preview = (
        select(ChatMessage.content)
        .where(
            ChatMessage.session_id == ChatSession.id,
            ChatMessage.role == "user",
        )
        .order_by(ChatMessage.id)
        .limit(1)
        .scalar_subquery()
    )
    last_activity = (
        select(func.max(ChatMessage.created_at))
        .where(ChatMessage.session_id == ChatSession.id)
        .scalar_subquery()
    )
    rows = db.execute(
        select(
            ChatSession.id,
            preview.label("preview"),
            func.coalesce(last_activity, ChatSession.created_at).label("updated_at"),
        )
        .where(ChatSession.user_id == user.id)
        .where(
            select(ChatMessage.id)
            .where(ChatMessage.session_id == ChatSession.id)
            .exists()
        )
        .order_by(
            func.coalesce(last_activity, ChatSession.created_at).desc(),
            ChatSession.id.desc(),
        )
    )
    return [
        ChatSessionSummaryOut(
            id=row.id,
            preview=(row.preview or "New conversation")[:120],
            updated_at=row.updated_at,
        )
        for row in rows
    ]

@router.get("/chat/sessions/{session_id}", response_model=ChatHistoryOut)
def chat_session_history(
    session_id: int,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    chat_session = db.scalar(
        select(ChatSession).where(
            ChatSession.id == session_id,
            ChatSession.user_id == user.id,
        )
    )
    if chat_session is None:
        raise HTTPException(404, "Chat session not found.")
    messages = list(
        db.scalars(
            select(ChatMessage)
            .where(ChatMessage.session_id == chat_session.id)
            .order_by(ChatMessage.created_at, ChatMessage.id)
        )
    )
    return ChatHistoryOut(messages=messages)

@router.post("/chat", response_model=ChatReplyOut)
def chat(data: ChatRequest, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if not settings.groq_api_key.strip():
        raise HTTPException(503, "Chatbot is not configured. Set GROQ_API_KEY in backend/.env.")

    chat_session = db.scalar(
        select(ChatSession).where(
            ChatSession.id == data.session_id,
            ChatSession.user_id == user.id,
        )
    )
    if chat_session is None:
        raise HTTPException(404, "Chat session not found.")

    history = list(
        db.scalars(
            select(ChatMessage)
            .where(ChatMessage.session_id == chat_session.id)
            .order_by(ChatMessage.created_at, ChatMessage.id)
        )
    )
    product_query = retrieval_query(data.message, history)
    try:
        collection = sync_product_index(db)
        product_documents, product_ids = retrieve_products(collection, product_query)
        products = list(
            db.scalars(
                select(Product)
                .where(Product.id.in_(product_ids))
                .options(joinedload(Product.category))
            )
        ) if product_ids else []
        products_by_id = {product.id: product for product in products}
        products = [products_by_id[product_id] for product_id in product_ids if product_id in products_by_id]
        answer_text = generate_answer(data.message, product_documents, history)
    except (GroqError, RuntimeError) as error:
        db.rollback()
        raise HTTPException(502, "The chatbot service could not generate a reply.") from error

    user_message = ChatMessage(
        session_id=chat_session.id,
        role="user",
        content=data.message,
    )
    answer = ChatMessage(
        session_id=chat_session.id,
        role="assistant",
        content=answer_text,
    )
    db.add_all([user_message, answer])
    db.commit()
    db.refresh(answer)
    messages = list(
        db.scalars(
            select(ChatMessage)
            .where(ChatMessage.session_id == chat_session.id)
            .order_by(ChatMessage.created_at, ChatMessage.id)
        )
    )
    return ChatReplyOut(
        answer=answer,
        messages=messages,
        products=[
            ChatProductOut(
                id=product.id,
                name=product.name,
                description=product.description,
                price=product.price,
                image_url=product.image_url,
                stock=product.stock,
                category_name=product.category.name if product.category else "Uncategorized",
            )
            for product in products
        ],
    )

@router.get("/categories", response_model=list[CategoryOut])
def categories(db: Session = Depends(get_db)):
    return list(db.scalars(select(Category).order_by(Category.name)))

@router.get("/products", response_model=list[ProductOut])
def products(search: Optional[str] = None, category_id: Optional[int] = None, db: Session = Depends(get_db)):
    q = select(Product).order_by(Product.created_at.desc())
    if search:
        term = f"%{search}%"
        q = q.where(or_(Product.name.ilike(term), Product.description.ilike(term)))
    if category_id: q = q.where(Product.category_id == category_id)
    return list(db.scalars(q.limit(100)))

@router.get("/products/{id}", response_model=ProductOut)
def product(id: int, db: Session = Depends(get_db)):
    x = db.get(Product, id)
    if not x: raise HTTPException(404, "Product not found")
    return x

@router.get("/products/{id}/related", response_model=list[ProductOut])
def related_products(id: int, db: Session = Depends(get_db)):
    selected = db.get(Product, id)
    if not selected: raise HTTPException(404, "Product not found")
    if selected.category_id is None: return []
    categories = {category.id: category for category in db.scalars(select(Category))}
    selected_category = categories.get(selected.category_id)
    if selected_category is None: return []
    family = category_family(selected_category.slug)
    family_ids = [category.id for category in categories.values()
                  if category_family(category.slug) == family]
    candidates = db.scalars(
        select(Product).where(Product.category_id.in_(family_ids), Product.id != selected.id)
    )
    return rank_related_products(selected, candidates, categories)

@router.post("/products", response_model=ProductOut)
def create_product(data: ProductIn, db: Session = Depends(get_db), _: User = Depends(admin)):
    x = Product(**data.model_dump(), slug=slugify(data.name))
    db.add(x); db.commit(); db.refresh(x); return x

@router.put("/products/{id}", response_model=ProductOut)
def update_product(id: int, data: ProductIn, db: Session = Depends(get_db), _: User = Depends(admin)):
    x = db.get(Product, id)
    if not x: raise HTTPException(404, "Product not found")
    for k,v in data.model_dump().items(): setattr(x,k,v)
    x.slug = slugify(data.name); db.commit(); db.refresh(x); return x

@router.delete("/products/{id}")
def delete_product(id: int, db: Session = Depends(get_db), _: User = Depends(admin)):
    x = db.get(Product, id)
    if not x: raise HTTPException(404, "Product not found")
    db.delete(x); db.commit(); return {"message":"deleted"}

@router.get("/cart", response_model=CartOut)
def get_cart(user: User = Depends(current_user), db: Session = Depends(get_db)):
    cart = cart_for(user, db)
    db.refresh(cart)
    return cart_out(cart)

@router.post("/cart/items", response_model=CartOut)
def add_cart(data: CartAdd, user: User = Depends(current_user), db: Session = Depends(get_db)):
    cart = cart_for(user, db); product = db.get(Product, data.product_id)
    if not product: raise HTTPException(404, "Product not found")
    item = db.scalar(select(CartItem).where(CartItem.cart_id==cart.id, CartItem.product_id==product.id))
    new_qty = (item.quantity if item else 0) + data.quantity
    if new_qty > product.stock: raise HTTPException(400, "Not enough stock")
    if item: item.quantity = new_qty
    else: db.add(CartItem(cart_id=cart.id, product_id=product.id, quantity=data.quantity))
    db.commit(); db.refresh(cart); return cart_out(cart)

@router.patch("/cart/items/{product_id}", response_model=CartOut)
def update_cart(product_id: int, data: CartUpdate, user: User = Depends(current_user), db: Session = Depends(get_db)):
    cart = cart_for(user, db)
    item = db.scalar(select(CartItem).where(CartItem.cart_id==cart.id, CartItem.product_id==product_id))
    if not item: raise HTTPException(404, "Item not found")
    if data.quantity > item.product.stock: raise HTTPException(400, "Not enough stock")
    item.quantity = data.quantity; db.commit(); db.refresh(cart); return cart_out(cart)

@router.delete("/cart/items/{product_id}", response_model=CartOut)
def remove_cart(product_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    cart = cart_for(user, db)
    item = db.scalar(select(CartItem).where(CartItem.cart_id==cart.id, CartItem.product_id==product_id))
    if item: db.delete(item); db.commit()
    db.refresh(cart); return cart_out(cart)

@router.post("/orders", response_model=OrderOut)
def create_order(data: OrderCreate, user: User = Depends(current_user), db: Session = Depends(get_db)):
    cart = cart_for(user, db)
    if not cart.items: raise HTTPException(400, "Cart is empty")
    order = Order(user_id=user.id, shipping_address=data.shipping_address, total=0)
    db.add(order); db.flush()
    total = Decimal("0")
    for ci in cart.items:
        if ci.quantity > ci.product.stock: raise HTTPException(400, f"Not enough stock: {ci.product.name}")
        total += ci.product.price * ci.quantity
        db.add(OrderItem(order_id=order.id, product_id=ci.product_id, product_name=ci.product.name,
                         unit_price=ci.product.price, quantity=ci.quantity))
        ci.product.stock -= ci.quantity
        db.delete(ci)
    order.total = total; db.commit()
    return db.scalar(select(Order).where(Order.id==order.id).options(joinedload(Order.items)))

@router.get("/orders", response_model=list[OrderOut])
def orders(user: User = Depends(current_user), db: Session = Depends(get_db)):
    q = select(Order).where(Order.user_id==user.id).options(joinedload(Order.items)).order_by(Order.created_at.desc())
    return list(db.execute(q).unique().scalars())

@router.get("/orders/{id}", response_model=OrderOut)
def order(id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    q = select(Order).where(Order.id==id, Order.user_id==user.id).options(joinedload(Order.items))
    x = db.execute(q).unique().scalar_one_or_none()
    if not x: raise HTTPException(404, "Order not found")
    return x
