from dataclasses import dataclass
from abc import ABC, abstractmethod
import json
import uuid
import httpx
from .config import get_settings


@dataclass
class ProvisionResult:
    username: str
    subscription_url: str | None = None


class PanelAdapter(ABC):
    @abstractmethod
    def health(self) -> bool: ...
    @abstractmethod
    def create_user(self, username: str, traffic_bytes: int, expire_at_epoch: int) -> ProvisionResult: ...
    @abstractmethod
    def delete_user(self, username: str) -> None: ...


class MockAdapter(PanelAdapter):
    def health(self) -> bool:
        return True
    def create_user(self, username: str, traffic_bytes: int, expire_at_epoch: int) -> ProvisionResult:
        return ProvisionResult(username=username, subscription_url=f"https://example.invalid/sub/{username}")
    def delete_user(self, username: str) -> None:
        return None


class MarzbanAdapter(PanelAdapter):
    def __init__(self, base_url: str, username: str, password: str, verify_tls: bool = True):
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password
        self.verify_tls = verify_tls

    def _token(self) -> str:
        with httpx.Client(verify=self.verify_tls, timeout=15) as client:
            r = client.post(f"{self.base_url}/api/admin/token", data={"username": self.username, "password": self.password})
            r.raise_for_status()
            return r.json()["access_token"]

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._token()}"}

    def health(self) -> bool:
        try:
            with httpx.Client(verify=self.verify_tls, timeout=10) as client:
                r = client.get(f"{self.base_url}/api/system", headers=self._headers())
                return r.is_success
        except Exception:
            return False

    def _available_inbounds(self, headers: dict[str, str]) -> dict[str, list[str]]:
        with httpx.Client(verify=self.verify_tls, timeout=15) as client:
            r = client.get(f"{self.base_url}/api/inbounds", headers=headers)
            r.raise_for_status()
            raw = r.json()
        result: dict[str, list[str]] = {}
        for protocol, items in raw.items():
            tags = []
            for item in items or []:
                tag = item.get("tag") if isinstance(item, dict) else str(item)
                if tag:
                    tags.append(tag)
            if tags:
                result[protocol] = tags
        return result

    def create_user(self, username: str, traffic_bytes: int, expire_at_epoch: int) -> ProvisionResult:
        headers = self._headers()
        inbounds = self._available_inbounds(headers)
        vless_inbounds = inbounds.get("vless", [])
        if not vless_inbounds:
            raise RuntimeError("Marzban has no active VLESS inbound")
        payload = {
            "username": username,
            "status": "active",
            "data_limit": traffic_bytes,
            "expire": expire_at_epoch,
            "data_limit_reset_strategy": "no_reset",
            "proxies": {"vless": {"flow": "xtls-rprx-vision"}},
            "inbounds": {"vless": vless_inbounds},
        }
        with httpx.Client(verify=self.verify_tls, timeout=20) as client:
            r = client.post(f"{self.base_url}/api/user", json=payload, headers=headers)
            r.raise_for_status()
            data = r.json()
        return ProvisionResult(username=username, subscription_url=data.get("subscription_url"))

    def delete_user(self, username: str) -> None:
        with httpx.Client(verify=self.verify_tls, timeout=20) as client:
            r = client.delete(f"{self.base_url}/api/user/{username}", headers=self._headers())
            if r.status_code not in (200, 204, 404):
                r.raise_for_status()


class XUIAdapter(PanelAdapter):
    def __init__(self, base_url: str, username: str, password: str, inbound_id: int, verify_tls: bool = True):
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password
        self.inbound_id = inbound_id
        self.verify_tls = verify_tls

    def _client(self) -> httpx.Client:
        c = httpx.Client(verify=self.verify_tls, timeout=20, follow_redirects=True)
        r = c.post(f"{self.base_url}/login", data={"username": self.username, "password": self.password})
        r.raise_for_status()
        return c

    def health(self) -> bool:
        try:
            with self._client() as c:
                return c.get(f"{self.base_url}/panel/api/inbounds/list").is_success
        except Exception:
            return False

    def create_user(self, username: str, traffic_bytes: int, expire_at_epoch: int) -> ProvisionResult:
        settings = {
            "clients": [{
                "id": str(uuid.uuid4()),
                "email": username,
                "limitIp": 0,
                "totalGB": traffic_bytes,
                "expiryTime": expire_at_epoch * 1000,
                "enable": True,
                "tgId": "",
                "subId": uuid.uuid4().hex[:16],
                "reset": 0,
            }]
        }
        with self._client() as c:
            r = c.post(f"{self.base_url}/panel/api/inbounds/addClient", json={"id": self.inbound_id, "settings": json.dumps(settings)})
            r.raise_for_status()
            data = r.json()
            if not data.get("success", True):
                raise RuntimeError(data.get("msg") or "3x-ui addClient failed")
        return ProvisionResult(username=username)

    def delete_user(self, username: str) -> None:
        raise NotImplementedError("3x-ui deletion requires stored client UUID")


def get_adapter() -> PanelAdapter:
    s = get_settings()
    kind = s.panel_kind.lower().strip()
    if kind == "marzban":
        return MarzbanAdapter(s.panel_base_url, s.panel_username, s.panel_password, s.panel_verify_tls)
    if kind in {"xui", "3x-ui", "sanaei"}:
        return XUIAdapter(s.panel_base_url, s.panel_username, s.panel_password, s.xui_inbound_id, s.panel_verify_tls)
    return MockAdapter()
