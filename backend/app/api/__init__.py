"""HTTP layer: FastAPI routers, request/response schemas, and DI wiring.

``API_V1`` is the single source of truth for the API version prefix. Every router
and cookie path derives from it, so bumping to ``/api/v2`` is a one-line change.
"""

API_V1 = "/api/v1"
