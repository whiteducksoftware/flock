"""Shared link and feedback storage implementations supporting SQLite and Azure Table Storage."""

import logging
import sqlite3
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

import aiosqlite

from flock.webapp.app.services.sharing_models import (
    FeedbackRecord,
    SharedLinkConfig,
)

# Azure Table Storage imports - will be conditionally imported
try:
    from azure.core.exceptions import ResourceExistsError, ResourceNotFoundError
    from azure.data.tables.aio import TableServiceClient
    AZURE_AVAILABLE = True
except ImportError:
    AZURE_AVAILABLE = False
    TableServiceClient = None
    ResourceNotFoundError = None
    ResourceExistsError = None

# Get a logger instance
logger = logging.getLogger(__name__)

class SharedLinkStoreInterface(ABC):
    """Interface for storing and retrieving shared link configurations."""

    @abstractmethod
    async def initialize(self) -> None:
        """Initialize the store (e.g., create tables)."""
        pass

    @abstractmethod
    async def save_config(self, config: SharedLinkConfig) -> SharedLinkConfig:
        """Saves a shared link configuration."""
        pass

    @abstractmethod
    async def get_config(self, share_id: str) -> SharedLinkConfig | None:
        """Retrieves a shared link configuration by its ID."""
        pass

    @abstractmethod
    async def delete_config(self, share_id: str) -> bool:
        """Deletes a shared link configuration by its ID. Returns True if deleted, False otherwise."""
        pass

    # Feedback
    @abstractmethod
    async def save_feedback(self, record: FeedbackRecord):
        """Persist a feedback record."""
        pass

class SQLiteSharedLinkStore(SharedLinkStoreInterface):
    """SQLite implementation for storing and retrieving shared link configurations."""

    def __init__(self, db_path: str):
        """Initialize SQLite store with database path."""
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True) # Ensure directory exists
        logger.info(f"SQLiteSharedLinkStore initialized with db_path: {self.db_path}")

    async def initialize(self) -> None:
        """Initializes the database and creates/updates the table if it doesn't exist."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                # Ensure the table exists with the base schema first
                await db.execute(
                    """
                    CREATE TABLE IF NOT EXISTS shared_links (
                        share_id TEXT PRIMARY KEY,
                        agent_name TEXT NOT NULL,
                        flock_definition TEXT NOT NULL,
                        created_at TEXT NOT NULL
                        /* New columns will be added below if they don't exist */
                    )
                    """
                )

                # Add new columns individually, ignoring errors if they already exist
                new_columns = [
                    ("share_type", "TEXT DEFAULT 'agent_run' NOT NULL"),
                    ("chat_message_key", "TEXT"),
                    ("chat_history_key", "TEXT"),
                    ("chat_response_key", "TEXT")
                ]

                for column_name, column_type in new_columns:
                    try:
                        await db.execute(f"ALTER TABLE shared_links ADD COLUMN {column_name} {column_type}")
                        logger.info(f"Added column '{column_name}' to shared_links table.")
                    except sqlite3.OperationalError as e:
                        if "duplicate column name" in str(e).lower():
                            logger.debug(f"Column '{column_name}' already exists in shared_links table.")
                        else:
                            raise # Re-raise if it's a different operational error

                # Feedback table
                await db.execute(
                    """
                    CREATE TABLE IF NOT EXISTS feedback (
                        feedback_id TEXT PRIMARY KEY,
                        share_id TEXT,
                        context_type TEXT NOT NULL,
                        reason TEXT NOT NULL,
                        expected_response TEXT,
                        actual_response TEXT,
                        flock_name TEXT,
                        agent_name TEXT,
                        flock_definition TEXT,
                        created_at TEXT NOT NULL,
                        FOREIGN KEY(share_id) REFERENCES shared_links(share_id)
                    )
                    """
                )

                await db.commit()
            logger.info(f"Database initialized and shared_links table schema ensured at {self.db_path}")
        except sqlite3.Error as e:
            logger.error(f"SQLite error during initialization: {e}", exc_info=True)
            raise

    async def save_config(self, config: SharedLinkConfig) -> SharedLinkConfig:
        """Saves a shared link configuration to the SQLite database."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    """INSERT INTO shared_links (
                        share_id, agent_name, created_at, flock_definition, 
                        share_type, chat_message_key, chat_history_key, chat_response_key
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        config.share_id,
                        config.agent_name,
                        config.created_at.isoformat(),
                        config.flock_definition,
                        config.share_type,
                        config.chat_message_key,
                        config.chat_history_key,
                        config.chat_response_key,
                    ),
                )
                await db.commit()
            logger.info(f"Saved shared link config for ID: {config.share_id} with type: {config.share_type}")
            return config
        except sqlite3.Error as e:
            logger.error(f"SQLite error saving config for ID {config.share_id}: {e}", exc_info=True)
            raise

    async def get_config(self, share_id: str) -> SharedLinkConfig | None:
        """Retrieves a shared link configuration from SQLite by its ID."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute(
                    """SELECT 
                        share_id, agent_name, created_at, flock_definition, 
                        share_type, chat_message_key, chat_history_key, chat_response_key 
                    FROM shared_links WHERE share_id = ?""",
                    (share_id,)
                ) as cursor:
                    row = await cursor.fetchone()
            if row:
                logger.debug(f"Retrieved shared link config for ID: {share_id}")
                return SharedLinkConfig(
                    share_id=row[0],
                    agent_name=row[1],
                    created_at=row[2], # SQLite stores as TEXT, Pydantic will parse from ISO format
                    flock_definition=row[3],
                    share_type=row[4],
                    chat_message_key=row[5],
                    chat_history_key=row[6],
                    chat_response_key=row[7],
                )
            logger.debug(f"No shared link config found for ID: {share_id}")
            return None
        except sqlite3.Error as e:
            logger.error(f"SQLite error retrieving config for ID {share_id}: {e}", exc_info=True)
            return None # Or raise, depending on desired error handling

    async def delete_config(self, share_id: str) -> bool:
        """Deletes a shared link configuration from SQLite by its ID."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                result = await db.execute("DELETE FROM shared_links WHERE share_id = ?", (share_id,))
                await db.commit()
                deleted_count = result.rowcount
            if deleted_count > 0:
                logger.info(f"Deleted shared link config for ID: {share_id}")
                return True
            logger.info(f"Attempted to delete non-existent shared link config for ID: {share_id}")
            return False
        except sqlite3.Error as e:
            logger.error(f"SQLite error deleting config for ID {share_id}: {e}", exc_info=True)
            return False # Or raise

    # ----------------------- Feedback methods -----------------------

    async def save_feedback(self, record: FeedbackRecord) -> FeedbackRecord:
        """Persist a feedback record to SQLite."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    """INSERT INTO feedback (
                        feedback_id, share_id, context_type, reason,
                        expected_response, actual_response, flock_name, agent_name, flock_definition, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        record.feedback_id,
                        record.share_id,
                        record.context_type,
                        record.reason,
                        record.expected_response,
                        record.actual_response,
                        record.flock_name,
                        record.agent_name,
                        record.flock_definition,
                        record.created_at.isoformat(),
                    ),
                )
                await db.commit()
            logger.info(f"Saved feedback {record.feedback_id} (share={record.share_id})")
            return record
        except sqlite3.Error as e:
            logger.error(f"SQLite error saving feedback {record.feedback_id}: {e}", exc_info=True)
            raise


# ---------------------------------------------------------------------------
# Azure Table + Blob implementation
# ---------------------------------------------------------------------------

try:
    from azure.storage.blob.aio import BlobServiceClient
    AZURE_BLOB_AVAILABLE = True
except ImportError:  # blob SDK not installed
    AZURE_BLOB_AVAILABLE = False
    BlobServiceClient = None

class AzureTableSharedLinkStore(SharedLinkStoreInterface):
    """Store configs in Azure Table; store large flock YAML in Blob Storage."""

    _TABLE_NAME        = "flocksharedlinks"
    _FEEDBACK_TBL_NAME = "flockfeedback"
    _CONTAINER_NAME    = "flocksharedlinkdefs"          # blobs live here
    _PARTITION_KEY     = "shared_links"

    def __init__(self, connection_string: str):
        if not AZURE_AVAILABLE:
            raise ImportError("pip install azure-data-tables")
        if not AZURE_BLOB_AVAILABLE:
            raise ImportError("pip install azure-storage-blob")

        self.connection_string = connection_string
        self.table_svc = TableServiceClient.from_connection_string(connection_string)
        self.blob_svc  = BlobServiceClient.from_connection_string(connection_string)

    # ------------------------------------------------------------------ init
    async def initialize(self) -> None:
        # 1. Azure Tables ----------------------------------------------------
        try:
            await self.table_svc.create_table(self._TABLE_NAME)
            logger.info("Created Azure Table '%s'", self._TABLE_NAME)
        except ResourceExistsError:
            logger.debug("Azure Table '%s' already exists", self._TABLE_NAME)

        try:
            await self.table_svc.create_table(self._FEEDBACK_TBL_NAME)
            logger.info("Created Azure Table '%s'", self._FEEDBACK_TBL_NAME)
        except ResourceExistsError:
            logger.debug("Azure Table '%s' already exists", self._FEEDBACK_TBL_NAME)

        # 2. Blob container --------------------------------------------------
        try:
            await self.blob_svc.create_container(self._CONTAINER_NAME)
            logger.info("Created Blob container '%s'", self._CONTAINER_NAME)
        except ResourceExistsError:
            logger.debug("Blob container '%s' already exists", self._CONTAINER_NAME)

    # ------------------------------------------------------------- save_config
    async def save_config(self, config: SharedLinkConfig) -> SharedLinkConfig:
        """Upload YAML to Blob, then upsert table row containing the blob name."""
        blob_name   = f"{config.share_id}.yaml"
        blob_client = self.blob_svc.get_blob_client(self._CONTAINER_NAME, blob_name)

        # 1. Upload flock_definition (overwrite in case of retry)
        await blob_client.upload_blob(config.flock_definition,
                                      overwrite=True,
                                      content_type="text/yaml")
        logger.debug("Uploaded blob '%s' (%d bytes)",
                     blob_name, len(config.flock_definition.encode()))

        # 2. Persist lightweight record in the table
        tbl_client = self.table_svc.get_table_client(self._TABLE_NAME)
        entity = {
            "PartitionKey": self._PARTITION_KEY,
            "RowKey":       config.share_id,
            "agent_name":   config.agent_name,
            "created_at":   config.created_at.isoformat(),
            "share_type":   config.share_type,
            "chat_message_key":  config.chat_message_key,
            "chat_history_key":  config.chat_history_key,
            "chat_response_key": config.chat_response_key,
            # NEW – just a few bytes, well under 64 KiB
            "flock_blob_name": blob_name,
        }
        await tbl_client.upsert_entity(entity)
        logger.info("Saved shared link %s → blob '%s'", config.share_id, blob_name)
        return config

    # -------------------------------------------------------------- get_config
    async def get_config(self, share_id: str) -> SharedLinkConfig | None:
        tbl_client = self.table_svc.get_table_client(self._TABLE_NAME)
        try:
            entity = await tbl_client.get_entity(self._PARTITION_KEY, share_id)
        except ResourceNotFoundError:
            logger.debug("No config entity for id '%s'", share_id)
            return None

        blob_name   = entity["flock_blob_name"]
        blob_client = self.blob_svc.get_blob_client(self._CONTAINER_NAME, blob_name)
        try:
            blob_bytes = await (await blob_client.download_blob()).readall()
            flock_yaml = blob_bytes.decode()
        except Exception as e:
            logger.error("Cannot download blob '%s' for share_id=%s: %s",
                         blob_name, share_id, e, exc_info=True)
            raise

        return SharedLinkConfig(
            share_id          = share_id,
            agent_name        = entity["agent_name"],
            created_at        = entity["created_at"],
            flock_definition  = flock_yaml,
            share_type        = entity.get("share_type", "agent_run"),
            chat_message_key  = entity.get("chat_message_key"),
            chat_history_key  = entity.get("chat_history_key"),
            chat_response_key = entity.get("chat_response_key"),
        )

    # ----------------------------------------------------------- delete_config
    async def delete_config(self, share_id: str) -> bool:
        tbl_client = self.table_svc.get_table_client(self._TABLE_NAME)
        try:
            entity = await tbl_client.get_entity(self._PARTITION_KEY, share_id)
        except ResourceNotFoundError:
            logger.info("Delete: entity %s not found", share_id)
            return False

        # 1. Remove blob (ignore missing blob)
        blob_name   = entity["flock_blob_name"]
        blob_client = self.blob_svc.get_blob_client(self._CONTAINER_NAME, blob_name)
        try:
            await blob_client.delete_blob(delete_snapshots="include")
            logger.debug("Deleted blob '%s'", blob_name)
        except ResourceNotFoundError:
            logger.warning("Blob '%s' already gone", blob_name)

        # 2. Remove table row
        await tbl_client.delete_entity(self._PARTITION_KEY, share_id)
        logger.info("Deleted shared link %s and its blob", share_id)
        return True

    # -------------------------------------------------------- save_feedback --
    async def save_feedback(self, record: FeedbackRecord) -> FeedbackRecord:
        """Persist a feedback record. If a flock_definition is present, upload it as a blob and
        store only a reference in the table row to avoid oversized entities (64 KiB limit).
        """
        tbl_client = self.table_svc.get_table_client(self._FEEDBACK_TBL_NAME)

        # Core entity fields (avoid dumping the full Pydantic model – too many columns / large value)
        entity: dict[str, Any] = {
            "PartitionKey": "feedback",
            "RowKey":       record.feedback_id,
            "share_id":     record.share_id,
            "context_type": record.context_type,
            "reason":       record.reason,
            "expected_response": record.expected_response,
            "actual_response":   record.actual_response,
            "created_at":   record.created_at.isoformat(),
        }
        if record.flock_name is not None:
            entity["flock_name"] = record.flock_name
        if record.agent_name is not None:
            entity["agent_name"] = record.agent_name

        # ------------------------------------------------------------------ YAML → Blob
        if record.flock_definition:
            blob_name   = f"{record.feedback_id}.yaml"
            blob_client = self.blob_svc.get_blob_client(self._CONTAINER_NAME, blob_name)
            # Overwrite=true so repeated feedback_id uploads (shouldn't happen) won't error
            await blob_client.upload_blob(record.flock_definition,
                                          overwrite=True,
                                          content_type="text/yaml")
            entity["flock_blob_name"] = blob_name  # lightweight reference only

        # ------------------------------------------------------------------ Table upsert
        await tbl_client.upsert_entity(entity)
        logger.info("Saved feedback %s%s",
                    record.feedback_id,
                    f" → blob '{entity['flock_blob_name']}'" if "flock_blob_name" in entity else "")
        return record



# ----------------------- Factory Function -----------------------

def create_shared_link_store(store_type: str | None = None, connection_string: str | None = None) -> SharedLinkStoreInterface:
    """Factory function to create the appropriate shared link store based on configuration.
    
    Args:
        store_type: Type of store to create ("local" for SQLite, "azure-storage" for Azure Table Storage)
        connection_string: Connection string for the store (file path for SQLite, connection string for Azure)
    
    Returns:
        Configured SharedLinkStoreInterface implementation
    """
    import os

    # Get values from environment if not provided
    if store_type is None:
        store_type = os.getenv("FLOCK_WEBAPP_STORE", "local").lower()

    if connection_string is None:
        connection_string = os.getenv("FLOCK_WEBAPP_STORE_CONNECTION", ".flock/shared_links.db")

    if store_type == "local":
        return SQLiteSharedLinkStore(connection_string)
    elif store_type == "azure-storage":
        return AzureTableSharedLinkStore(connection_string)
    else:
        raise ValueError(f"Unsupported store type: {store_type}. Supported types: 'local', 'azure-storage'")
