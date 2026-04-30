"""API Monitor router — exposes request logs to the frontend dashboard."""

from fastapi import APIRouter, Query
from typing import Optional
from app.services.request_logger import request_logger

monitor_router = APIRouter(prefix="/v1/monitor", tags=["monitor"])


@monitor_router.get("/logs")
async def get_logs(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    method: Optional[str] = Query(None),
    path: Optional[str] = Query(None),
    status: Optional[int] = Query(None),
    search: Optional[str] = Query(None),
):
    """Get paginated API request logs with stats."""
    return request_logger.get_logs(
        limit=limit, offset=offset,
        method=method, path=path, status=status, search=search,
    )


@monitor_router.get("/stats")
async def get_stats():
    """Get aggregated request statistics."""
    return request_logger.get_logs(limit=0)


@monitor_router.delete("/logs")
async def clear_logs():
    """Clear all request logs."""
    request_logger.clear()
    return {"message": "Logs cleared", "count": request_logger.count}
