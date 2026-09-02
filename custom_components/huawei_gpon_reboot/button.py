import logging
import re
import base64
import urllib.parse
import asyncio
import aiohttp
from homeassistant.components.button import ButtonEntity
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, CONF_ROUTER_IP, CONF_USERNAME, CONF_PASSWORD, CONF_TIMEOUT, DEFAULT_TIMEOUT

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """Set up the reboot button from a config entry."""
    async_add_entities([HuaweiGPONRebootButton(entry)], True)

class HuaweiGPONRebootButton(ButtonEntity):
    """Representation of a Huawei GPON Router Reboot Button."""

    _attr_has_entity_name = True

    def __init__(self, entry: ConfigEntry):
        self._entry = entry
        config = entry.data
        
        self._router_ip = config[CONF_ROUTER_IP]
        self._username = config[CONF_USERNAME]
        self._raw_password = config.get(CONF_PASSWORD, "")
        
        self._attr_name = "Reboot"
        self._attr_unique_id = f"huawei_gpon_reboot_{self._router_ip}"
        self._attr_icon = "mdi:restart"

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"huawei_gpon_{self._router_ip}")},
            name="Huawei GPON Router",
            manufacturer="Huawei",
            model="EchoLife HG8245Q2",
            configuration_url=f"http://{self._router_ip}"
        )

    async def async_press(self) -> None:
        """Handle the button press to trigger the router reboot."""
        base_url = f"http://{self._router_ip}"
        jar = aiohttp.CookieJar(unsafe=True)
        
        timeout_val = self._entry.options.get(CONF_TIMEOUT, DEFAULT_TIMEOUT)
        timeout = aiohttp.ClientTimeout(total=timeout_val)

        global_headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36',
            'Accept-Language': 'pl,en-US;q=0.9,en;q=0.8,pl-PL;q=0.7',
            'Connection': 'keep-alive',
            'DNT': '1'
        }

        password_bytes = self._raw_password.encode('utf-8')
        base64_bytes = base64.b64encode(password_bytes)
        base64_password = base64_bytes.decode('utf-8').strip()
        encoded_password = base64_password.replace('=', '%3D')

        async with aiohttp.ClientSession(cookie_jar=None, timeout=timeout, headers=global_headers) as session:
            try:
                _LOGGER.debug("Huawei GPON: Step 1 - Initializing session")
                async with session.get(f"{base_url}/") as response:
                    await response.text()
                    raw_cookies = response.headers.getall('Set-Cookie', [])
                
                cookie_header = "body:Language:english:id=-1"
                for cookie in raw_cookies:
                    cookie_header += f"; {cookie.split(';')}"

                _LOGGER.debug("Huawei GPON: Step 2 - Fetching RandCount token")
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

                _LOGGER.debug("Huawei GPON: Step 3 - Logging-in via raw binary payload")
                payload_string = f"UserName={self._username}&PassWord={encoded_password}&Language=english&x.X_HW_Token={login_token}"
                payload_bytes = payload_string.encode('utf-8')
                
                headers_login = {
                    'Content-Type': 'application/x-www-form-urlencoded',
                    'Origin': base_url,
                    'Referer': f"{base_url}/",
                    'Cookie': cookie_header,
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7'
                }
                async with session.post(f"{base_url}/login.cgi", data=payload_bytes, headers=headers_login) as response:
                    await response.text()
                    if 'Set-Cookie' in response.headers:
                        for cookie in response.headers.getall('Set-Cookie', []):
                            cookie_header += f"; {cookie.split(';')}"

                _LOGGER.debug("Huawei GPON: Step 4 - Fetching reset page to scrape onttoken")
                headers_reset = {
                    'Referer': f"{base_url}/html/ssmp/reset/reset.asp",
                    'Upgrade-Insecure-Requests': '1',
                    'Cookie': cookie_header,
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8'
                }
                async with session.get(f"{base_url}/html/ssmp/reset/reset.asp", headers=headers_reset) as response:
                    reset_page_text = await response.text()
                    
                match = re.search(r'id="hwonttoken" value="([a-f0-9]{32})"', reset_page_text)
                if not match:
                    _LOGGER.error("Huawei GPON: Failed to find onttoken on the reset page. Session rejected.")
                    return
                reset_token = match.group(1)

                _LOGGER.debug("Huawei GPON: Step 5 - Submitting final reboot trigger")
                reboot_url = f"{base_url}/html/ssmp/reset/set.cgi?x=InternetGatewayDevice.X_HW_DEBUG.SMP.DM.ResetBoard&RequestFile=html/ssmp/reset/reset.asp"
                reboot_string = f"x.X_HW_Token={reset_token}"
                reboot_bytes = reboot_string.encode('utf-8')
                
                headers_reboot = {
                    'Content-Type': 'application/x-www-form-urlencoded',
                    'Origin': base_url,
                    'Referer': f"{base_url}/html/ssmp/reset/reset.asp",
                    'Upgrade-Insecure-Requests': '1',
                    'Cookie': cookie_header
                }
                
                async with session.post(reboot_url, data=reboot_bytes, headers=headers_reboot) as response:
                    _LOGGER.info("Huawei GPON: Reboot command sent successfully! Status: %s", response.status)

            except asyncio.TimeoutError:
                _LOGGER.error("Huawei GPON: Connection timed out during execution.")
            except Exception as err:
                _LOGGER.error("Huawei GPON: Exception during execution: %s", err)
