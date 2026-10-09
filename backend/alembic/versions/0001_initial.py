from alembic import op
import sqlalchemy as sa
revision="0001_initial"; down_revision=None; branch_labels=None; depends_on=None

def upgrade():
    op.create_table("users",
        sa.Column("id",sa.Integer,primary_key=True), sa.Column("name",sa.String(120),nullable=False),
        sa.Column("email",sa.String(255),nullable=False,unique=True), sa.Column("password_hash",sa.String(255),nullable=False),
        sa.Column("is_admin",sa.Boolean,nullable=False,server_default=sa.false()), sa.Column("created_at",sa.DateTime,nullable=False))
    op.create_table("categories",
        sa.Column("id",sa.Integer,primary_key=True),sa.Column("name",sa.String(100),nullable=False,unique=True),
        sa.Column("slug",sa.String(120),nullable=False,unique=True))
    op.create_table("products",
        sa.Column("id",sa.Integer,primary_key=True),sa.Column("category_id",sa.Integer,sa.ForeignKey("categories.id")),
        sa.Column("name",sa.String(180),nullable=False),sa.Column("slug",sa.String(200),nullable=False,unique=True),
        sa.Column("description",sa.Text,nullable=False),sa.Column("price",sa.Numeric(12,2),nullable=False),
        sa.Column("image_url",sa.String(500),nullable=False),sa.Column("stock",sa.Integer,nullable=False),
        sa.Column("is_featured",sa.Boolean,nullable=False),sa.Column("created_at",sa.DateTime,nullable=False))
    op.create_table("carts",sa.Column("id",sa.Integer,primary_key=True),
        sa.Column("user_id",sa.Integer,sa.ForeignKey("users.id"),unique=True),sa.Column("created_at",sa.DateTime,nullable=False))
    op.create_table("cart_items",sa.Column("id",sa.Integer,primary_key=True),
        sa.Column("cart_id",sa.Integer,sa.ForeignKey("carts.id")),sa.Column("product_id",sa.Integer,sa.ForeignKey("products.id")),
        sa.Column("quantity",sa.Integer,nullable=False),sa.UniqueConstraint("cart_id","product_id"))
    op.create_table("orders",sa.Column("id",sa.Integer,primary_key=True),
        sa.Column("user_id",sa.Integer,sa.ForeignKey("users.id")),sa.Column("status",sa.String(40),nullable=False),
        sa.Column("total",sa.Numeric(12,2),nullable=False),sa.Column("shipping_address",sa.String(500),nullable=False),
        sa.Column("created_at",sa.DateTime,nullable=False))
    op.create_table("order_items",sa.Column("id",sa.Integer,primary_key=True),
        sa.Column("order_id",sa.Integer,sa.ForeignKey("orders.id")),sa.Column("product_id",sa.Integer,sa.ForeignKey("products.id")),
        sa.Column("product_name",sa.String(180),nullable=False),sa.Column("unit_price",sa.Numeric(12,2),nullable=False),
        sa.Column("quantity",sa.Integer,nullable=False))

def downgrade():
    for t in ["order_items","orders","cart_items","carts","products","categories","users"]: op.drop_table(t)
