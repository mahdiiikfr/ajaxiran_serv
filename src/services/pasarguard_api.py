import aiohttp
import logging
from typing import Optional, List, Dict, Any

from config import PASARGUARD_BASE_URL, PASARGUARD_USERNAME, PASARGUARD_PASSWORD

logger = logging.getLogger(__name__)

class PasarGuardAPI:
    def __init__(self):
        self.base_url = PASARGUARD_BASE_URL.rstrip('/')
        self.username = PASARGUARD_USERNAME
        self.password = PASARGUARD_PASSWORD
        self.token = None

    async def _get_token(self) -> str:
        url = f"{self.base_url}/api/admin/token"
        data = {
            "username": self.username,
            "password": self.password
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(url, data=data) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    self.token = result.get("access_token")
                    return self.token
                else:
                    logger.error(f"Failed to get token: {await resp.text()}")
                    raise Exception("Failed to authenticate with PasarGuard")

    async def _request(self, method: str, endpoint: str, **kwargs):
        if not self.token:
            await self._get_token()

        url = f"{self.base_url}{endpoint}"
        headers = kwargs.get("headers", {})
        headers["Authorization"] = f"Bearer {self.token}"
        kwargs["headers"] = headers

        async with aiohttp.ClientSession() as session:
            async with session.request(method, url, **kwargs) as resp:
                if resp.status == 401: # Token expired
                    await self._get_token()
                    headers["Authorization"] = f"Bearer {self.token}"
                    kwargs["headers"] = headers
                    async with session.request(method, url, **kwargs) as retry_resp:
                        if retry_resp.status in (200, 201):
                            return await retry_resp.json()
                        text = await retry_resp.text()
                        logger.error(f"API Error ({retry_resp.status}): {text}")
                        raise Exception(f"API Error: {text}")
                elif resp.status in (200, 201):
                    return await resp.json()
                else:
                    text = await resp.text()
                    logger.error(f"API Error ({resp.status}): {text}")
                    raise Exception(f"API Error: {text}")

    async def get_groups(self):
        return await self._request("GET", "/api/groups")

    async def get_group_by_name(self, name: str) -> Optional[int]:
        groups = await self.get_groups()
        for group in groups:
            if group.get('name') == name:
                return group.get('id')
        return None

    async def create_user(self, username: str, data_limit: int, expire_duration: int, group_ids: List[int], note: str = ""):
        # Group IDs format expected: list of dict with 'id'
        groups = [{"id": group_id} for group_id in group_ids] if group_ids else []
        payload = {
            "username": username,
            "data_limit": data_limit, # bytes
            "expire_duration": expire_duration, # seconds
            "status": "active",
            "note": note,
            "group_ids": groups
        }
        return await self._request("POST", "/api/user", json=payload)

    async def create_admin(self, username: str, password: str, is_sudo: bool = False, role_id: int = 3, data_limit: int = 0):
        # We can pass data_limit for operators to assign them a volume limit in panel
        payload = {
            "username": username,
            "password": password,
            "is_sudo": is_sudo,
            "role_id": role_id, "data_limit": data_limit
        }
        return await self._request("POST", "/api/admin", json=payload)

    async def modify_admin_data_limit(self, username: str, additional_bytes: int):
        # Fetch current admin data
        admins = await self._request("GET", "/api/admins")
        target_admin = None
        for admin in admins:
            if admin.get('username') == username:
                target_admin = admin
                break

        if not target_admin:
            raise Exception("Admin not found")

        current_limit = target_admin.get('data_limit', 0)
        new_limit = current_limit + additional_bytes

        # We need the username to modify.
        return await self._request("PUT", f"/api/admin/{username}", json={"data_limit": new_limit})
