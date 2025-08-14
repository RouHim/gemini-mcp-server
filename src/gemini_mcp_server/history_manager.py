"""Image generation history and metadata tracking system."""

import asyncio
import json
import logging
import sqlite3
import time
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
import os
import shutil
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class GenerationMetadata:
    """Metadata for a single image generation."""

    id: str
    prompt: str
    timestamp: datetime
    parameters: Dict[str, Any]
    file_path: Optional[str] = None
    file_size: Optional[int] = None
    success: bool = True
    error_message: Optional[str] = None
    generation_time: float = 0.0
    model: str = "gemini-2.0-flash-exp"


class ImageHistoryManager:
    """Manages image generation history and metadata storage."""

    def __init__(
        self,
        db_path: str = "image_history.db",
        storage_path: Optional[str] = None,
        max_storage_size_mb: int = 1000,
        max_age_days: int = 30,
        max_count: int = 100,
        auto_cleanup: bool = True,
    ):
        """
        Initialize the history manager.

        Args:
            db_path: Path to SQLite database file
            storage_path: Optional path for storing images locally
            max_storage_size_mb: Maximum storage size in MB
            max_age_days: Maximum age for stored images
            max_count: Maximum number of images to keep
            auto_cleanup: Whether to automatically cleanup old files
        """
        self.db_path = db_path
        self.storage_path = Path(storage_path) if storage_path else None
        self.max_storage_size_mb = max_storage_size_mb
        self.max_age_days = max_age_days
        self.max_count = max_count
        self.auto_cleanup = auto_cleanup

        self._init_database()
        if self.storage_path:
            self.storage_path.mkdir(parents=True, exist_ok=True)

    def _init_database(self):
        """Initialize the SQLite database."""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS image_generations (
                    id TEXT PRIMARY KEY,
                    prompt TEXT NOT NULL,
                    timestamp REAL NOT NULL,
                    parameters TEXT NOT NULL,
                    file_path TEXT,
                    file_size INTEGER,
                    success BOOLEAN NOT NULL,
                    error_message TEXT,
                    generation_time REAL NOT NULL,
                    model TEXT NOT NULL
                )
            """
            )

            # Create indexes for common queries
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_timestamp ON image_generations(timestamp)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_success ON image_generations(success)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_model ON image_generations(model)"
            )

            conn.commit()
            conn.close()
            logger.info(f"History database initialized at {self.db_path}")
        except Exception as e:
            logger.error(f"Failed to initialize history database: {e}")
            raise

    async def save_generation(
        self,
        prompt: str,
        parameters: Dict[str, Any],
        image_data: Optional[bytes] = None,
        success: bool = True,
        error_message: Optional[str] = None,
        generation_time: float = 0.0,
        model: str = "gemini-2.0-flash-exp",
    ) -> str:
        """
        Save a generation record to the database and optionally store the image.

        Args:
            prompt: The text prompt used
            parameters: Generation parameters
            image_data: Optional image binary data
            success: Whether generation was successful
            error_message: Error message if failed
            generation_time: Time taken to generate
            model: Model used for generation

        Returns:
            Generation ID
        """
        generation_id = str(uuid.uuid4())
        timestamp = datetime.now()
        file_path = None
        file_size = None

        # Save image to local storage if enabled and data provided
        if self.storage_path and image_data:
            try:
                file_path = await self._save_image_file(generation_id, image_data)
                file_size = len(image_data)
            except Exception as e:
                logger.error(f"Failed to save image file: {e}")

        metadata = GenerationMetadata(
            id=generation_id,
            prompt=prompt,
            timestamp=timestamp,
            parameters=parameters,
            file_path=file_path,
            file_size=file_size,
            success=success,
            error_message=error_message,
            generation_time=generation_time,
            model=model,
        )

        # Save to database
        try:
            conn = sqlite3.connect(self.db_path)
            conn.execute(
                """
                INSERT INTO image_generations 
                (id, prompt, timestamp, parameters, file_path, file_size, 
                 success, error_message, generation_time, model)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    metadata.id,
                    metadata.prompt,
                    metadata.timestamp.timestamp(),
                    json.dumps(metadata.parameters),
                    metadata.file_path,
                    metadata.file_size,
                    metadata.success,
                    metadata.error_message,
                    metadata.generation_time,
                    metadata.model,
                ),
            )
            conn.commit()
            conn.close()

            logger.info(f"Saved generation record {generation_id}")

            # Auto cleanup if enabled
            if self.auto_cleanup:
                await self._auto_cleanup()

        except Exception as e:
            logger.error(f"Failed to save generation record: {e}")
            raise

        return generation_id

    async def _save_image_file(self, generation_id: str, image_data: bytes) -> str:
        """Save image data to local file."""
        if not self.storage_path:
            raise ValueError("Storage path not configured")

        # Use PNG extension by default
        filename = f"{generation_id}.png"
        file_path = self.storage_path / filename

        # Write file
        with open(file_path, "wb") as f:
            f.write(image_data)

        return str(file_path)

    async def get_generation(self, generation_id: str) -> Optional[GenerationMetadata]:
        """Get a specific generation record."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.execute(
                "SELECT * FROM image_generations WHERE id = ?", (generation_id,)
            )
            row = cursor.fetchone()
            conn.close()

            if row:
                return self._row_to_metadata(row)
            return None

        except Exception as e:
            logger.error(f"Failed to get generation record: {e}")
            return None

    async def get_history(
        self,
        limit: int = 50,
        offset: int = 0,
        success_only: bool = False,
        model_filter: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> List[GenerationMetadata]:
        """
        Get generation history with filtering.

        Args:
            limit: Maximum number of records to return
            offset: Number of records to skip
            success_only: Only return successful generations
            model_filter: Filter by model name
            start_date: Start date filter
            end_date: End date filter

        Returns:
            List of generation metadata
        """
        try:
            conn = sqlite3.connect(self.db_path)

            # Build query
            query = "SELECT * FROM image_generations WHERE 1=1"
            params = []

            if success_only:
                query += " AND success = ?"
                params.append(True)

            if model_filter:
                query += " AND model = ?"
                params.append(model_filter)

            if start_date:
                query += " AND timestamp >= ?"
                params.append(start_date.timestamp())

            if end_date:
                query += " AND timestamp <= ?"
                params.append(end_date.timestamp())

            query += " ORDER BY timestamp DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])

            cursor = conn.execute(query, params)
            rows = cursor.fetchall()
            conn.close()

            return [self._row_to_metadata(row) for row in rows]

        except Exception as e:
            logger.error(f"Failed to get history: {e}")
            return []

    async def search_history(
        self,
        search_term: str,
        limit: int = 50,
    ) -> List[GenerationMetadata]:
        """Search generation history by prompt text."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.execute(
                """
                SELECT * FROM image_generations 
                WHERE prompt LIKE ? 
                ORDER BY timestamp DESC 
                LIMIT ?
            """,
                (f"%{search_term}%", limit),
            )
            rows = cursor.fetchall()
            conn.close()

            return [self._row_to_metadata(row) for row in rows]

        except Exception as e:
            logger.error(f"Failed to search history: {e}")
            return []

    async def get_statistics(self) -> Dict[str, Any]:
        """Get generation statistics."""
        try:
            conn = sqlite3.connect(self.db_path)

            # Total generations
            cursor = conn.execute("SELECT COUNT(*) FROM image_generations")
            total_count = cursor.fetchone()[0]

            # Successful generations
            cursor = conn.execute(
                "SELECT COUNT(*) FROM image_generations WHERE success = ?", (True,)
            )
            success_count = cursor.fetchone()[0]

            # Failed generations
            failed_count = total_count - success_count

            # Average generation time
            cursor = conn.execute(
                "SELECT AVG(generation_time) FROM image_generations WHERE success = ?",
                (True,),
            )
            avg_time = cursor.fetchone()[0] or 0.0

            # Total storage size
            cursor = conn.execute(
                "SELECT SUM(file_size) FROM image_generations WHERE file_size IS NOT NULL"
            )
            total_size = cursor.fetchone()[0] or 0

            # Model breakdown
            cursor = conn.execute(
                """
                SELECT model, COUNT(*) 
                FROM image_generations 
                GROUP BY model
            """
            )
            model_counts = dict(cursor.fetchall())

            # Recent activity (last 7 days)
            week_ago = (datetime.now() - timedelta(days=7)).timestamp()
            cursor = conn.execute(
                "SELECT COUNT(*) FROM image_generations WHERE timestamp >= ?",
                (week_ago,),
            )
            recent_count = cursor.fetchone()[0]

            conn.close()

            return {
                "total_generations": total_count,
                "successful_generations": success_count,
                "failed_generations": failed_count,
                "success_rate": success_count / total_count if total_count > 0 else 0.0,
                "average_generation_time": avg_time,
                "total_storage_size_bytes": total_size,
                "total_storage_size_mb": (
                    total_size / (1024 * 1024) if total_size else 0
                ),
                "model_counts": model_counts,
                "recent_generations_7_days": recent_count,
            }

        except Exception as e:
            logger.error(f"Failed to get statistics: {e}")
            return {}

    async def export_history(
        self,
        format: str = "json",
        include_files: bool = False,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Union[str, bytes]:
        """
        Export generation history to JSON or CSV format.

        Args:
            format: Export format ("json" or "csv")
            include_files: Whether to include image file data
            start_date: Start date filter
            end_date: End date filter

        Returns:
            Exported data as string or bytes
        """
        history = await self.get_history(
            limit=10000,  # Large limit for export
            start_date=start_date,
            end_date=end_date,
        )

        if format.lower() == "json":
            return await self._export_json(history, include_files)
        elif format.lower() == "csv":
            return await self._export_csv(history)
        else:
            raise ValueError(f"Unsupported export format: {format}")

    async def _export_json(
        self, history: List[GenerationMetadata], include_files: bool
    ) -> str:
        """Export history to JSON format."""
        export_data = []

        for item in history:
            data = {
                "id": item.id,
                "prompt": item.prompt,
                "timestamp": item.timestamp.isoformat(),
                "parameters": item.parameters,
                "file_path": item.file_path,
                "file_size": item.file_size,
                "success": item.success,
                "error_message": item.error_message,
                "generation_time": item.generation_time,
                "model": item.model,
            }

            # Include base64 encoded file data if requested
            if include_files and item.file_path and os.path.exists(item.file_path):
                try:
                    with open(item.file_path, "rb") as f:
                        import base64

                        data["file_data"] = base64.b64encode(f.read()).decode("utf-8")
                except Exception as e:
                    logger.error(f"Failed to include file data for {item.id}: {e}")

            export_data.append(data)

        return json.dumps(export_data, indent=2)

    async def _export_csv(self, history: List[GenerationMetadata]) -> str:
        """Export history to CSV format."""
        import csv
        import io

        output = io.StringIO()
        writer = csv.writer(output)

        # Write header
        writer.writerow(
            [
                "id",
                "prompt",
                "timestamp",
                "parameters",
                "file_path",
                "file_size",
                "success",
                "error_message",
                "generation_time",
                "model",
            ]
        )

        # Write data
        for item in history:
            writer.writerow(
                [
                    item.id,
                    item.prompt,
                    item.timestamp.isoformat(),
                    json.dumps(item.parameters),
                    item.file_path,
                    item.file_size,
                    item.success,
                    item.error_message,
                    item.generation_time,
                    item.model,
                ]
            )

        return output.getvalue()

    async def cleanup_old_files(self, dry_run: bool = False) -> Dict[str, Any]:
        """
        Cleanup old files based on configured retention policies.

        Args:
            dry_run: If True, only report what would be deleted

        Returns:
            Cleanup report
        """
        if not self.storage_path or not self.storage_path.exists():
            return {"error": "Storage path not configured or doesn't exist"}

        deleted_count = 0
        deleted_size = 0
        errors = []

        try:
            conn = sqlite3.connect(self.db_path)

            # Get files to delete based on age
            cutoff_time = (
                datetime.now() - timedelta(days=self.max_age_days)
            ).timestamp()
            cursor = conn.execute(
                """
                SELECT id, file_path, file_size 
                FROM image_generations 
                WHERE timestamp < ? AND file_path IS NOT NULL
            """,
                (cutoff_time,),
            )

            old_files = cursor.fetchall()

            # Get files to delete based on count (keep only max_count newest)
            cursor = conn.execute(
                """
                SELECT id, file_path, file_size 
                FROM image_generations 
                WHERE file_path IS NOT NULL
                ORDER BY timestamp DESC
                LIMIT -1 OFFSET ?
            """,
                (self.max_count,),
            )

            excess_files = cursor.fetchall()

            # Combine and deduplicate
            files_to_delete = {}
            for file_info in old_files + excess_files:
                files_to_delete[file_info[0]] = file_info

            # Check storage size limit
            cursor = conn.execute(
                "SELECT SUM(file_size) FROM image_generations WHERE file_size IS NOT NULL"
            )
            total_size = cursor.fetchone()[0] or 0
            max_size_bytes = self.max_storage_size_mb * 1024 * 1024

            if total_size > max_size_bytes:
                # Delete oldest files until under limit
                cursor = conn.execute(
                    """
                    SELECT id, file_path, file_size 
                    FROM image_generations 
                    WHERE file_path IS NOT NULL
                    ORDER BY timestamp ASC
                """
                )

                current_size = total_size
                for file_info in cursor.fetchall():
                    if current_size <= max_size_bytes:
                        break
                    files_to_delete[file_info[0]] = file_info
                    current_size -= file_info[2] or 0

            # Delete files
            for file_id, file_path, file_size in files_to_delete.values():
                try:
                    if file_path and os.path.exists(file_path):
                        if not dry_run:
                            os.remove(file_path)
                            # Update database to remove file reference
                            conn.execute(
                                "UPDATE image_generations SET file_path = NULL, file_size = NULL WHERE id = ?",
                                (file_id,),
                            )
                        deleted_count += 1
                        deleted_size += file_size or 0
                except Exception as e:
                    errors.append(f"Failed to delete {file_path}: {e}")

            if not dry_run:
                conn.commit()
            conn.close()

        except Exception as e:
            logger.error(f"Cleanup failed: {e}")
            return {"error": str(e)}

        return {
            "dry_run": dry_run,
            "deleted_count": deleted_count,
            "deleted_size_bytes": deleted_size,
            "deleted_size_mb": deleted_size / (1024 * 1024),
            "errors": errors,
        }

    async def _auto_cleanup(self):
        """Automatically cleanup old files if limits are exceeded."""
        try:
            stats = await self.get_statistics()

            # Check if cleanup is needed
            needs_cleanup = (
                stats.get("total_generations", 0) > self.max_count
                or stats.get("total_storage_size_mb", 0) > self.max_storage_size_mb
            )

            if needs_cleanup:
                logger.info("Auto cleanup triggered")
                await self.cleanup_old_files(dry_run=False)

        except Exception as e:
            logger.error(f"Auto cleanup failed: {e}")

    def _row_to_metadata(self, row) -> GenerationMetadata:
        """Convert database row to GenerationMetadata object."""
        return GenerationMetadata(
            id=row[0],
            prompt=row[1],
            timestamp=datetime.fromtimestamp(row[2]),
            parameters=json.loads(row[3]),
            file_path=row[4],
            file_size=row[5],
            success=bool(row[6]),
            error_message=row[7],
            generation_time=row[8],
            model=row[9],
        )


# Global history manager instance
history_manager: Optional[ImageHistoryManager] = None


def get_history_manager() -> ImageHistoryManager:
    """Get the global history manager instance."""
    global history_manager
    if history_manager is None:
        # Check for environment variables to configure storage
        storage_path = os.getenv("IMAGE_STORAGE_PATH")
        max_storage_mb = int(os.getenv("MAX_STORAGE_MB", "1000"))
        max_age_days = int(os.getenv("MAX_AGE_DAYS", "30"))
        max_count = int(os.getenv("MAX_IMAGE_COUNT", "100"))

        history_manager = ImageHistoryManager(
            storage_path=storage_path,
            max_storage_size_mb=max_storage_mb,
            max_age_days=max_age_days,
            max_count=max_count,
        )
    return history_manager
