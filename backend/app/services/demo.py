"""Demo-mode helpers: seeding the demo accounts and resetting the ephemeral DB.

Kept out of ``main`` so both startup and the ``/demo/reset`` endpoint can share
one source of truth without a circular import.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.db.repositories import UserRepo

if TYPE_CHECKING:
    from app.db.database import Database
    from app.services.auth_service import AuthService
    from app.settings import AppSettings


async def seed_demo_users(db: "Database", auth: "AuthService", settings: "AppSettings") -> None:
    """On an *empty* demo DB, seed the accounts a hosted demo needs.

    - The private **superadmin** (``demo_admin_*``) so the demo isn't stuck on
      ``/setup`` after an ephemeral-DB restart — its credentials stay with the operator.
    - An optional published **admin**-role account (``demo_public_admin_*``) whose
      credentials are shared with visitors, so they can explore the admin panel
      (users, audit, the credentials screen) without the private superadmin.

    No-op when the DB already has users, or when the matching env vars are unset.
    """
    if await UserRepo(db).list():
        return
    if settings.demo_admin_email and settings.demo_admin_password:
        await auth.register(
            email=settings.demo_admin_email,
            name="Demo Admin",
            password=settings.demo_admin_password,
            role="superadmin",
        )
    if settings.demo_public_admin_email and settings.demo_public_admin_password:
        await auth.register(
            email=settings.demo_public_admin_email,
            name="Demo Admin (shared)",
            password=settings.demo_public_admin_password,
            role="admin",
        )


async def reset_demo(db: "Database", auth: "AuthService", settings: "AppSettings") -> None:
    """Wipe every row from the demo DB and re-seed the demo accounts.

    Called by the token-guarded ``/demo/reset`` endpoint (a scheduled job) so
    accumulated test accounts and runs don't pile up on the shared demo.
    """
    await db.wipe_all()
    await seed_demo_users(db, auth, settings)
