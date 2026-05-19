
import json
from typing import List, Optional
from pydantic import BaseModel, Field

class FileMetadata(BaseModel):
    """
    The 'Smart File' profile. 
    Generated for every single file in the library.
    """
    # 1. Canonical Identity
    original_filename: str
    canonical_name: str
    file_type: str  # pdf, epub, md, etc.
    hash: str
    
    # 2. Curation & Categorization
    primary_category: str
    sub_category: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    
    # 3. The "Soul" (Deep LLM Analysis)
    soul: str = Field(description="The core essence and provocative purpose of the book.")
    hooks: List[str] = Field(description="Specific, spicy insights or 'hooks' extracted from the text.")
    takes: List[str] = Field(description="Unique perspectives or 'takes' this book offers on its subject.")
    
    # 4. Structural Intelligence
    specialist_instruction: str = Field(description="Instructions for a specialist agent on how to use this specific file.")
    summary: str
    table_of_contents: List[str] = Field(default_factory=list)
    index_keywords: List[str] = Field(default_factory=list)

    # 5. Pipeline Metadata
    ocr_applied: bool = False
    processed_at: str
    model_used: str

def get_metadata_template():
    """Returns a blank JSON template of the schema for the user to review."""
    return FileMetadata.model_json_schema()

if __name__ == "__main__":
    print(json.dumps(get_metadata_template(), indent=2))
