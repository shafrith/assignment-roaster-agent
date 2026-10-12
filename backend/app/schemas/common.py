"""Shared Pydantic base models: camelCase wire format and pagination."""

from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

T = TypeVar("T")


class CamelModel(BaseModel):
    """Base schema serialized as camelCase JSON, populatable by field name or ORM attributes."""

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
    )


class Paginated(CamelModel, Generic[T]):
    """A page of results: ``{items, total, page, pageSize}``."""

    items: list[T]
    total: int = Field(ge=0)
    page: int = Field(ge=1)
    page_size: int = Field(ge=1)
