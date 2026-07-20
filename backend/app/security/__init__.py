"""Security primitives: the credential vault (crypto), master-key resolution.

Auth (passwords, JWT, RBAC) and OAuth land in later M3 slices. Nothing here
imports FastAPI or the DB — these are pure, unit-testable building blocks.
"""
