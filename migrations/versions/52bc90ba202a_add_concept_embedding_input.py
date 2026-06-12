"""add embedding_input column to concepts

Revision ID: 52bc90ba202a
Revises: 2a0bf3ccc1f5
Create Date: 2026-06-12 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '52bc90ba202a'
down_revision = '2a0bf3ccc1f5'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('concepts', schema=None) as batch_op:
        batch_op.add_column(sa.Column('embedding_input', sa.Text(), nullable=True))


def downgrade():
    with op.batch_alter_table('concepts', schema=None) as batch_op:
        batch_op.drop_column('embedding_input')
