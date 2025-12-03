from pydantic import BaseModel, Field
from typing import Dict, Optional, Literal

class MDRChunk(BaseModel):
    id: str = Field(..., description="Unique ID (e.g., mdr_art_10)")
    source_type: Literal["MDR", "MDCG"] = Field(..., description="Source type")
    title: str = Field(..., description="The Heading")
    content: str = Field(..., description="The full text of the article")
    url: str = Field(..., description="Source URL")
    metadata: Dict[str, str] = Field(..., description="Metadata including chapter and valid_from")

class ComplianceData(BaseModel):
    chunks: list[MDRChunk]
