"""ORM models package.

Import all models here so that:
- Alembic autogenerate can detect them via Base.metadata
- Application code can use a single import path

Add new model modules to the __all__ list as they are created.
"""

from makervault.models.ai_provider_config import AIProviderConfig
from makervault.models.category import Category
from makervault.models.container import Container
from makervault.models.document import Document
from makervault.models.location import Location
from makervault.models.part import Part
from makervault.models.part_alias import PartAlias
from makervault.models.part_document import PartDocument
from makervault.models.project import Project
from makervault.models.project_document import ProjectDocument
from makervault.models.stock_item import StockItem
from makervault.models.stock_item_document import StockItemDocument

__all__ = [
    "AIProviderConfig",
    "Category",
    "Container",
    "Document",
    "Location",
    "Part",
    "PartAlias",
    "PartDocument",
    "Project",
    "ProjectDocument",
    "StockItem",
    "StockItemDocument",
]
