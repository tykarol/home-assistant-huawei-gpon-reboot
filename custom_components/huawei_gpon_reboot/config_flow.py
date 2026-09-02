import voluptuous as vol
import re
import base64
import aiohttp
import asyncio
import logging
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
import homeassistant.helpers.config_validation as cv

from .const import (
    DOMAIN, CONF_ROUTER_IP, CONF_USERNAME, CONF_PASSWORD, 
    CONF_TIMEOUT, CONF_SCAN_INTERVAL, DEFAULT_TIMEOUT, DEFAULT_SCAN_INTERVAL
)

_LOGGER = logging.getLogger(__name__)

async def validate_input(data: dict) -> None:
    """Validate the user input by attempting a real login to the Huawei router."""
    base_url = f"http://{data[CONF_ROUTER_IP]}"
    timeout = aiohttp.ClientTimeout(total=DEFAULT_TIMEOUT)
    
    global_headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36',
        'Accept-Language': 'pl,en-US;q=0.9,en;q=0.8,pl-PL;q=0.7',
        'Connection': 'keep-alive',
        'DNT': '1'
    }

    password_bytes = data[CONF_PASSWORD].encode('utf-8')
    base64_bytes = base64.b64encode(password_bytes)
    base64_password = base64_bytes.decode('utf-8').strip()
    encoded_password = base64_password.replace('=', '%3D')

    async with aiohttp.ClientSession(cookie_jar=None, headers=global_headers, timeout=timeout) as session:
        try:
            async with session.get(f"{base_url}/") as response:
                await response.text()
                raw_cookies = response.headers.getall('Set-Cookie', [])
            
            cookie_header = "body:Language:english:id=-1"
            for cookie in raw_cookies:
                cookie_header += f"; {cookie.split(';')}"

            headers_xhr = {
                'X-Requested-With': 'XMLHttpRequest', 
                'Referer': f"{base_url}/",
                'Accept': '*/*',
                'Content-Length': '0',
                'Cookie': cookie_header
            }
            async with session.post(f"{base_url}/asp/GetRandCount.asp", headers=headers_xhr, data=b'') as response:
                raw_rand = await response.text()
                login_token = "".join(c for c in raw_rand if c.isalnum())
                if 'Set-Cookie' in response.headers:
                    for cookie in response.headers.getall('Set-Cookie', []):
                        cookie_header += f"; {cookie.split(';')}"

            if not login_token:
                raise InvalidAuth

            payload_string = f"UserName={data[CONF_USERNAME]}&PassWord={encoded_password}&Language=english&x.X_HW_Token={login_token}"
            payload_bytes = payload_string.encode('utf-8')
            
            headers_login = {
                'Content-Type': 'application/x-www-form-urlencoded',
                'Origin': base_url,
                'Referer': f"{base_url}/",
                'Cookie': cookie_header,
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8'
            }
            
            async with session.post(f"{base_url}/login.cgi", data=payload_bytes, headers=headers_login) as response:
                await response.text()
                if 'Set-Cookie' in response.headers:
                    for cookie in response.headers.getall('Set-Cookie', []):
                        cookie_header += f"; {cookie.split(';')}"

            headers_reset = {
                'Referer': f"{base_url}/html/ssmp/reset/reset.asp",
                'Upgrade-Insecure-Requests': '1',
                'Cookie': cookie_header,
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9'
            }
            async with session.get(f"{base_url}/html/ssmp/reset/reset.asp", headers=headers_reset) as response:
                reset_page_text = await response.text()
                
            if not re.search(r'id="hwonttoken" value="([a-f0-9]{32})"', reset_page_text):
                raise InvalidAuth

        except (aiohttp.ClientError, asyncio.TimeoutError):
            raise CannotConnect


class HuaweiGPONConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Huawei GPON Router Reboot."""
    VERSION = 1

    def __init__(self):
        """Initialize flow."""
        self._reconfig_entry = None

    async def async_step_user(self, user_input=None):
        """Handle credentials setup (Initial or Reconfigure)."""
        errors = {}
        if user_input is not None:
            try:
                await validate_input(user_input)
                
                if self._reconfig_entry:
                    self.hass.config_entries.async_update_entry(
                        self._reconfig_entry, data=user_input
                    )
                    await self.hass.config_entries.async_reload(self._reconfig_entry.entry_id)
                    return self.async_abort(reason="reconfigure_successful")
                
                return self.async_create_entry(
                    title=f"Huawei GPON ({user_input[CONF_ROUTER_IP]})", 
                    data=user_input
                )
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        default_ip = "192.168.100.1"
        default_user = "root"
        
        if self._reconfig_entry:
            default_ip = self._reconfig_entry.data.get(CONF_ROUTER_IP, default_ip)
            default_user = self._reconfig_entry.data.get(CONF_USERNAME, default_user)

        DATA_SCHEMA = vol.Schema({
            vol.Required(CONF_ROUTER_IP, default=default_ip): str,
            vol.Required(CONF_USERNAME, default=default_user): str,
            vol.Required(CONF_PASSWORD): vol.All(str, vol.Length(min=1)),
        })

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )

    async def async_step_reconfigure(self, user_input=None):
        """Trigger reconfigure step for credentials."""
        self._reconfig_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        return await self.async_step_user()

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> config_entries.OptionsFlow:
        """Get options flow handler."""
        return HuaweiGPONOptionsFlowHandler()


class HuaweiGPONOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle timers adjustment under the gear icon (Options Flow)."""

    async def async_step_init(self, user_input=None):
        """Manage the standalone options form."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        entry = self.config_entry
        
        current_timeout = entry.options.get(
            CONF_TIMEOUT, entry.data.get(CONF_TIMEOUT, DEFAULT_TIMEOUT)
        )
        current_interval = entry.options.get(
            CONF_SCAN_INTERVAL, entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        )

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Required(CONF_TIMEOUT, default=int(current_timeout)): cv.positive_int,
                vol.Required(CONF_SCAN_INTERVAL, default=int(current_interval)): cv.positive_int,
            }),
        )

class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect to the router."""

class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth credentials."""
