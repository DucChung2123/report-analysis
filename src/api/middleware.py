from fastapi import Request
import time
from typing import Callable
import logging
import asyncio

from fastapi.responses import JSONResponse


logger = logging.getLogger("     api")


async def logging_middleware(request: Request, call_next: Callable):
    """Middleware to log API requests and response time."""
    start_time = time.time()

    # Xử lý request
    response = await call_next(request)

    # Tính thời gian xử lý
    process_time = time.time() - start_time

    # Tạo task mới để log mà không chặn response
    async def log_after_response():
        # Đợi 10ms để đảm bảo response đã được gửi đi
        await asyncio.sleep(0.01)
        logger.info(
            f"Request path: {request.url.path} ({request.method}) - Took {process_time:.2f}s"
        )

    # Tạo task mà không đợi nó hoàn thành
    asyncio.create_task(log_after_response())

    return response


async def error_handler_middleware(request: Request, call_next: Callable):
    """Middleware to handle unexpected errors."""
    try:
        return await call_next(request)
    except Exception as e:
        logger.error(f"Unhandled exception: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error. Please try again later."},
        )
