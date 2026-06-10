"""SQLAlchemy ORM models.

Tables (added in the Auth & multi-tenancy + ingestion milestones):
  organizations, users, memberships, collections,
  documents, chunks, conversations, messages, feedback

Every domain table carries org_id for tenant isolation.
Import models here so Alembic autogenerate can discover them.
"""
