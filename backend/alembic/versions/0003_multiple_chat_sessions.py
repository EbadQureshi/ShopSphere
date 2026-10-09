from alembic import op
import sqlalchemy as sa


revision = "0003_multiple_chat_sessions"
down_revision = "0002_user_chat"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    user_id_constraint = next(
        (
            constraint
            for constraint in sa.inspect(bind).get_unique_constraints("chat_sessions")
            if constraint["column_names"] == ["user_id"]
        ),
        None,
    )
    if user_id_constraint is None:
        return

    if bind.dialect.name == "sqlite":
        constraint_name = user_id_constraint["name"] or "uq_chat_sessions_user_id"
        with op.batch_alter_table(
            "chat_sessions",
            naming_convention={"uq": "uq_%(table_name)s_%(column_0_name)s"},
        ) as batch_op:
            batch_op.drop_constraint(constraint_name, type_="unique")
    else:
        constraint_name = user_id_constraint["name"]
        if constraint_name is None:
            raise RuntimeError("The chat_sessions user_id uniqueness constraint has no name.")
        op.drop_constraint(constraint_name, "chat_sessions", type_="unique")

    op.create_index("ix_chat_sessions_user_id", "chat_sessions", ["user_id"])


def downgrade():
    op.drop_index("ix_chat_sessions_user_id", table_name="chat_sessions")
    op.create_unique_constraint(
        "uq_chat_sessions_user_id",
        "chat_sessions",
        ["user_id"],
    )
