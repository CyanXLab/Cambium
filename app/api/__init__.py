"""
Cambium API Routers — modular route definitions.

This package contains FastAPI APIRouter modules that will progressively
replace the monolithic main.py. Each router owns a domain of endpoints.

Current status (v2.2):
  - routers/__init__.py: router registry
  - routers/system.py: health, migrations, debug, vector-store status
  - routers/governance.py: SSGM memory governance endpoints
  - routers/agent_v2.py: v2 Agent Loop endpoint
  - routers/providers.py: API provider management (main + custom)

Future (v2.3+):
  - routers/chat.py, routers/memory.py, routers/cognitive.py, etc.
  - main.py will be reduced to app instantiation + router registration
"""
from fastapi import APIRouter

from .system import router as system_router
from .governance import router as governance_router
from .agent_v2 import router as agent_v2_router
from .providers import router as providers_router


def get_all_routers() -> list[APIRouter]:
    """Return all v2 modular routers, in registration order."""
    return [
        system_router,
        governance_router,
        agent_v2_router,
        providers_router,
    ]


__all__ = [
    "get_all_routers",
    "system_router",
    "governance_router",
    "agent_v2_router",
    "providers_router",
]
