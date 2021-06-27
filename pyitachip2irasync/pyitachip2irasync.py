"""
Control an itach ip2ir gateway using aysncio
"""
from ctypes import *
import os
import fnmatch
import sys
import logging

# import socket
import asyncio

_LOGGER = logging.getLogger(__name__)

TIMEOUT = 5


class IRCommand:
    def addcommand(self, device, name, data):
        self.name = name

        _LOGGER.debug("Adding command %s", name)

        hex = data.split(" ")
        words = []
        for value in hex:
            words.append(int(value, 16))

        if len(words) < 4:
            _LOGGER.error(
                "Cannot add command %s for device %s data length must be greather than 4",
                name,
                device,
            )
            return False

        if words[0] != 0:
            _LOGGER.error(
                "Cannot add command %s for device %s first digit must be zero (0000)",
                name,
                device,
            )
            return False

        self.frequency = int(1000000 / (float(words[1]) * 0.241246))
        self.repeatPairOffset = words[2]

        length = (words[2] + words[3]) * 2
        cmdLength = len(words) - 4
        if cmdLength != length:
            _LOGGER.error(
                "Cannot add command %s for device %s length does not match, expected %d found %d",
                name,
                device,
                length,
                cmdLength,
            )
            return False

        self.command = words[4:]
        return True

    def getgccommand(self, modaddr, connaddr, count):
        scstring = "sendir,{}:{},1,{},{},{}{}\r"

        pulses = ""
        for t in self.command:
            pulses += "," + str(t)

        scstring = scstring.format(
            modaddr,
            connaddr,
            self.frequency,
            count,
            (self.repeatPairOffset * 2 + 1),
            pulses,
        )
        return scstring

    def dump(self):
        _LOGGER.debug(
            "%s - freq=%f, repeatPairOffset=%d, command=%s",
            self.name,
            self.frequency,
            self.repeatPairOffset,
            self.command,
        )


class IRDevice:
    def add_device(self, name, modaddr, connaddr, cmddata):
        self.name = name
        self.modaddr = modaddr
        self.connaddr = connaddr
        self.commands = {}

        failed = 0

        _LOGGER.debug("Adding commands for device %s", name)
        for cmdName in cmddata:
            ircommand = IRCommand()
            if ircommand.addcommand(name, cmdName, (cmddata[cmdName])):
                self.commands[cmdName] = ircommand
            else:
                failed += 1

        if failed > 0:
            if failed == 1:
                command = "command"
            else:
                command = "commands"

            _LOGGER.error("Could not load %d %s for device %s", failed, command, name)

    def getcommand(self, device, command, count):
        count = count if count > 0 else 1

        _LOGGER.debug(
            "Sending command %s to device %s with count of %d", command, device, count
        )
        if command in self.commands:
            ircmd = self.commands[command]
            gccommand = ircmd.getgccommand(self.modaddr, self.connaddr, count)
            # _LOGGER.debug("%s", gccommand)
            return gccommand
        else:
            _LOGGER.error("Cannot find command %s for device %s", command, device)
            return None

    def dump(self):
        logdev(
            "Device %s - modaddr=%d, connaddr=%d",
            self.name,
            self.modaddr,
            self.connaddr,
        )
        logdev("Commands")
        for cmd in self.commands:
            self.commands[cmd].dump()


class ITachIP2IR(object):
    def __init__(self, ip, port, timeout):
        self.ip = ip
        self.port = port
        self.devices = {}
        self.connected = False
        self.timeout = timeout

    async def connect(self):
        _LOGGER.debug("Connecting to %s on port %d", self.ip, self.port)
        self.connected = False

        # aw = asyncio.open_connection(self.ip, self.port)
        try:
            self.reader, self.writer = await asyncio.wait_for(
                asyncio.open_connection(self.ip, self.port), self.timeout
            )
        except asyncio.TimeoutError:
            _LOGGER.error(
                "Cannot connect to iTach host %s on port %d, a timeout occurred",
                self.ip,
                self.port,
            )
            return False
        except ConnectionRefusedError:
            _LOGGER.error(
                "Cannot connect to iTach host %s on port %d, connection refused, check host name or IP address",
                self.ip,
                self.port,
            )
            return False
        except:
            _LOGGER.exception(
                "Cannot connect to iTach host %s on port %d", self.ip, self.port
            )
            return False

        _LOGGER.debug(
            "Connected to iTach host %s on port %d",
            self.ip,
            self.port,
        )
        self.connected = True
        return True

    async def close(self):
        _LOGGER.debug(
            "Closing socket to %s on port %d",
            self.ip,
            self.port,
        )
        self.connected = False

        try:
            self.writer.close()
        except:
            _LOGGER.exception(
                "Cannot close stream %s on port % error {sys.exc_info()}",
                self.ip,
                self.port,
            )
            return

        try:
            await self.writer.wait_closed()
        except:
            _LOGGER.exception(
                "Error while waiting for socket to close %s on port %d",
                self.ip,
                self.port,
            )
            return

    async def sendcmd(self, command):
        if not self.connected:
            if not await self.connect():
                return False

        bytes = bytearray(command, "utf-8")

        _LOGGER.debug(
            "Sending command to %s on port %d",
            self.ip,
            self.port,
        )
        try:
            self.writer.write(bytes)
        except:
            _LOGGER.exception(
                "Failed to send command to %s on port %d", self.ip, self.port
            )
            await self.close()
            return False

        _LOGGER.debug(
            "Checking result %s on port %d",
            self.ip,
            self.port,
        )
        result = bytearray()

        try:
            result = await asyncio.wait_for(self.reader.readuntil(b"\r"), self.timeout)
        except asyncio.exceptions.TimeoutError:
            _LOGGER.error(
                "Receive failed from device %s on port %d, timeout",
                self.ip,
                self.port,
            )
            await self.close()
            return False
        except asyncio.exceptions.IncompleteReadError:
            _LOGGER.error(
                "Receive failed from device %s on port %d, incomplete read, probably disconnected",
                self.ip,
                self.port,
            )
            await self.close()
            return False
        except:
            _LOGGER.exception(
                "Receive failed from device %s on port %d", self.ip, self.port
            )
            await self.close()
            return False

        _LOGGER.debug(
            "Result %s on port %d is '%s'",
            self.ip,
            self.port,
            result,
        )

        if len(result) != 0:
            result = result.decode()
            if "completeir" in result:
                _LOGGER.debug(
                    "Command sent to %s on port %d",
                    self.ip,
                    self.port,
                )
                return True
            elif "ERR" in result:
                parts = result.split(",")
                if len(parts) >= 2:
                    code = parts[1]
                else:
                    code = "unknown"

                _LOGGER.error(
                    "Error sending command to %s on port %d iTach error %s",
                    self.ip,
                    self.port,
                    code,
                )
                return False
            else:
                _LOGGER.warn(
                    "Unexpect result from command to %s on port %d result was '%s'",
                    self.ip,
                    self.port,
                    result,
                )
                return True
        else:
            await self.close()
            return False

        return True

    async def ready(self):
        return await self.connect()

    def add_device(self, name, modaddr, connaddr, cmddata):
        _LOGGER.debug(
            "Adding device %s, modaddr %d, connaddr %d", name, modaddr, connaddr
        )
        device = IRDevice()
        if device.add_device(name, modaddr, connaddr, cmddata) == False:
            return False

        if name in self.devices:
            _LOGGER.error(
                "Device %s already exists, cannot add a second device with the same name",
                name,
            )
            return False

        self.devices[name] = device
        _LOGGER.debug("Add device %s complete", name)
        return True

    async def send(self, name, command, count):
        _LOGGER.debug(
            "Sending command %s on device %s with count %d", command, name, count
        )
        if name in self.devices:
            device = self.devices[name]
            gccommand = device.getcommand(name, command, count)
            if gccommand is not None:
                if await self.sendcmd(gccommand):
                    return True
                else:
                    _LOGGER.debug("Retrying command %s on device %s", command, name)
                    return await self.sendcmd(gccommand)
        else:
            _LOGGER.error("Device has not been added %s", name)

        return False
