Global Caché ITach Alternate Platform for Home Assistant
--------------------------------------------------------

This is an alternative to the Home Assistant itach platform written in Python with asyncio rather than C.

It is based on the Home Assistant itech platform and the module ITachIP2IR library (alanfischer/itachip2ir).

The Home Assistant component using the new pyitachip2irasync module which uses the Python asyncio library to send commands to the Global Caché ITach or Flex devices. There is no support for multicast discovery of devices by MAC address.

This platform has only been tested with the Global Caché’ Flex devices. The protocol implenmented is the sendir protocol from iTach API Specification Version 1.5 documented here https://www.globalcache.com/files/docs/API-iTach.pdf.

How to use
----------
To install the platform in Home Assistant
1. Create the directory custom_components under your configuration directory if it does not exist
2. Copy the files into the directory itachpyasync under the custom_components directory
3. Added the itachpyasync pltform under the remote section in your configuration.yaml file, see below

The Home Assistant platform works the same way as the itach platform documented here https://www.home-assistant.io/integrations/itach/, except the platform name is itachpyasync

    remote:
    - platform: itach
        host: itach023fdc
    ...
License
-------
- MIT License
