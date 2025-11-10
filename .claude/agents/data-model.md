# Data Model Agent

## Purpose
Generate Azure Table Storage entities, repositories, and data access patterns for invoice processing.

## Capabilities
- Create Pydantic models for data validation
- Generate repository classes with CRUD operations
- Implement query patterns for Table Storage
- Create seed data scripts
- Handle data migrations

## Data Models

### VendorMaster Entity
```python
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class VendorMaster(BaseModel):
    """Vendor lookup table entity."""
    partition_key: str = Field(default="Vendor")
    row_key: str  # vendor_name_lower (e.g., "adobe_com")
    vendor_name: str
    expense_dept: str
    allocation_schedule_number: str
    gl_code: str
    billing_party: str
    active: bool = True
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
```

### InvoiceTransaction Entity
```python
class InvoiceTransaction(BaseModel):
    """Transaction audit log entity."""
    partition_key: str  # YYYYMM format
    row_key: str  # ULID
    transaction_id: str
    vendor_name: str
    sender_email: str
    expense_dept: Optional[str]
    allocation_schedule_number: Optional[str]
    gl_code: Optional[str]
    billing_party: Optional[str]
    status: str  # processed|unknown|error
    blob_url: str
    error_message: Optional[str]
    processed_at: datetime
    created_at: datetime = Field(default_factory=datetime.utcnow)
```

## Repository Pattern

### Base Repository
```python
from azure.data.tables import TableServiceClient, TableEntity
from typing import Dict, List, Optional
import os

class BaseRepository:
    """Base class for Table Storage operations."""

    def __init__(self, table_name: str):
        conn_str = os.environ["AzureWebJobsStorage"]
        self.table_client = TableServiceClient.from_connection_string(
            conn_str
        ).get_table_client(table_name)

    def create(self, entity: BaseModel) -> Dict:
        """Insert entity into table."""
        return self.table_client.create_entity(
            entity.dict(exclude_none=True)
        )

    def get(self, partition_key: str, row_key: str) -> Optional[Dict]:
        """Get entity by keys."""
        try:
            return self.table_client.get_entity(
                partition_key=partition_key,
                row_key=row_key
            )
        except:
            return None

    def update(self, entity: BaseModel) -> Dict:
        """Update existing entity."""
        return self.table_client.update_entity(
            entity.dict(exclude_none=True),
            mode="merge"
        )

    def query(self, filter_query: str, max_results: int = 100) -> List[Dict]:
        """Query entities with filter."""
        return list(self.table_client.query_entities(
            filter=filter_query,
            results_per_page=max_results
        ))
```

### VendorMasterRepository
```python
class VendorMasterRepository(BaseRepository):
    """Repository for vendor operations."""

    def __init__(self):
        super().__init__("VendorMaster")

    def find_by_email_domain(self, email: str) -> Optional[VendorMaster]:
        """Find vendor by email domain."""
        domain = email.split("@")[-1].replace(".", "_")
        entity = self.get("Vendor", domain)
        return VendorMaster(**entity) if entity else None

    def find_by_name(self, vendor_name: str) -> Optional[VendorMaster]:
        """Find vendor by name (fuzzy)."""
        clean_name = vendor_name.lower().replace(" ", "_")
        entity = self.get("Vendor", clean_name)
        return VendorMaster(**entity) if entity else None

    def get_active_vendors(self) -> List[VendorMaster]:
        """Get all active vendors."""
        entities = self.query("PartitionKey eq 'Vendor' and active eq true")
        return [VendorMaster(**e) for e in entities]

    def bulk_insert(self, vendors: List[VendorMaster]) -> None:
        """Batch insert vendors."""
        for vendor in vendors:
            self.create(vendor)
```

### InvoiceTransactionRepository
```python
from ulid import ULID
from datetime import datetime

class InvoiceTransactionRepository(BaseRepository):
    """Repository for transaction operations."""

    def __init__(self):
        super().__init__("InvoiceTransactions")

    def create_transaction(self, data: Dict) -> InvoiceTransaction:
        """Create new transaction with ULID."""
        transaction = InvoiceTransaction(
            partition_key=datetime.utcnow().strftime("%Y%m"),
            row_key=str(ULID()),
            transaction_id=str(ULID()),
            **data
        )
        self.create(transaction)
        return transaction

    def get_by_month(self, year: int, month: int) -> List[InvoiceTransaction]:
        """Get transactions for a specific month."""
        partition = f"{year:04d}{month:02d}"
        entities = self.query(f"PartitionKey eq '{partition}'")
        return [InvoiceTransaction(**e) for e in entities]

    def get_by_status(self, status: str, limit: int = 100) -> List[InvoiceTransaction]:
        """Get transactions by status."""
        entities = self.query(
            f"status eq '{status}'",
            max_results=limit
        )
        return [InvoiceTransaction(**e) for e in entities]

    def get_daily_summary(self) -> Dict:
        """Get today's processing summary."""
        today = datetime.utcnow().strftime("%Y%m")
        entities = self.query(f"PartitionKey eq '{today}'")

        summary = {
            "total": len(entities),
            "processed": sum(1 for e in entities if e["status"] == "processed"),
            "unknown": sum(1 for e in entities if e["status"] == "unknown"),
            "errors": sum(1 for e in entities if e["status"] == "error")
        }
        return summary
```

## Queue Message Models

```python
class RawMailMessage(BaseModel):
    """Message for raw-mail queue."""
    id: str = Field(default_factory=lambda: str(ULID()))
    sender: str
    subject: str
    blob_url: str
    received_at: datetime

class EnrichedMessage(BaseModel):
    """Message for to-post queue."""
    id: str
    vendor_name: str
    expense_dept: Optional[str]
    allocation_schedule_number: Optional[str]
    gl_code: Optional[str]
    billing_party: Optional[str]
    blob_url: str
    status: str  # enriched|unknown

class NotifyMessage(BaseModel):
    """Message for notify queue."""
    type: str  # success|unknown|error
    message: str
    details: Dict
    transaction_id: str
```

## Seed Data Script

```python
# scripts/seed_vendors.py
import csv
from shared.repositories import VendorMasterRepository
from shared.models import VendorMaster

def seed_vendors(csv_path: str):
    """Load vendors from CSV."""
    repo = VendorMasterRepository()

    with open(csv_path, 'r') as f:
        reader = csv.DictReader(f)
        vendors = []

        for row in reader:
            vendor = VendorMaster(
                row_key=row['email_domain'].replace('.', '_'),
                vendor_name=row['vendor_name'],
                expense_dept=row['expense_dept'],
                allocation_schedule_number=row['allocation_schedule'],
                gl_code=row['gl_code'],
                billing_party=row['billing_party']
            )
            vendors.append(vendor)

        repo.bulk_insert(vendors)
        print(f"Loaded {len(vendors)} vendors")

if __name__ == "__main__":
    seed_vendors("data/vendors.csv")
```

## Sample Vendor Data (CSV)
```csv
vendor_name,email_domain,expense_dept,allocation_schedule,gl_code,billing_party
Adobe Inc,adobe.com,IT,MONTHLY,6100,Company HQ
Microsoft Corporation,microsoft.com,IT,ANNUAL,6100,Company HQ
Amazon Web Services,aws.amazon.com,IT,MONTHLY,6110,Company HQ
Salesforce,salesforce.com,SALES,ANNUAL,6200,Company HQ
Zoom,zoom.us,IT,MONTHLY,6120,Company HQ
```

## Success Criteria
- Models validate all required fields
- Repositories handle CRUD operations
- Queries are efficient (<1 second)
- Seed script loads initial data
- Error handling on all operations