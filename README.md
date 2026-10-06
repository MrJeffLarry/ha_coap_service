# Home Assistant CoAP Server

This Home Assistant integration runs a CoAP server for devices to register
themselves and send sensor updates. The server listens on all network
interfaces (`0.0.0.0`) using the port configured in the integration (suggested
default: `5683`). It uses UDP and exposes the resources described below.

## Configure Home Assistant

Add **CoAP Server** from Home Assistant's Integrations page and choose a port.
Devices must be able to reach Home Assistant at that port.

By default, the server accepts unencrypted `coap://` traffic. To require
encrypted `coaps://` traffic, enable DTLS and configure a PSK identity and key.
DTLS requires the optional `DTLSSocket` package and its native build
prerequisites:

```bash
apt-get install -y autoconf automake libtool build-essential
pip install DTLSSocket
```

When DTLS is enabled the server uses the configured port for CoAPS; clients
must use the same port and matching PSK identity/key. The server then accepts
DTLS only, not plain CoAP. Protect the PSK and use a trusted network, especially
when using unencrypted CoAP.

## CoAP API

Device registration and updates use binary Protocol Buffer messages, not JSON.
The authoritative message definitions are in
[`proto/coap.proto`](proto/coap.proto); generated Python examples are in
[`test_client.py`](test_client.py).

| Resource | Method | Request | Result |
| --- | --- | --- | --- |
| `/whoami` | GET | None | UTF-8 text describing the protocol and request peer. |
| `/device` | POST | Serialized `NewDevice` | Registers a device or refreshes its metadata/entities in Home Assistant. Successful requests return `2.04 Changed`. |
| `/device` | PUT | Serialized `UpdateDevice` | Updates values for known entities. Returns `2.04 Changed` for a known device, or `4.04 Not Found` otherwise. |
| `/device/observe?id=<device-id>&sensor_id=<entity-id>` | GET | Empty payload; add the CoAP Observe option to subscribe | Returns the current selected entity value and sends subsequent updates as Observe notifications. Without Observe, this is a one-time read. |

### Registration payload

POST a serialized `NewDevice` message. Set its `id`, and include each entity's
numeric `id`, numeric `value`, `type`, and optional `name`, `sub_type`, and
`unit`. Device metadata (`manufacturer`, `model`, `fw_version`, and
`hw_version`) is optional. The `type` enum values are
`ENTITY_TYPE_SENSOR`, `ENTITY_TYPE_BINARY_SENSOR`, `ENTITY_TYPE_SWITCH`, and
`ENTITY_TYPE_LIGHT`; `sub_type` should be a Home Assistant device-class value
for sensor, binary sensor, or switch entities.

### Update payload

PUT a serialized `UpdateDevice` message with the device `id` and an `entities`
list of `{id, value}` pairs. Entity IDs must match IDs previously registered
for that device. Unknown entity IDs are ignored; updates do not change entity
metadata.

### Observe payload and notifications

Send a GET with the CoAP Observe option and both query parameters:
`id` identifies the device and `sensor_id` identifies the entity. The initial
response and later notifications are serialized `ObserveDeviceResponse`
messages containing `entities` entries with an `id` and `value`. The server
also sends a refresh notification every 10 seconds while the subscription is
active. Cancel the CoAP observation to unsubscribe.

Example client commands (replace the address and port as needed):

```bash
python test_client.py --type new --device_id device001 --address 127.0.0.1 --port 5683
python test_client.py --type update --device_id device001 --address 127.0.0.1 --port 5683
python test_client.py --type observe --device_id device001 --address 127.0.0.1 --port 5683
```

The example client uses plain CoAP. Use `coaps://` and configure the PSK
credentials in your client when the server has DTLS enabled.

Registered devices are saved in Home Assistant storage and restored when the
integration starts again. Sensor values are updated from incoming PUT messages.

## Development

### Dev container

Open in Dev Containers and run the following commands:

```bash
./scripts/setup
```

Start Home Assistant:

```bash
./scripts/develop
```

### Local

Install dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements_dev.txt
python3 -m pip install -r requirements_common.txt
python3 -m pip install -r requirements_lint.txt
```
