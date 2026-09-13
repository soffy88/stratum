"""Expose the shared AgentContract to API clients and agent runtimes."""

from typing import Any

from fastapi import APIRouter, Depends

from stratum.common import jwt_auth
from stratum.services.agent_contract import DEFAULT_AGENT_CONTRACT

router = APIRouter(prefix="/api/v1/agent-contract", tags=["agents"])


@router.get("")
async def get_agent_contract(user_id: str = Depends(jwt_auth)) -> dict[str, Any]:
    return DEFAULT_AGENT_CONTRACT.to_dict()
