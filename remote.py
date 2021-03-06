"""Support for iTach IR devices using a Python library."""
import logging
import asyncio

# from .pyitachip2ir.pyitachip2ir import ITachIP2IR
# from .pyitachip2ir import pyitachip2ir
from .pyitachip2irasync import pyitachip2irasync

import voluptuous as vol

from homeassistant.components import remote
from homeassistant.components.remote import (
    ATTR_NUM_REPEATS,
    DEFAULT_NUM_REPEATS,
    PLATFORM_SCHEMA,
)
from homeassistant.const import (
    CONF_DEVICES,
    CONF_HOST,
    CONF_MAC,
    CONF_NAME,
    CONF_PORT,
    DEVICE_DEFAULT_NAME,
)
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

DEFAULT_PORT = 4998
SOCKET_TIMEOUT = 5
DEFAULT_MODADDR = 1
DEFAULT_CONNADDR = 1
DEFAULT_IR_COUNT = 1

CONF_MODADDR = "modaddr"
CONF_CONNADDR = "connaddr"
CONF_COMMANDS = "commands"
CONF_DATA = "data"
CONF_IR_COUNT = "ir_count"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_MAC): cv.string,
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Required(CONF_DEVICES): vol.All(
            cv.ensure_list,
            [
                {
                    vol.Optional(CONF_NAME): cv.string,
                    vol.Optional(CONF_MODADDR): cv.positive_int,
                    vol.Required(CONF_CONNADDR): cv.positive_int,
                    vol.Optional(CONF_IR_COUNT): cv.positive_int,
                    vol.Required(CONF_COMMANDS): vol.All(
                        cv.ensure_list,
                        [
                            {
                                vol.Required(CONF_NAME): cv.string,
                                vol.Required(CONF_DATA): cv.string,
                            }
                        ],
                    ),
                }
            ],
        ),
    }
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the ITach connection and devices."""
    itachip2ir = pyitachip2irasync.ITachIP2IR(
        config.get(CONF_HOST), int(config.get(CONF_PORT)), SOCKET_TIMEOUT
    )

    asyncio.run_coroutine_threadsafe(
        itachip2ir.ready(),
        hass.loop,
    )

    devices = []
    for data in config.get(CONF_DEVICES):
        name = data.get(CONF_NAME)
        modaddr = int(data.get(CONF_MODADDR, DEFAULT_MODADDR))
        connaddr = int(data.get(CONF_CONNADDR, DEFAULT_CONNADDR))
        ir_count = int(data.get(CONF_IR_COUNT, DEFAULT_IR_COUNT))
        cmddatas = {}
        for cmd in data.get(CONF_COMMANDS):
            cmdname = cmd[CONF_NAME].strip()
            if not cmdname:
                cmdname = '""'
            cmddata = cmd[CONF_DATA].strip()
            if not cmddata:
                cmddata = '""'
            cmddatas[cmdname] = cmddata
        itachip2ir.add_device(name, modaddr, connaddr, cmddatas)
        devices.append(ITachIP2IRPyRemote(hass, itachip2ir, name, ir_count))
    async_add_entities(devices, True)
    return True


class ITachIP2IRPyRemote(remote.RemoteEntity):
    """Device that sends commands to an ITachIP2IR device."""

    def __init__(self, hass, itachip2ir, name, ir_count):
        """Initialize device."""
        self.itachip2ir = itachip2ir
        self._power = False
        self._name = name or DEVICE_DEFAULT_NAME
        self._ir_count = ir_count or DEFAULT_IR_COUNT
        self.hass = hass

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._power

    def turn_on(self, **kwargs):
        """Turn the device on."""
        result = asyncio.run_coroutine_threadsafe(
            self.itachip2ir.send(self._name, "ON", self._ir_count), self.hass.loop
        ).result()

        if (not self._power) and result:
            self._power = True

        self.schedule_update_ha_state()
        return result

    def turn_off(self, **kwargs):
        """Turn the device off."""
        result = asyncio.run_coroutine_threadsafe(
            self.itachip2ir.send(self._name, "OFF", self._ir_count), self.hass.loop
        ).result()

        if self._power and result:
            self._power = False

        self.schedule_update_ha_state()
        return result

    def send_command(self, command, **kwargs):
        """Send a command to one device."""
        num_repeats = kwargs.get(ATTR_NUM_REPEATS, DEFAULT_NUM_REPEATS)
        for single_command in command:
            if not asyncio.run_coroutine_threadsafe(
                self.itachip2ir.send(
                    self._name, single_command, self._ir_count * num_repeats
                ),
                self.hass.loop,
            ).result():
                return False
        return True

    async def async_update(self):
        """Update the device."""
        # self.itachip2ir.update()
