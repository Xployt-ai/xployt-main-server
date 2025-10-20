from typing import List, Optional, Literal
from pydantic import BaseModel


class FileItem(BaseModel):
    name: str
    type: Literal["file", "folder"]
    children: Optional[List["FileItem"]] = None


class FileContentResponse(BaseModel):
    code: str
    language: str


FileItem.model_rebuild()


