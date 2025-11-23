"""
Azure Storage test utilities for integration tests.

Provides helper functions to interact with Azurite (local Azure Storage emulator)
for queues, blobs, and tables during integration testing.
"""

from typing import Optional, List, Dict, Any
from azure.storage.queue import QueueServiceClient, QueueClient
from azure.storage.blob import BlobServiceClient
from azure.data.tables import TableServiceClient, TableClient


class StorageTestHelper:
    """Helper class for Azure Storage operations in integration tests."""

    def __init__(
        self,
        connection_string: str = (
            "DefaultEndpointsProtocol=http;"
            "AccountName=devstoreaccount1;"
            "AccountKey=Eby8vdM02xNOcqFlqUwJPLlmEtlCDXJ1OUzFT50uSRZ6IFsuFq2UVErCz4I6tq/K1SZFPTOtr/KBHBeksoGMGw==;"
            "BlobEndpoint=http://127.0.0.1:10000/devstoreaccount1;"
            "QueueEndpoint=http://127.0.0.1:10001/devstoreaccount1;"
            "TableEndpoint=http://127.0.0.1:10002/devstoreaccount1;"
        ),
    ):
        """Initialize with Azurite connection string."""
        self.connection_string = connection_string
        self.queue_service = QueueServiceClient.from_connection_string(connection_string)
        self.blob_service = BlobServiceClient.from_connection_string(connection_string)
        self.table_service = TableServiceClient.from_connection_string(connection_string)

    # Queue operations
    def create_queue(self, queue_name: str) -> QueueClient:
        """Create a test queue."""
        queue_client = self.queue_service.get_queue_client(queue_name)
        queue_client.create_queue()
        return queue_client

    def delete_queue(self, queue_name: str) -> None:
        """Delete a test queue."""
        try:
            queue_client = self.queue_service.get_queue_client(queue_name)
            queue_client.delete_queue()
        except Exception:
            pass  # Queue may not exist

    def send_message(self, queue_name: str, message: str) -> None:
        """Send message to queue."""
        queue_client = self.queue_service.get_queue_client(queue_name)
        queue_client.send_message(message)

    def receive_messages(self, queue_name: str, max_messages: int = 1) -> List[Any]:
        """Receive messages from queue."""
        queue_client = self.queue_service.get_queue_client(queue_name)
        return list(queue_client.receive_messages(max_messages=max_messages))

    def get_queue_length(self, queue_name: str) -> int:
        """Get approximate message count in queue."""
        queue_client = self.queue_service.get_queue_client(queue_name)
        properties = queue_client.get_queue_properties()
        return properties.approximate_message_count

    # Blob operations
    def create_container(self, container_name: str) -> None:
        """Create a test blob container."""
        container_client = self.blob_service.get_container_client(container_name)
        container_client.create_container()

    def delete_container(self, container_name: str) -> None:
        """Delete a test blob container."""
        try:
            container_client = self.blob_service.get_container_client(container_name)
            container_client.delete_container()
        except Exception:
            pass  # Container may not exist

    def upload_blob(self, container_name: str, blob_name: str, data: bytes) -> str:
        """Upload blob and return URL."""
        blob_client = self.blob_service.get_blob_client(container_name, blob_name)
        blob_client.upload_blob(data, overwrite=True)
        return blob_client.url

    def download_blob(self, container_name: str, blob_name: str) -> bytes:
        """Download blob content."""
        blob_client = self.blob_service.get_blob_client(container_name, blob_name)
        return blob_client.download_blob().readall()

    def list_blobs(self, container_name: str) -> List[str]:
        """List all blobs in container."""
        container_client = self.blob_service.get_container_client(container_name)
        return [blob.name for blob in container_client.list_blobs()]

    # Table operations
    def create_table(self, table_name: str) -> TableClient:
        """Create a test table."""
        table_client = self.table_service.create_table_if_not_exists(table_name)
        return table_client

    def delete_table(self, table_name: str) -> None:
        """Delete a test table."""
        try:
            self.table_service.delete_table(table_name)
        except Exception:
            pass  # Table may not exist

    def insert_entity(self, table_name: str, entity: Dict[str, Any]) -> None:
        """Insert entity into table."""
        table_client = self.table_service.get_table_client(table_name)
        table_client.upsert_entity(entity)

    def get_entity(self, table_name: str, partition_key: str, row_key: str) -> Optional[Dict[str, Any]]:
        """Get entity from table."""
        try:
            table_client = self.table_service.get_table_client(table_name)
            return table_client.get_entity(partition_key, row_key)
        except Exception:
            return None

    def query_entities(self, table_name: str, filter_query: Optional[str] = None) -> List[Dict[str, Any]]:
        """Query entities from table."""
        table_client = self.table_service.get_table_client(table_name)
        if filter_query:
            return list(table_client.query_entities(filter_query))
        return list(table_client.query_entities())

    def delete_all_entities(self, table_name: str) -> None:
        """Delete all entities from table."""
        table_client = self.table_service.get_table_client(table_name)
        entities = table_client.query_entities()
        for entity in entities:
            table_client.delete_entity(entity["PartitionKey"], entity["RowKey"])

    # Cleanup operations
    def cleanup_all(self, queues: List[str], containers: List[str], tables: List[str]) -> None:
        """Clean up all test resources."""
        for queue in queues:
            self.delete_queue(queue)
        for container in containers:
            self.delete_container(container)
        for table in tables:
            self.delete_table(table)
