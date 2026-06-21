from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Optional
from datetime import datetime

class CustomerInferenceRequest(BaseModel):
    merchant_id: int        = Field(..., gt=0)
    user_id:     str        = Field(..., min_length=1, max_length=64)
    recency_days: float     = Field(..., ge=0, le=3650)
    frequency:   int        = Field(..., ge=0)
    monetary_value: float   = Field(..., ge=0)
    session_failures: int   = Field(default=0, ge=0)
    last_seen_at: Optional[datetime] = None

    @field_validator("user_id")
    @classmethod
    def user_id_no_whitespace(cls, v: str) -> str:
        if v != v.strip():
            raise ValueError("user_id must not contain leading or trailing whitespace")
        return v

    @model_validator(mode="after")
    def monetary_requires_frequency(self) -> "CustomerInferenceRequest":
        if self.monetary_value > 0 and self.frequency == 0:
            raise ValueError(
                "monetary_value > 0 with frequency = 0 is physically impossible"
            )
        return self

class CustomerInferenceResponse(BaseModel):
    user_id:           str
    churn_probability: float = Field(..., ge=0, le=1)
    segment:           str
    shap_values:       dict  # Feature name -> contribution score
    generated_at:      datetime
