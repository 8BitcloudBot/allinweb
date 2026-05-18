from dataclasses import dataclass, field
from typing import List, Dict, Any
from enum import Enum


class NodeType(str, Enum):
    RECIPE = "Recipe"
    INGREDIENT = "Ingredient"
    CATEGORY = "Category"
    COOKING_STEP = "CookingStep"


class RelationType(str, Enum):
    REQUIRES = "REQUIRES"
    BELONGS_TO_CATEGORY = "BELONGS_TO_CATEGORY"
    CONTAINS_STEP = "CONTAINS_STEP"
    SIMILAR_TO = "SIMILAR_TO"
    SUBSTITUTE_FOR = "SUBSTITUTE_FOR"


VALID_RELATION_TYPES = {r.value for r in RelationType}


@dataclass
class GraphNode:
    node_id: str
    labels: List[str]
    name: str
    properties: Dict[str, Any] = field(default_factory=dict)


@dataclass
class GraphRelation:
    start_node_id: str
    end_node_id: str
    relation_type: str
    properties: Dict[str, Any] = field(default_factory=dict)
