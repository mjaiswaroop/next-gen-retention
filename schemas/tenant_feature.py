from enum import Enum
from pydantic import BaseModel, Field, create_model
from typing import Dict, Any, List

class FeatureType(str, Enum):
    NUMERIC = "numeric"
    CATEGORICAL = "categorical"
    BOOLEAN = "boolean"

class FeatureDefinition(BaseModel):
    name: str = Field(..., description="Exact column name in the CSV")
    dtype: FeatureType
    is_required: bool = False

class TenantSchemaRegistry(BaseModel):
    """
    Data contract defining the exact structure a specific tenant is allowed to upload.
    """
    tenant_id: int
    core_features: List[FeatureDefinition] = []
    custom_features: List[FeatureDefinition] = []

    def build_dynamic_validator(self) -> type[BaseModel]:
        """
        Dynamically compiles a Pydantic model class to validate incoming CSV rows.
        """
        fields: Dict[str, Any] = {}
        for feat in self.core_features + self.custom_features:
            py_type = float if feat.dtype == FeatureType.NUMERIC else str
            if feat.dtype == FeatureType.BOOLEAN:
                py_type = bool
            
            # (Type, Default/Ellipsis)
            fields[feat.name] = (py_type, ... if feat.is_required else None)
            
        return create_model(f"Tenant{self.tenant_id}RowValidator", **fields)
