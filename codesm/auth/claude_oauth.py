"""Claude Pro/Max OAuth authentication"""

import httpx
import time
from typing import Optional
from .credentials import CredentialStore


class ClaudeOAuth:
    """Handle Claude Pro/Max OAuth flow"""

    # Use console.anthropic.com endpoint (like opencode does)
    TOKEN_URL = "https://console.anthropic.com/v1/oauth/token"
    CLIENT_ID = "9d1c250a-e61b-44d9-88ed-5944d1962f5e"
    REDIRECT_URI = "https://console.anthropic.com/oauth/code/callback"

    def __init__(self):
        self.credential_store = CredentialStore()

    async def exchange_code(self, code: str, code_verifier: str, state: str, create_api_key: bool = True) -> dict:
        """Exchange authorization code for access token.
        
        The code parameter should be in the format "code#state" as pasted by the user.
        If create_api_key is True, will also create an API key using the OAuth token.
        """
        # Parse code#state format (user pastes "authcode#verifierstate")
        if "#" in code:
            actual_code, actual_state = code.split("#", 1)
        else:
            actual_code = code
            actual_state = state

        async with httpx.AsyncClient() as client:
            # Send as JSON (not form-urlencoded) - this is what opencode does
            json_data = {
                "grant_type": "authorization_code",
                "code": actual_code,
                "state": actual_state,
                "redirect_uri": self.REDIRECT_URI,
                "client_id": self.CLIENT_ID,
                "code_verifier": code_verifier,
            }

            try:
                response = await client.post(
                    self.TOKEN_URL,
                    json=json_data,
                    headers={"Content-Type": "application/json"},
                )
                if response.status_code != 200:
                    error_text = response.text
                    # Check if response is HTML (e.g., Cloudflare challenge page)
                    if error_text.strip().startswith("<!DOCTYPE") or "<html" in error_text[:100]:
                        return {"success": False, "error": f"Server returned HTML (status {response.status_code}). This may be a Cloudflare challenge - try again later."}
                    # Try to parse JSON error
                    try:
                        error_json = response.json()
                        error_msg = error_json.get("error_description") or error_json.get("error") or error_json.get("message") or str(error_json)
                        return {"success": False, "error": error_msg[:200]}
                    except Exception:
                        # Truncate raw text error
                        return {"success": False, "error": error_text[:200]}
                
                token_data = response.json()
                access_token = token_data.get("access_token")
                
                if create_api_key and access_token:
                    # Create an API key using the OAuth token
                    # This works for third-party apps since it creates a real API key
                    api_key_result = await self._create_api_key(client, access_token)
                    if api_key_result["success"]:
                        self.save_api_key(api_key_result["api_key"])
                        return {"success": True, "data": {"api_key": api_key_result["api_key"]}}
                    else:
                        return api_key_result
                else:
                    # Save OAuth credentials directly (only works for whitelisted apps)
                    self._save_credentials(token_data)
                    return {"success": True, "data": token_data}
                    
            except Exception as e:
                return {"success": False, "error": str(e)[:200]}

    async def _create_api_key(self, client: httpx.AsyncClient, access_token: str) -> dict:
        """Create an API key using OAuth access token."""
        try:
            response = await client.post(
                "https://api.anthropic.com/api/oauth/claude_cli/create_api_key",
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {access_token}",
                },
            )
            if response.status_code == 200:
                data = response.json()
                api_key = data.get("raw_key")
                if api_key:
                    return {"success": True, "api_key": api_key}
                return {"success": False, "error": "No API key in response"}
            else:
                try:
                    error_json = response.json()
                    error_msg = error_json.get("error", {}).get("message") or str(error_json)
                    return {"success": False, "error": f"Failed to create API key: {error_msg[:150]}"}
                except:
                    return {"success": False, "error": f"Failed to create API key: {response.status_code}"}
        except Exception as e:
            return {"success": False, "error": f"Error creating API key: {str(e)[:150]}"}

    async def refresh_token(self, refresh_token: str) -> dict:
        """Refresh an expired access token."""
        async with httpx.AsyncClient() as client:
            json_data = {
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "client_id": self.CLIENT_ID,
            }

            try:
                response = await client.post(
                    self.TOKEN_URL,
                    json=json_data,
                    headers={"Content-Type": "application/json"},
                )
                if response.status_code == 200:
                    token_data = response.json()
                    self._save_credentials(token_data)
                    return {"success": True, "data": token_data}
                else:
                    try:
                        error_json = response.json()
                        error_msg = error_json.get("error_description") or error_json.get("error") or str(error_json)
                        return {"success": False, "error": error_msg[:200]}
                    except Exception:
                        return {"success": False, "error": response.text[:200]}
            except Exception as e:
                return {"success": False, "error": str(e)[:200]}

    def _save_credentials(self, token_data: dict):
        """Save OAuth credentials"""
        expires_in = token_data.get("expires_in", 3600)
        self.credential_store.set("anthropic", {
            "auth_type": "oauth",
            "access_token": token_data.get("access_token"),
            "refresh_token": token_data.get("refresh_token"),
            "expires_at": int(time.time() * 1000) + (expires_in * 1000),
        })

    def save_api_key(self, api_key: str):
        """Save API key"""
        self.credential_store.set("anthropic", {
            "auth_type": "api_key",
            "api_key": api_key,
        })

    def get_credentials(self) -> Optional[dict]:
        """Get stored credentials"""
        return self.credential_store.get("anthropic")

    def is_authenticated(self) -> bool:
        """Check if authenticated"""
        return self.credential_store.is_authenticated("anthropic")

    def get_api_key(self) -> Optional[str]:
        """Get API key or access token for API calls"""
        creds = self.get_credentials()
        if creds:
            if creds.get("auth_type") == "api_key":
                return creds.get("api_key")
            elif creds.get("auth_type") == "oauth":
                return creds.get("access_token")
        return None

    def is_token_expired(self) -> bool:
        """Check if the OAuth token is expired"""
        creds = self.get_credentials()
        if not creds or creds.get("auth_type") != "oauth":
            return True
        expires_at = creds.get("expires_at", 0)
        return int(time.time() * 1000) >= expires_at
