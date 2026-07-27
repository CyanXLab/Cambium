"""
Memory Governance endpoints (SSGM Framework).

Full SSGM pipeline: quarantine → validate → promote.
These endpoints expose the governance system to the frontend,
allowing users to inspect and manually validate/reject/promote memories.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict, Any

from app.config import DB_PATH
from app.logging_config import get_logger
from app.exceptions import NotFoundError, ValidationError

log = get_logger(__name__)
router = APIRouter(prefix="/api/v2/governance", tags=["governance"])


@router.get("/stats")
async def governance_stats(user_id: str = "default"):
    """Get memory governance statistics.

    Returns counts of memories in each lifecycle stage:
      quarantined, validated, rejected, promoted
    Plus audit_entries total.
    """
    from app import memory_governance
    return memory_governance.get_stats(DB_PATH, user_id=user_id)


@router.get("/quarantine")
async def governance_list_quarantine(
    user_id: str = "default",
    status: str = "quarantined",
    limit: int = 50,
):
    """List memories in quarantine (or filtered by status).

    status: quarantined | validated | rejected | promoted
    """
    from app import memory_governance
    from app.db_utils import safe_connect
    conn = safe_connect(DB_PATH)
    conn.row_factory = __import__("sqlite3").Row
    rows = conn.execute(
        "SELECT * FROM memory_quarantine WHERE user_id=? AND status=? "
        "ORDER BY created_at DESC LIMIT ?",
        (user_id, status, limit)
    ).fetchall()
    conn.close()
    return {"items": [dict(r) for r in rows], "status_filter": status}


@router.get("/audit")
async def governance_audit_log(
    user_id: str = "default",
    limit: int = 100,
):
    """Get the governance audit log.

    Every governance action (quarantine/validate/reject/promote/contradiction)
    is recorded here.
    """
    from app import memory_governance
    return {"entries": memory_governance.get_audit_log(DB_PATH, user_id=user_id, limit=limit)}


class ValidateRequest(BaseModel):
    verdict: str  # "validate" | "reject"
    confidence: float = 0.8
    notes: str = ""


@router.post("/quarantine/{qid}/validate")
async def governance_validate(qid: str, req: ValidateRequest, user_id: str = "default"):
    """Manually validate or reject a quarantined memory.

    verdict: "validate" to promote to main store, "reject" to discard.
    """
    from app import memory_governance
    if req.verdict not in ("validate", "reject"):
        raise ValidationError("verdict must be 'validate' or 'reject'")

    success = memory_governance.validate_quarantine(
        DB_PATH, qid, req.verdict,
        confidence=req.confidence,
        validated_by="user",
        notes=req.notes,
    )
    if not success:
        raise NotFoundError(f"Quarantined memory {qid} not found")

    log.info("governance.user_validated", extra={
        "qid": qid, "verdict": req.verdict, "user_id": user_id,
    })
    return {"status": "validated" if req.verdict == "validate" else "rejected", "qid": qid}


@router.post("/quarantine/{qid}/promote")
async def governance_promote(qid: str):
    """Promote a validated memory to the main store.

    Only memories with status='validated' can be promoted.
    """
    from app import memory_governance
    result = memory_governance.promote_to_main(DB_PATH, qid)
    if not result:
        raise NotFoundError(f"Validated memory {qid} not found (must be validated first)")
    log.info("governance.promoted", extra={"qid": qid})
    return {"status": "promoted", "qid": qid, "main_memory": result}


@router.post("/validate-batch")
async def governance_validate_batch(limit: int = 10, user_id: str = "default"):
    """Trigger LLM batch validation of quarantined memories.

    Uses the memory_api_config to call the LLM for coherence-checking.
    Returns counts of validated/rejected.
    """
    from app import memory_governance
    from app.main import get_memory_api_config
    import httpx

    api_cfg = get_memory_api_config()
    if not api_cfg.get("api_key"):
        raise ValidationError("Memory API not configured — set API key in settings")

    async with httpx.AsyncClient(timeout=30.0) as c:
        result = await memory_governance.validate_quarantine_batch(
            DB_PATH, user_id=user_id,
            http_client=c, api_cfg=api_cfg,
            batch_size=limit,
        )
    log.info("governance.batch_validated", extra=result)
    return result


@router.post("/promote-all")
async def governance_promote_all(user_id: str = "default"):
    """Promote all validated memories to the main store."""
    from app import memory_governance
    result = memory_governance.promote_all_validated(DB_PATH, user_id=user_id)
    log.info("governance.batch_promoted", extra=result)
    return result


@router.post("/auto-validate")
async def governance_auto_validate(user_id: str = "default"):
    """Run rule-based auto-validation on quarantined memories.

    High-importance + clear category → auto-validate.
    Low-importance + trivial content → auto-reject.
    Everything else → keep for LLM validation.
    """
    from app import memory_governance
    result = memory_governance.auto_validate_by_rules(DB_PATH, user_id=user_id)
    log.info("governance.auto_validated", extra=result)
    return result
