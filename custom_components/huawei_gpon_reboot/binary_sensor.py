import asyncio
import logging
from datetime import timedelta
from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval

from .const import DOMAIN, CONF_ROUTER_IP, CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """Set up the Huawei GPON connectivity sensor."""
    sensor = HuaweiGPONConnectivitySensor(entry)
    async_add_entities([sensor], True)

    interval_seconds = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    scan_interval = timedelta(seconds=interval_seconds)

    async def pinger(now):
        await sensor.async_update_status()

    entry.async_on_unload(
        async_track_time_interval(hass, pinger, scan_interval)
    )

class HuaweiGPONConnectivitySensor(BinarySensorEntity):
    """Representation of a Huawei GPON Router Connectivity Sensor."""

    _attr_has_entity_name = True

    def __init__(self, entry: ConfigEntry):
        self._entry = entry
        config = entry.data
        self._router_ip = config[CONF_ROUTER_IP]
        
        self._attr_name = "Status"
        self._attr_unique_id = f"huawei_gpon_status_{self._router_ip}"
        self._attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
        self._is_online = False

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"huawei_gpon_{self._router_ip}")},
            name="Huawei GPON Router",
            manufacturer="Huawei",
            model="EchoLife HG8245Q2",
            configuration_url=f"http://{self._router_ip}"
        )

    @property
    def is_on(self) -> bool:
        """Return true if the router is online and reachable."""
        return self._is_online

    async def async_update_status(self) -> None:
        """Check router availability using system ping command."""
        try:
            process = await asyncio.create_subprocess_exec(
                'ping', '-c', '1', '-W', '2', self._router_ip,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL
            )
            await process.wait()
            
            new_state = (process.returncode == 0)
            if new_state != self._is_online:
                self._is_online = new_state
                self.async_write_ha_state()
                
        except Exception as err:
            _LOGGER.error("Error pinging Huawei GPON router: %s", err)
            if self._is_online:
                self._is_online = False
                self.async_write_ha_state()
