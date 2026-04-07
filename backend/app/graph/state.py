from typing import Any, List, Optional, TypedDict


class ContentPlanItem(TypedDict, total=False):
    title: str
    content_type: str
    platform: str
    agent: str
    rationale: str


class DraftItem(TypedDict, total=False):
    id: str
    agent_name: str
    content_type: str
    title: str
    body: str
    platform: str
    status: str


class GraphState(TypedDict, total=False):
    workspace_id: str
    brand_profile: dict
    memory_snippets: List[str]
    trends: List[dict]
    content_plan: List[ContentPlanItem]
    drafts: List[DraftItem]
    cycle_id: Optional[str]
    approval_mode: bool
    awaiting_approval: bool
    summary: dict
    errors: List[str]
