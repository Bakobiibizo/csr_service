from .health import router as health_router
from .review import router as review_router
from .standards import router as standards_router

__all__ = ["health_router", "review_router", "standards_router"]
