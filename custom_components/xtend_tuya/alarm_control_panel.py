"""Support for Tuya Alarm."""

from __future__ import annotations

from enum import StrEnum

from tuya_sharing import CustomerDevice, Manager

from homeassistant.components.alarm_control_panel import (
    AlarmControlPanelEntity,
    AlarmControlPanelEntityDescription,
    AlarmControlPanelEntityFeature,
    #AlarmControlPanelState,    #Activate somewhere around 2025.8
)
from homeassistant.const import (
    Platform,
    STATE_ALARM_ARMED_AWAY,     #Disable somewhere around 2025.8
    STATE_ALARM_ARMED_HOME,     #Disable somewhere around 2025.8
    STATE_ALARM_DISARMED,       #Disable somewhere around 2025.8
    STATE_ALARM_TRIGGERED,      #Disable somewhere around 2025.8
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .util import (
    merge_device_descriptors
)

from .multi_manager.multi_manager import XTConfigEntry
from .base import TuyaEntity
from .const import TUYA_DISCOVERY_NEW, DPType


class Mode(StrEnum):
    """Alarm modes."""

    ARM = "arm"
    DISARMED = "disarmed"
    HOME = "home"
    SOS = "sos"


STATE_MAPPING: dict[str, str] = {
    #Mode.DISARMED: AlarmControlPanelState.DISARMED,    #Activate somewhere around 2025.8
    #Mode.ARM: AlarmControlPanelState.ARMED_AWAY,       #Activate somewhere around 2025.8
    #Mode.HOME: AlarmControlPanelState.ARMED_HOME,      #Activate somewhere around 2025.8
    #Mode.SOS: AlarmControlPanelState.TRIGGERED,        #Activate somewhere around 2025.8
    Mode.DISARMED: STATE_ALARM_DISARMED,                #Disable somewhere around 2025.8
    Mode.ARM: STATE_ALARM_ARMED_AWAY,                   #Disable somewhere around 2025.8
    Mode.HOME: STATE_ALARM_ARMED_HOME,                  #Disable somewhere around 2025.8
    Mode.SOS: STATE_ALARM_TRIGGERED,                    #Disable somewhere around 2025.8
}


# All descriptions can be found here:
# https://developer.tuya.com/en/docs/iot/standarddescription?id=K9i5ql6waswzq
ALARM: dict[str, tuple[AlarmControlPanelEntityDescription, ...]] = {
}


async def async_setup_entry(
    hass: HomeAssistant, entry: XTConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Tuya alarm dynamically through Tuya discovery."""
    hass_data = entry.runtime_data

    merged_descriptors = ALARM
    for new_descriptor in entry.runtime_data.multi_manager.get_platform_descriptors_to_merge(Platform.ALARM_CONTROL_PANEL):
        merged_descriptors = merge_device_descriptors(merged_descriptors, new_descriptor)

    @callback
    def async_discover_device(device_map) -> None:
        """Discover and add a discovered Tuya siren."""
        entities: list[TuyaAlarmEntity] = []
        device_ids = [*device_map]
        for device_id in device_ids:
            if device := hass_data.manager.device_map.get(device_id, None):
                if descriptions := merged_descriptors.get(device.category):
                    entities.extend(
                        TuyaAlarmEntity(device, hass_data.manager, description)
                        for description in descriptions
                        if description.key in device.status
                    )
        async_add_entities(entities)

    hass_data.manager.register_device_descriptors("alarm_control", merged_descriptors)
    async_discover_device([*hass_data.manager.device_map])

    entry.async_on_unload(
        async_dispatcher_connect(hass, TUYA_DISCOVERY_NEW, async_discover_device)
    )


class TuyaAlarmEntity(TuyaEntity, AlarmControlPanelEntity):
    """Tuya Alarm Entity."""

    _attr_name = None
    _attr_code_arm_required = False

    def __init__(
        self,
        device: CustomerDevice,
        device_manager: Manager,
        description: AlarmControlPanelEntityDescription,
    ) -> None:
        """Init Tuya Alarm."""
        super().__init__(device, device_manager)
        self.entity_description = description
        self._attr_unique_id = f"{super().unique_id}{description.key}"

        # Determine supported  modes
        if supported_modes := self.find_dpcode(
            description.key, dptype=DPType.ENUM, prefer_function=True
        ):
            if Mode.HOME in supported_modes.range:
                self._attr_supported_features |= AlarmControlPanelEntityFeature.ARM_HOME

            if Mode.ARM in supported_modes.range:
                self._attr_supported_features |= AlarmControlPanelEntityFeature.ARM_AWAY

            if Mode.SOS in supported_modes.range:
                self._attr_supported_features |= AlarmControlPanelEntityFeature.TRIGGER

    @property
    def state(self) -> str | None:
        """Return the state of the device."""
        if not (status := self.device.status.get(self.entity_description.key)):
            return None
        return STATE_MAPPING.get(status)

    def alarm_disarm(self, code: str | None = None) -> None:
        """Send Disarm command."""
        self._send_command(
            [{"code": self.entity_description.key, "value": Mode.DISARMED}]
        )

    def alarm_arm_home(self, code: str | None = None) -> None:
        """Send Home command."""
        self._send_command([{"code": self.entity_description.key, "value": Mode.HOME}])

    def alarm_arm_away(self, code: str | None = None) -> None:
        """Send Arm command."""
        self._send_command([{"code": self.entity_description.key, "value": Mode.ARM}])

    def alarm_trigger(self, code: str | None = None) -> None:
        """Send SOS command."""
        self._send_command([{"code": self.entity_description.key, "value": Mode.SOS}])
