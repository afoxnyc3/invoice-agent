# Pydantic models for queue messages
from pydantic import BaseModel
from typing import List, Dict

class Attachment(BaseModel):
    name: str
    blob_url: str | None = None

class RawMail(BaseModel):
    message_id: str
    subject: str
    attachments: List[Attachment]

class WorkItem(BaseModel):
    tx_id: str
    vendor: str
    expense_code: str
    schedule_allocation: str
    gl_code: str
    attachments: List[Attachment]

class NotifyPayload(BaseModel):
    title: str
    facts: Dict[str, str]
