from dataclasses import asdict, dataclass
from typing import Iterable

from .config import get_settings


@dataclass(frozen=True)
class ConnectorDescriptor:
    name: str
    category: str
    status: str
    required_env: tuple[str, ...]
    capability: str


CONNECTORS: tuple[ConnectorDescriptor, ...] = (
    ConnectorDescriptor("Workday", "hris", "planned", ("WORKDAY_BASE_URL", "WORKDAY_CLIENT_ID"), "employee profile and requisition sync"),
    ConnectorDescriptor("BambooHR", "hris", "planned", ("BAMBOOHR_SUBDOMAIN", "BAMBOOHR_API_KEY"), "lightweight employee directory sync"),
    ConnectorDescriptor("Greenhouse", "ats", "planned", ("GREENHOUSE_API_KEY",), "candidate and interview stage sync"),
    ConnectorDescriptor("Lever", "ats", "planned", ("LEVER_API_KEY",), "candidate opportunity sync"),
    ConnectorDescriptor("Feishu", "collaboration", "planned", ("FEISHU_APP_ID", "FEISHU_APP_SECRET"), "message and calendar approval workflow"),
    ConnectorDescriptor("DingTalk", "collaboration", "planned", ("DINGTALK_APP_KEY", "DINGTALK_APP_SECRET"), "message and approval workflow"),
    ConnectorDescriptor("Enterprise WeChat", "collaboration", "planned", ("WECHAT_CORP_ID", "WECHAT_SECRET"), "message and approval workflow"),
    ConnectorDescriptor("Outlook", "calendar", "planned", ("MS_GRAPH_CLIENT_ID", "MS_GRAPH_TENANT_ID"), "mail and calendar execution"),
    ConnectorDescriptor("Google Calendar", "calendar", "planned", ("GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET"), "calendar execution"),
)


def connector_inventory() -> list[dict[str, object]]:
    settings = get_settings()
    configured_env = set(settings.configured_connector_env)
    inventory: list[dict[str, object]] = []
    for connector in CONNECTORS:
        missing = [name for name in connector.required_env if name not in configured_env]
        status = "configured" if not missing else connector.status
        item = asdict(connector)
        item["status"] = status
        item["missing_env"] = missing
        inventory.append(item)
    return inventory


def configured_connector_names() -> Iterable[str]:
    return [item["name"] for item in connector_inventory() if item["status"] == "configured"]
