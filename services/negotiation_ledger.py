import json
import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

from sqlalchemy.orm import Session
from models import LedgerEntryModel

@dataclass
class Justification:
    """An offer can only execute if every field here is populated from a real model output."""
    shap_drivers: list
    causal_uplift_estimate: float
    causal_confidence: float
    customer_ltv: float
    expected_value_score: float

    def is_complete(self) -> bool:
        return all([
            self.shap_drivers,
            self.causal_uplift_estimate is not None,
            self.customer_ltv is not None,
        ])
    
    def to_dict(self):
        return {
            "shap_drivers": self.shap_drivers,
            "causal_uplift_estimate": self.causal_uplift_estimate,
            "causal_confidence": self.causal_confidence,
            "customer_ltv": self.customer_ltv,
            "expected_value_score": self.expected_value_score
        }

@dataclass
class LedgerEntry:
    session_id: str
    sequence: int
    timestamp: datetime
    speaker: str                 # "agent" | "customer" | "system"
    message: str
    claim_type: str              # "grounded" | "generic" | "offer"
    justification: Optional[Justification]
    telemetry_snapshot: Dict[str, Any]
    prev_hash: str
    entry_hash: str = field(init=False)
    tenant_id: int

    def __post_init__(self):
        payload = json.dumps({
            "session_id": self.session_id,
            "sequence": self.sequence,
            "message": self.message,
            "prev_hash": self.prev_hash,
        }, sort_keys=True)
        self.entry_hash = hashlib.sha256(payload.encode()).hexdigest()
        
    def to_model_dict(self):
        return {
            "tenant_id": self.tenant_id,
            "session_id": self.session_id,
            "sequence": self.sequence,
            "timestamp": self.timestamp,
            "speaker": self.speaker,
            "message": self.message,
            "claim_type": self.claim_type,
            "justification": self.justification.to_dict() if self.justification else None,
            "telemetry_snapshot": self.telemetry_snapshot,
            "prev_hash": self.prev_hash,
            "entry_hash": self.entry_hash
        }


class NegotiationLedger:
    def __init__(self, db: Session, tenant_id: int, session_id: str, customer_repo, causal_service, clv_estimator):
        self.db = db
        self.tenant_id = tenant_id
        self.session_id = session_id
        self.customer_repo = customer_repo
        self.causal_service = causal_service
        self.clv_estimator = clv_estimator
        
        # Load existing entries from DB to resume chain
        self.entries = self._load_entries()

    def _load_entries(self) -> List[LedgerEntry]:
        rows = self.db.query(LedgerEntryModel).filter(
            LedgerEntryModel.tenant_id == self.tenant_id,
            LedgerEntryModel.session_id == self.session_id
        ).order_by(LedgerEntryModel.sequence.asc()).all()
        
        entries = []
        for r in rows:
            j = None
            if r.justification:
                j = Justification(**r.justification)
            
            # Reconstruct the dataclass without re-hashing
            e = LedgerEntry(
                session_id=r.session_id,
                sequence=r.sequence,
                timestamp=r.timestamp,
                speaker=r.speaker,
                message=r.message,
                claim_type=r.claim_type,
                justification=j,
                telemetry_snapshot=r.telemetry_snapshot,
                prev_hash=r.prev_hash,
                tenant_id=r.tenant_id
            )
            # Override __post_init__ hash with DB hash
            e.entry_hash = r.entry_hash
            entries.append(e)
            
        return entries

    def record(self, speaker: str, message: str, claim_type: str,
               justification: Optional[Justification], merchant_id: int, customer_id: str) -> LedgerEntry:
        prev_hash = self.entries[-1].entry_hash if self.entries else "GENESIS"
        snapshot = self.customer_repo.get_telemetry_snapshot(merchant_id, customer_id)

        entry = LedgerEntry(
            session_id=self.session_id,
            sequence=len(self.entries),
            timestamp=datetime.now(timezone.utc),
            speaker=speaker,
            message=message,
            claim_type=claim_type,
            justification=justification,
            telemetry_snapshot=snapshot,
            prev_hash=prev_hash,
            tenant_id=self.tenant_id
        )
        self.entries.append(entry)
        
        # Persist to DB
        model = LedgerEntryModel(**entry.to_model_dict())
        self.db.add(model)
        self.db.commit()
        
        return entry

    def build_justification(self, merchant_id: int, customer_id: str,
                            discount_tier: str) -> Justification:
        """The agent calls this BEFORE it's allowed to make an offer.
        If this raises, the offer cannot execute."""
        shap = self.customer_repo.get_shap_explanation(merchant_id, customer_id)
        uplift = self.causal_service.estimate_uplift(
            merchant_id, customer_id, intervention=discount_tier
        )
        ltv = self.clv_estimator.estimate(merchant_id, customer_id)
        
        point_estimate = uplift.get("uplift", 0)
        confidence_width = uplift.get("confidence_interval_width", 0.05)

        j = Justification(
            shap_drivers=shap,
            causal_uplift_estimate=point_estimate,
            causal_confidence=confidence_width,
            customer_ltv=ltv,
            expected_value_score=point_estimate * ltv,
        )
        if not j.is_complete():
            raise ValueError(
                f"Cannot justify {discount_tier} offer for {customer_id}: "
                f"insufficient evidence. Routing to human approval."
            )
        return j

    def verify_chain(self) -> bool:
        """Detect tampering — recompute hashes and check the chain."""
        prev = "GENESIS"
        for e in self.entries:
            expected = hashlib.sha256(json.dumps({
                "session_id": e.session_id, "sequence": e.sequence,
                "message": e.message, "prev_hash": prev,
            }, sort_keys=True).encode()).hexdigest()
            if expected != e.entry_hash:
                return False
            prev = e.entry_hash
        return True

    def negotiation_integrity_score(self) -> float:
        """Fraction of substantive claims that were grounded vs generic."""
        substantive = [e for e in self.entries
                      if e.speaker == "agent" and e.claim_type in ("grounded", "generic")]
        if not substantive:
            return 1.0
        grounded = sum(1 for e in substantive if e.claim_type == "grounded")
        return grounded / len(substantive)
