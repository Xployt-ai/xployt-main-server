from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime

class ScanRequest(BaseModel):
    repository_name: str
    scanner_name: str
    configurations: Dict[str, Any] = Field(default_factory=dict)

class ScanBase(BaseModel):
    repository_name: str
    scanner_name: str
    configurations: Dict[str, Any] = Field(default_factory=dict)
    status: str = "pending"
    progress_percent: int = 0
    progress_text: str = "Initializing..."

class ScanCreate(ScanBase):
    user_id: str
    created_at: datetime = Field(default_factory=datetime.utcnow)

class ScanInDB(ScanBase):
    id: str
    user_id: str
    created_at: datetime
    finished_at: Optional[datetime] = None

class Scan(ScanBase):
    id: str
    user_id: str
    created_at: datetime
    finished_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class ScanStatus(BaseModel):
    scan_id: str
    status: str
    progress_percent: int
    progress_text: str

class VulnerabilityBase(BaseModel):
    type: str
    severity: str
    description: str
    location: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)

class VulnerabilityCreate(VulnerabilityBase):
    scan_id: str

class VulnerabilityInDB(VulnerabilityBase):
    id: str
    scan_id: str
    created_at: datetime = Field(default_factory=datetime.utcnow)

class Vulnerability(VulnerabilityBase):
    id: str
    scan_id: str
    created_at: datetime

    class Config:
        from_attributes = True 