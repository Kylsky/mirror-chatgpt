from dataclasses import dataclass
from typing import List, Optional, Any
from datetime import datetime

@dataclass
class ProjectData:
    data: List[Any]
    object: str

@dataclass
class OrgSettings:
    disable_user_api_keys: bool
    threads_ui_visibility: str
    usage_dashboard_visibility: str

@dataclass
class OrgData:
    created: int
    description: str
    geography: Any
    groups: List[Any]
    id: str
    is_default: bool
    is_scale_tier_authorized_purchaser: Any
    is_scim_managed: bool
    name: str
    object: str
    parent_org_id: Any
    personal: bool
    projects: ProjectData
    role: str
    settings: OrgSettings
    title: str

@dataclass
class Orgs:
    data: List[OrgData]
    object: str

@dataclass
class Me:
    amr: List[Any]
    created: int
    email: str
    groups: List[Any]
    has_payg_project_spend_limit: bool
    id: str
    mfa_flag_enabled: bool
    name: str
    object: str
    orgs: Orgs
    phone_number: Optional[str]
    picture: str

# Headers that should be ignored when forwarding requests
IGNORE_HEADERS = {
    "cf-warp-tag-id",
    "cf-visitor",
    "cf-ray",
    "cf-request-id",
    "cf-worker",
    "cf-access-client-id",
    "cf-access-client-device-type",
    "cf-access-client-device-model",
    "cf-access-client-device-name",
    "cf-access-client-device-brand",
    "cf-connecting-ip",
    "cf-ipcountry",
    "x-real-ip",
    "x-forwarded-for",
    "x-forwarded-proto",
    "x-forwarded-port",
    "x-forwarded-host",
    "x-forwarded-server",
    "cdn-loop",
    "remote-host",
    "x-frame-options",
    "x-xss-protection",
    "x-content-type-options",
    "content-security-policy",
    "host",
    "cookie",
    "connection",
    "content-length",
    "content-encoding",
    "x-middleware-prefetch",
    "x-nextjs-data",
    "x-forwarded-uri",
    "x-forwarded-path",
    "x-forwarded-method",
    "x-forwarded-protocol",
    "x-forwarded-scheme",
    "authorization",
    "referer",
    "origin",
}

def filter_header(header: str) -> bool:
    return header.lower() in IGNORE_HEADERS