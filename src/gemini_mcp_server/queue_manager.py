"""Async queue system for managing concurrent requests with rate limiting."""

import asyncio
import json
import logging
import sqlite3
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class RequestStatus(str, Enum):
    """Status of a request in the queue."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class RequestPriority(str, Enum):
    """Priority levels for requests."""

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"


@dataclass
class QueuedRequest:
    """Represents a request in the queue."""

    id: str
    function_name: str
    args: tuple
    kwargs: dict
    priority: RequestPriority
    status: RequestStatus
    created_at: float
    started_at: float | None = None
    completed_at: float | None = None
    result: Any | None = None
    error: str | None = None
    retry_count: int = 0
    max_retries: int = 3


class AsyncRequestQueue:
    """Async queue for managing API requests with rate limiting and persistence."""

    def __init__(
        self,
        max_concurrent: int = 3,
        max_queue_size: int = 100,
        rate_limit_per_minute: int = 15,
        persist_to_db: bool = True,
        db_path: str | None = None,
    ):
        self.max_concurrent = max_concurrent
        self.max_queue_size = max_queue_size
        self.rate_limit_per_minute = rate_limit_per_minute
        self.persist_to_db = persist_to_db

        # Queue management
        self._queue: asyncio.PriorityQueue = asyncio.PriorityQueue(
            maxsize=max_queue_size
        )
        self._processing: dict[str, QueuedRequest] = {}
        self._completed: dict[str, QueuedRequest] = {}
        self._semaphore = asyncio.Semaphore(max_concurrent)

        # Rate limiting
        self._request_times: list[float] = []
        self._rate_lock = asyncio.Lock()

        # Database persistence
        self.db_path = db_path or "queue_persistence.db"
        if persist_to_db:
            self._init_db()

        # Background task
        self._worker_task: asyncio.Task | None = None
        self._shutdown_event = asyncio.Event()

    def _init_db(self):
        """Initialize SQLite database for queue persistence."""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS queued_requests (
                    id TEXT PRIMARY KEY,
                    function_name TEXT NOT NULL,
                    args TEXT NOT NULL,
                    kwargs TEXT NOT NULL,
                    priority TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    started_at REAL,
                    completed_at REAL,
                    result TEXT,
                    error TEXT,
                    retry_count INTEGER DEFAULT 0,
                    max_retries INTEGER DEFAULT 3
                )
            """
            )
            conn.commit()
            conn.close()
            logger.info(f"Queue database initialized at {self.db_path}")
        except Exception as e:
            logger.error(f"Failed to initialize queue database: {e}")

    def _save_request_to_db(self, request: QueuedRequest):
        """Save request to database."""
        if not self.persist_to_db:
            return

        try:
            conn = sqlite3.connect(self.db_path)
            conn.execute(
                """
                INSERT OR REPLACE INTO queued_requests 
                (id, function_name, args, kwargs, priority, status, created_at, 
                 started_at, completed_at, result, error, retry_count, max_retries)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    request.id,
                    request.function_name,
                    json.dumps(request.args),
                    json.dumps(request.kwargs),
                    request.priority.value,
                    request.status.value,
                    request.created_at,
                    request.started_at,
                    request.completed_at,
                    json.dumps(request.result) if request.result else None,
                    request.error,
                    request.retry_count,
                    request.max_retries,
                ),
            )
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Failed to save request to database: {e}")

    def _load_pending_requests(self):
        """Load pending requests from database on startup."""
        if not self.persist_to_db:
            return

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.execute(
                """
                SELECT * FROM queued_requests 
                WHERE status IN ('pending', 'processing')
                ORDER BY created_at
            """
            )

            for row in cursor.fetchall():
                request = QueuedRequest(
                    id=row[0],
                    function_name=row[1],
                    args=tuple(json.loads(row[2])),
                    kwargs=json.loads(row[3]),
                    priority=RequestPriority(row[4]),
                    status=RequestStatus.PENDING,  # Reset processing to pending
                    created_at=row[6],
                    started_at=row[7],
                    completed_at=row[8],
                    result=json.loads(row[9]) if row[9] else None,
                    error=row[10],
                    retry_count=row[11],
                    max_retries=row[12],
                )
                # Add back to queue
                priority_value = self._get_priority_value(request.priority)
                self._queue.put_nowait((priority_value, request.created_at, request))

            conn.close()
            logger.info("Loaded pending requests from database")
        except Exception as e:
            logger.error(f"Failed to load pending requests: {e}")

    def _get_priority_value(self, priority: RequestPriority) -> int:
        """Convert priority enum to numeric value for queue ordering."""
        priority_map = {
            RequestPriority.HIGH: 1,
            RequestPriority.NORMAL: 2,
            RequestPriority.LOW: 3,
        }
        return priority_map[priority]

    async def _check_rate_limit(self) -> bool:
        """Check if we can make a new request within rate limits."""
        async with self._rate_lock:
            now = time.time()
            # Remove requests older than 1 minute
            self._request_times = [t for t in self._request_times if now - t < 60]

            if len(self._request_times) < self.rate_limit_per_minute:
                self._request_times.append(now)
                return True
            return False

    async def _get_wait_time(self) -> float:
        """Get the time to wait before next request is allowed."""
        async with self._rate_lock:
            if len(self._request_times) < self.rate_limit_per_minute:
                return 0.0

            # Time until oldest request expires
            oldest = min(self._request_times)
            return 60 - (time.time() - oldest)

    async def enqueue(
        self,
        function: Callable,
        *args,
        priority: RequestPriority = RequestPriority.NORMAL,
        max_retries: int = 3,
        **kwargs,
    ) -> str:
        """
        Enqueue a function call for execution.

        Args:
            function: The async function to call
            *args: Positional arguments for the function
            priority: Request priority
            max_retries: Maximum number of retry attempts
            **kwargs: Keyword arguments for the function

        Returns:
            Request ID for tracking

        Raises:
            asyncio.QueueFull: If the queue is full
        """
        request_id = str(uuid.uuid4())
        request = QueuedRequest(
            id=request_id,
            function_name=function.__name__,
            args=args,
            kwargs=kwargs,
            priority=priority,
            status=RequestStatus.PENDING,
            created_at=time.time(),
            max_retries=max_retries,
        )

        # Store function reference separately (not persisted)
        if not hasattr(self, "_functions"):
            self._functions = {}
        self._functions[request_id] = function

        priority_value = self._get_priority_value(priority)
        await self._queue.put((priority_value, request.created_at, request))

        self._save_request_to_db(request)
        logger.info(f"Enqueued request {request_id} with priority {priority.value}")

        return request_id

    async def get_status(self, request_id: str) -> QueuedRequest | None:
        """Get the status of a request."""
        # Check processing requests
        if request_id in self._processing:
            return self._processing[request_id]

        # Check completed requests
        if request_id in self._completed:
            return self._completed[request_id]

        # Check database
        if self.persist_to_db:
            try:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.execute(
                    "SELECT * FROM queued_requests WHERE id = ?", (request_id,)
                )
                row = cursor.fetchone()
                conn.close()

                if row:
                    return QueuedRequest(
                        id=row[0],
                        function_name=row[1],
                        args=tuple(json.loads(row[2])),
                        kwargs=json.loads(row[3]),
                        priority=RequestPriority(row[4]),
                        status=RequestStatus(row[5]),
                        created_at=row[6],
                        started_at=row[7],
                        completed_at=row[8],
                        result=json.loads(row[9]) if row[9] else None,
                        error=row[10],
                        retry_count=row[11],
                        max_retries=row[12],
                    )
            except Exception as e:
                logger.error(f"Failed to get request status from database: {e}")

        return None

    async def cancel_request(self, request_id: str) -> bool:
        """Cancel a pending request."""
        # Can't cancel if already processing or completed
        if request_id in self._processing or request_id in self._completed:
            return False

        # Mark as cancelled in database
        if self.persist_to_db:
            try:
                conn = sqlite3.connect(self.db_path)
                conn.execute(
                    "UPDATE queued_requests SET status = ? WHERE id = ?",
                    (RequestStatus.CANCELLED.value, request_id),
                )
                conn.commit()
                conn.close()
            except Exception as e:
                logger.error(f"Failed to cancel request in database: {e}")

        logger.info(f"Cancelled request {request_id}")
        return True

    async def get_queue_stats(self) -> dict[str, Any]:
        """Get queue statistics."""
        queue_size = self._queue.qsize()
        processing_count = len(self._processing)
        wait_time = await self._get_wait_time()

        return {
            "queue_size": queue_size,
            "processing_count": processing_count,
            "max_concurrent": self.max_concurrent,
            "max_queue_size": self.max_queue_size,
            "rate_limit_per_minute": self.rate_limit_per_minute,
            "requests_last_minute": len(self._request_times),
            "wait_time_seconds": wait_time,
        }

    async def _process_request(self, request: QueuedRequest, function: Callable):
        """Process a single request."""
        async with self._semaphore:
            request.status = RequestStatus.PROCESSING
            request.started_at = time.time()
            self._processing[request.id] = request
            self._save_request_to_db(request)

            try:
                # Wait for rate limit if needed
                while not await self._check_rate_limit():
                    wait_time = await self._get_wait_time()
                    if wait_time > 0:
                        logger.info(f"Rate limited, waiting {wait_time:.1f} seconds")
                        await asyncio.sleep(wait_time)

                # Execute the function
                result = await function(*request.args, **request.kwargs)

                request.status = RequestStatus.COMPLETED
                request.completed_at = time.time()
                request.result = result

                logger.info(f"Completed request {request.id}")

            except Exception as e:
                request.retry_count += 1

                if request.retry_count <= request.max_retries:
                    logger.warning(
                        f"Request {request.id} failed (attempt {request.retry_count}), will retry: {e}"
                    )
                    request.status = RequestStatus.PENDING
                    # Re-queue for retry
                    priority_value = self._get_priority_value(request.priority)
                    await self._queue.put((priority_value, time.time(), request))
                else:
                    logger.error(
                        f"Request {request.id} failed permanently after {request.retry_count} attempts: {e}"
                    )
                    request.status = RequestStatus.FAILED
                    request.completed_at = time.time()
                    request.error = str(e)

            finally:
                # Move from processing to completed
                if request.id in self._processing:
                    del self._processing[request.id]

                if request.status in (RequestStatus.COMPLETED, RequestStatus.FAILED):
                    self._completed[request.id] = request

                self._save_request_to_db(request)

    async def _worker(self):
        """Background worker to process queued requests."""
        logger.info("Queue worker started")

        while not self._shutdown_event.is_set():
            try:
                # Wait for a request with timeout
                try:
                    priority_value, created_at, request = await asyncio.wait_for(
                        self._queue.get(), timeout=1.0
                    )
                except asyncio.TimeoutError:
                    continue

                # Skip cancelled requests
                if request.status == RequestStatus.CANCELLED:
                    continue

                # Get the function
                function = self._functions.get(request.id)
                if not function:
                    logger.error(f"Function not found for request {request.id}")
                    request.status = RequestStatus.FAILED
                    request.error = "Function not found"
                    self._completed[request.id] = request
                    self._save_request_to_db(request)
                    continue

                # Process the request
                await self._process_request(request, function)

            except Exception as e:
                logger.error(f"Error in queue worker: {e}")

    async def start(self):
        """Start the queue worker."""
        if self._worker_task is not None:
            return

        # Load pending requests from database
        self._load_pending_requests()

        # Start the worker
        self._worker_task = asyncio.create_task(self._worker())
        logger.info("Queue started")

    async def stop(self):
        """Stop the queue worker."""
        if self._worker_task is None:
            return

        self._shutdown_event.set()
        await self._worker_task
        self._worker_task = None
        logger.info("Queue stopped")

    async def wait_for_completion(
        self, request_id: str, timeout: float | None = None
    ) -> QueuedRequest:
        """
        Wait for a request to complete.

        Args:
            request_id: The request ID to wait for
            timeout: Maximum time to wait in seconds

        Returns:
            The completed request

        Raises:
            asyncio.TimeoutError: If timeout is reached
            ValueError: If request not found
        """
        start_time = time.time()

        while True:
            request = await self.get_status(request_id)
            if not request:
                raise ValueError(f"Request {request_id} not found")

            if request.status in (
                RequestStatus.COMPLETED,
                RequestStatus.FAILED,
                RequestStatus.CANCELLED,
            ):
                return request

            if timeout and (time.time() - start_time) > timeout:
                raise asyncio.TimeoutError(
                    f"Request {request_id} did not complete within {timeout} seconds"
                )

            await asyncio.sleep(0.1)


# Global queue instance
request_queue: AsyncRequestQueue | None = None


def get_request_queue() -> AsyncRequestQueue:
    """Get the global request queue instance."""
    global request_queue
    if request_queue is None:
        request_queue = AsyncRequestQueue()
    return request_queue
