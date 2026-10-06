import asyncio
import json
import random
import argparse

import proto.coap_pb2 as coap_pb2
from aiocoap import *

def enum_value(msg, field_name, enum_name):
    """Return the integer for the enum name of a field,
       or None if the field does not exist, is not an enum, or the
       enum does not have a value with the supplied name."""
    field = msg.DESCRIPTOR.fields_by_name.get(field_name,None)
    if field and field.enum_type:
        enum = field.enum_type.values_by_name.get(enum_name,None)
        return enum and enum.number

# device classes aka sensor types can be found here:
# https://developers.home-assistant.io/docs/core/entity/sensor/
#
async def send_update_request(device_id: str, port: int, address: str):
    # 1. Create a client context
    protocol = await Context.create_client_context()

    device = coap_pb2.UpdateDevice()
    device.id = device_id
    device.entities.add(id=1, value=random.randint(19, 25) + random.random()/10)  # temperature
    device.entities.add(id=2, value=random.randint(40, 50))  # humidity
    device.entities.add(id=3, value=random.randint(70, 80))  # battery
    device.entities.add(id=4, value=random.randint(100, 1000))  # light
    device.entities.add(id=5, value=random.randint(0, 1))  # motion
    device.entities.add(id=6, value=random.randint(0, 1))

    payload = device.SerializeToString()

    # 3. Create the PUT request
    # NOTE: The path '/sensors/device001/data' matches your tree structure
    request = Message(code=PUT, payload=payload)
    request.set_request_uri(f"coap://{address}:{port}/device")

    print("Sending request...")

    try:
        # 4. Send and wait for response
        response = await protocol.request(request).response
        print(f"Response Code: {response.code}")
        print(f"Response Payload: {response.payload.decode('utf-8')}")
    except Exception as e:
        print(f"Failed to send request: {e}")

# device classes aka sensor types can be found here:
# https://developers.home-assistant.io/docs/core/entity/sensor/
#
async def send_new_request(device_id: str, port: int, address: str):
    # 1. Create a client context
    protocol = await Context.create_client_context()

    device = coap_pb2.NewDevice()
    device.id = device_id
    device.manufacturer = "Acme Corp"
    device.model = "Model PETA"
    device.fw_version = "1.0.0"
    device.hw_version = "1.0.0"
    # device.entities.add(id=1, name="Temperature", value=random.randint(19, 25) + random.random()/10,
    #     type=enum_value(coap_pb2.NewEntity, 'type', 'ENTITY_TYPE_SENSOR'),
    #     sub_type="temperature",
    #     unit="°C"
    # )
    # device.entities.add(id=2, name="Humidity", value=random.randint(40, 50),
    #     unit="%",
    #     type=enum_value(coap_pb2.NewEntity, 'type', 'ENTITY_TYPE_SENSOR'),
    #     sub_type="humidity"
    # )
    # device.entities.add(id=3, name="Battery", value=random.randint(70, 80),
    #     unit="%",
    #     type=enum_value(coap_pb2.NewEntity, 'type', 'ENTITY_TYPE_SENSOR'),
    #     sub_type="battery"
    # )
    # device.entities.add(id=4, name="Light", value=random.randint(100, 200),
    #     unit="lx",
    #     type=enum_value(coap_pb2.NewEntity, 'type', 'ENTITY_TYPE_SENSOR'),
    #     sub_type="illuminance"
    # )
    # device.entities.add(id=5, name="Motion", value=random.randint(0, 1),
    #     unit="",
    #     type=enum_value(coap_pb2.NewEntity, 'type', 'ENTITY_TYPE_BINARY'),
    #     sub_type="motion"
    # )
    device.entities.add(id=6, name="Switch", value=random.randint(0, 1),
        unit="",
        type=enum_value(coap_pb2.NewEntity, 'type', 'ENTITY_TYPE_SWITCH'),
        sub_type="switch"
    )

    payload: bytes = device.SerializeToString()
    # 3. Create the PUT request
    # NOTE: The path '/sensors/device001/data' matches your tree structure
    request = Message(code=POST, payload=payload)
    request.set_request_uri(f"coap://{address}:{port}/device")

    print("Sending request...")

    try:
        # 4. Send and wait for response
        response = await protocol.request(request).response
        print(f"Response Code: {response.code}")
        print(f"Response Payload: {response.payload.decode('utf-8')}")
    except Exception as e:
        print(f"Failed to send request: {e}")

async def send_observe_request(device_id: str, port: int, address: str):
    # 1. Create a client context
    protocol = await Context.create_client_context()

    # 3. Create the GET request
    # NOTE: The path '/sensors/device001/data' matches your tree structure
    request = Message(code=GET, observe=0)
    request.set_request_uri(f"coap://{address}:{port}/device/observe?id={device_id}&sensor_id=6")

    print("Sending request...")
    res = coap_pb2.ObserveDeviceResponse()

    try:
        # 4. Send and wait for response
        req = protocol.request(request)
        response = await req.response
        res.ParseFromString(response.payload)

        print(f"Response Code: {response.code}")
        print(f"Response Payload: {res}")

        async for notification in req.observation:
            notis = coap_pb2.ObserveDeviceResponse()
            notis.ParseFromString(notification.payload)
            print(f"Notification: {notis}")

#            req.observation.cancel()
#            break  # Exit after receiving the first notification for demonstration purposes

    except Exception as e:
        print(f"Failed to send request: {e}")

async def main(device_id: str, message_type: str, port: int, address: str):
    print(f"Device ID: {device_id}, Message Type: {message_type}, Port: {port}, Address: {address}")

    if message_type == "observe":
        await send_observe_request(device_id, port, address)
    elif message_type == "update":
        await send_update_request(device_id, port, address)
    elif message_type == "new":
        await send_new_request(device_id, port, address)
    else:
        print(f"Message type '{message_type}' is not implemented yet.")

# Construct the argument parser
ap = argparse.ArgumentParser()

# Add the arguments to the parser
ap.add_argument("-t", "--type", required=True,
   help="Message type (new, update, observe) (default: new)")
ap.add_argument("-d", "--device_id", required=False, default="device001",
   help="Device ID (default: device001)")
ap.add_argument("-p", "--port", required=False, default=5683,
   help="Port number (default: 5683)")
ap.add_argument("-a", "--address", required=False, default="127.0.0.1",
   help="Address (default: 127.0.0.1)")

args = vars(ap.parse_args())

if __name__ == "__main__":
    asyncio.run(main(
        device_id=args['device_id'],
        message_type=args['type'],
        port=args['port'],
        address=args['address']
    ))
