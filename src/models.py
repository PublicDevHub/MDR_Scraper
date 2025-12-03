from pydantic import BaseModel, Field
from typing import Optional, Literal, List


class MDRChunk(BaseModel):
    id: str = Field(..., description="Unique ID (e.g., mdr_art_10)")
    source_type: Literal["MDR", "MDCG"] = Field(..., description="Source type")
    title: str = Field(..., description="The Heading")
    content: str = Field(..., description="The full text of the article")
    url: str = Field(..., description="Source URL")

    # Flattened metadata
    chapter: str = Field(..., description="Chapter title, e.g. KAPITEL I")
    valid_from: str = Field(..., description="ISO 8601 Date, e.g. 2025-01-10T00:00:00Z")

    # Vector field
    contentVector: Optional[List[float]] = Field(default=None, description="Embedding vector (3072 dimensions)")
    metadata: Dict[str, str] = Field(..., description="Metadata including chapter and valid_from")

class ComplianceData(BaseModel):
    chunks: list[MDRChunk]
