"""add concepts table

Revision ID: 2a0bf3ccc1f5
Revises: f5d71a1504bb
Create Date: 2026-06-01 20:05:05.233156

"""
from alembic import op
from pgvector.sqlalchemy import VECTOR
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '2a0bf3ccc1f5'
down_revision = 'f5d71a1504bb'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'concepts',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('document_version_id', sa.String(), nullable=False),
        sa.Column('term', sa.String(length=200), nullable=False),
        sa.Column('definition', sa.Text(), nullable=False),
        sa.Column('context_hint', sa.Text(), nullable=True),
        sa.Column('embedding', VECTOR(dim=3072), nullable=True),
        sa.Column('embedding_model', sa.String(length=100), nullable=True),
        sa.Column('extraction_order', sa.Integer(), nullable=False),
        sa.Column('metadata_json', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ['document_version_id'], ['document_versions.id'], ondelete='CASCADE'
        ),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('concepts', schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f('ix_concepts_document_version_id'),
            ['document_version_id'],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f('ix_concepts_term'),
            ['term'],
            unique=False,
        )
        batch_op.create_index(
            'ix_concepts_term_lower',
            [sa.literal_column('lower(term)')],
            unique=False,
        )

    # NOTE: pgvector 0.8.2 caps both ivfflat and hnsw at 2000 dimensions.
    # text-embedding-3-large produces 3072-dim vectors, so no ANN index is
    # possible here. Concept search (and chunk search) use exact cosine distance.
    # Revisit when either: (a) a sub-2000-dim embedding model is adopted, or
    # (b) a pgvector release lifts the ANN index dimension ceiling above 3072.


def downgrade():
    with op.batch_alter_table('concepts', schema=None) as batch_op:
        batch_op.drop_index('ix_concepts_term_lower')
        batch_op.drop_index(batch_op.f('ix_concepts_term'))
        batch_op.drop_index(batch_op.f('ix_concepts_document_version_id'))

    op.drop_table('concepts')
