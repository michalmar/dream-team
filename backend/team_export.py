"""
Utilities for exporting team definitions.

Rationale for location:
- Keep transformation logic out of route handlers (main.py) and data access (database.py)
- Make it easy to unit test and reuse across APIs (e.g., download, share, backups)
"""
from typing import Dict, Any, List
import os
from datetime import datetime, timezone


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _pick_str(d: Dict[str, Any], key: str, default: str = "") -> str:
    v = d.get(key, default)
    return str(v) if v is not None else default


def _pick_bool(d: Dict[str, Any], key: str, default: bool = False) -> bool:
    v = d.get(key, default)
    if isinstance(v, bool):
        return v
    # Coerce common truthy/falsey strings
    if isinstance(v, str):
        return v.lower() in ("1", "true", "yes", "y", "on")
    if isinstance(v, (int, float)):
        return bool(v)
    return default


def _shape_agent(agent: Dict[str, Any]) -> Dict[str, Any]:
    """Return an agent object matching the schema. Only include known fields.
    Required: input_key, type, name, icon
    Optional: model_name, use_mcp, use_bing_grounding, system_message, description,
              use_rag, index_name, index_endpoint, coding_tools
    """
    original_type = _pick_str(agent, "type", "Custom")
    # Normalize type to only 'MagenticOne' and 'Custom'
    normalized_type = "MagenticOne" if original_type == "MagenticOne" else "Custom"
    shaped: Dict[str, Any] = {
        "input_key": _pick_str(agent, "input_key"),
        "type": normalized_type,
        "name": _pick_str(agent, "name"),
        "icon": _pick_str(agent, "icon", "Terminal"),
    }
    # Optional fields - include only if present in input to avoid adding noise
    if "model_name" in agent:
        shaped["model_name"] = _pick_str(agent, "model_name")
    if "use_bing_grounding" in agent:
        shaped["use_bing_grounding"] = _pick_bool(agent, "use_bing_grounding")
    if "system_message" in agent:
        shaped["system_message"] = _pick_str(agent, "system_message")
    if "description" in agent:
        shaped["description"] = _pick_str(agent, "description")
    # Set flags based on the original (pre-normalized) type regardless of input values
    shaped["use_rag"] = original_type == "RAG"
    shaped["use_mcp"] = original_type == "CustomMCP"
    if "index_name" in agent:
        shaped["index_name"] = _pick_str(agent, "index_name")
    # index_endpoint logic: if use_rag is true, prefer env var; otherwise use provided value if present
    env_endpoint = os.getenv("AZURE_SEARCH_SERVICE_ENDPOINT")
    if shaped["use_rag"] and env_endpoint:
        shaped["index_endpoint"] = env_endpoint
    elif "index_endpoint" in agent:
        shaped["index_endpoint"] = _pick_str(agent, "index_endpoint")
    # coding_tools logic: true only for MagenticOne Coder, false otherwise
    agent_name = _pick_str(agent, "name")
    shaped["coding_tools"] = (normalized_type == "MagenticOne" and agent_name == "Coder")
    return shaped


def _shape_starting_task(task: Dict[str, Any]) -> Dict[str, Any]:
    shaped: Dict[str, Any] = {
        "id": _pick_str(task, "id"),
        "name": _pick_str(task, "name"),
        "prompt": _pick_str(task, "prompt"),
        "created": _pick_str(task, "created", _iso_now()),
        "creator": _pick_str(task, "creator", "system"),
        "logo": _pick_str(task, "logo", "Circle")
    }
    return shaped


def convert_team_for_download(team: Dict[str, Any]) -> Dict[str, Any]:
    """Shape/filter a team object for download to match MACAE-team-template schema.

    - Ensures required fields exist with safe defaults
    - Filters to known schema properties
    - Preserves optional fields when present
    """
    agents_in: List[Dict[str, Any]] = team.get("agents", []) or []
    starting_tasks_in: List[Dict[str, Any]] = team.get("starting_tasks", []) or []

    shaped: Dict[str, Any] = {
        # Required
        "id": _pick_str(team, "id", _pick_str(team, "team_id")),
        "team_id": _pick_str(team, "team_id", _pick_str(team, "id")),
        "name": _pick_str(team, "name"),
        "status": _pick_str(team, "status", "visible"),
        "created": _pick_str(team, "created", _iso_now()),
        "created_by": _pick_str(team, "created_by", "system"),
        "agents": [_shape_agent(a) for a in agents_in],
    }

    # Optional top-level fields
    if "protected" in team:
        shaped["protected"] = _pick_bool(team, "protected", False)
    else:
        shaped["protected"] = False

    if "description" in team:
        shaped["description"] = _pick_str(team, "description")
    if "logo" in team:
        shaped["logo"] = _pick_str(team, "logo")
    if "plan" in team:
        shaped["plan"] = _pick_str(team, "plan")
    if starting_tasks_in:
        shaped["starting_tasks"] = [_shape_starting_task(t) for t in starting_tasks_in]
    else:
        # include empty array to keep the shape predictable
        shaped["starting_tasks"] = []

    return shaped

