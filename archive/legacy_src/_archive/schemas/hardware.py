from uuid import uuid4

from pydantic import BaseModel, Field


class Source(BaseModel):
    uri: str
    page: int
    chunk_id: str


class SVGCoordinate(BaseModel):
    x: float
    y: float
    width: float = 20.0
    height: float = 20.0


class VisualComponentProperties(BaseModel):
    designator: str
    value: str
    coordinates: SVGCoordinate | None = None
    connected_to: list[str] = []


class BaseEntity(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    type: str
    label: str
    source: Source
    embedding_text: str | None = None
    properties: dict = {}


class Edge(BaseModel):
    source_id: str
    target_id: str
    relationship: str = "CONNECTED_TO"
    properties: dict = {}
