import asyncio
import json
import random
import argparse

from aiocoap import *

# device classes aka sensor types can be found here:
# https://developers.home-assistant.io/docs/core/entity/sensor/
#
async def send_update_request(device_id: str, port: int, address: str):
    # 1. Create a client context
    protocol = await Context.create_client_context()

    # 2. Define the exact payload that matches your server expectations
    payload = {
        "id": device_id,
        "sensors": [
            {"id": 1, "value": random.randint(19, 25) + random.random()/10},  # temperature
            {"id": 2, "value": random.randint(40, 50)},  # humidity
            {"id": 3, "value": random.randint(70, 80)},  # battery
            {"id": 4, "value": random.randint(0, 1)},  # motion
        ],
    }

    # 3. Create the PUT request
    # NOTE: The path '/sensors/device001/data' matches your tree structure
    request = Message(code=PUT, payload=json.dumps(payload).encode("utf-8"))
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

    # 2. Define the exact payload that matches your server expectations
    payload = {
        "id": "device001",
        "manufacturer": "Acme Corp",
        "model": "Model PETA",
        "fw_version": "1.0.0",
        "hw_version": "1.0.0",
        "sensors": [
            {"id": 1, "name": "Temperature", "unit": "°C", "type": "sensor", "sub_type": "temperature", "value": random.randint(19, 25) + random.random()/10},
            {"id": 2, "name": "Humidity", "unit": "%", "type": "sensor", "sub_type": "humidity", "value": random.randint(40, 50)},
            {"id": 3, "name": "Battery", "unit": "%", "type": "sensor", "sub_type": "battery", "value": random.randint(70, 80)},
            {"id": 4, "name": "Light",  "unit": "lx", "type": "sensor", "sub_type": "illuminance", "value": random.randint(100, 200)},
            {"id": 5, "name": "Motion",  "unit": "", "type": "binary", "sub_type": "motion", "value": random.randint(0, 1)},
            {"id": 6, "name": "Switch",  "unit": "", "type": "switch", "sub_type": "switch", "value": random.randint(0, 1)},
        ],
    }

    # 3. Create the PUT request
    # NOTE: The path '/sensors/device001/data' matches your tree structure
    request = Message(code=POST, payload=json.dumps(payload).encode("utf-8"))
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

    try:
        # 4. Send and wait for response
        req = protocol.request(request)
        response = await req.response
        print(f"Response Code: {response.code}")
        print(f"Response Payload: {response.payload.decode('utf-8')}")

        async for notification in req.observation:
            print(f"Notification: {notification.payload.decode('utf-8')}")

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
