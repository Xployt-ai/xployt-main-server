from typing import Optional, Dict, Any, List
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
    file_path: str
    line: int
    description: str
    vulnerability: str
    severity: str
    confidence_level: str

class VulnerabilityCreate(VulnerabilityBase):
    scan_id: str

class VulnerabilityInDB(VulnerabilityBase):
    id: str
    scan_id: str

class Vulnerability(VulnerabilityBase):
    id: str
    scan_id: str

    class Config:
        from_attributes = True 

# --- Scan Collections ---

class ScanCollectionCreate(BaseModel):
    repository_name: str
    scanners: List[str]
    configurations: Dict[str, Any] = Field(default_factory=dict)


class ScanCollection(BaseModel):
    id: str
    user_id: str
    repository_name: str
    scanners: List[str]
    scan_ids: List[str]
    status: str = "pending"
    progress_percent: int = 0
    created_at: datetime = Field(default_factory=datetime.utcnow)
    finished_at: Optional[datetime] = None

    class Config:
        from_attributes = True