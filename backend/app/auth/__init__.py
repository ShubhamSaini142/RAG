"""Auth & multi-tenancy.

  - security.py : password hashing (bcrypt) + JWT create/verify
  - schemas.py  : Pydantic request/response models
  - deps.py     : current-user, current-context (org+role), role-check deps

All protected handlers resolve the tenant (org) from the JWT and scope DB
access by org_id.
"""
