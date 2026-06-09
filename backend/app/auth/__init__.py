"""Auth & multi-tenancy.

Will hold:
  - jwt.py        : token create/verify, password hashing
  - deps.py       : current-user, current-org, role-check FastAPI dependencies

All request handlers resolve the tenant (org) from the JWT and scope DB
access by org_id.
"""
