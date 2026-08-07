import asyncio
import json
import random

from aiocoap import *

# device classes aka sensor types can be found here:
# https://developers.home-assistant.io/docs/core/entity/sensor/


async def main():
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
            {"id": 1, "name": "Temperature", "unit": "°C", "type": "temperature", "value": random.randint(19, 25) + random.random()/10},
            {"id": 2, "name": "Humidity", "unit": "%", "type": "humidity", "value": random.randint(40, 50)},
            {"id": 3, "name": "Battery", "unit": "%", "type": "battery", "value": random.randint(70, 80)},
#            {"id": 4, "name": "CO2",  "unit": "ppm", "type": "co2", "value": random.randint(500, 900)},
        ],
    }

    # 3. Create the PUT request
    # NOTE: The path '/sensors/device001/data' matches your tree structure
    request = Message(code=POST, payload=json.dumps(payload).encode("utf-8"))
    request.set_request_uri("coap://127.0.0.1:5683/device")

    print("Sending request...")

    try:
        # 4. Send and wait for response
        response = await protocol.request(request).response
        print(f"Response Code: {response.code}")
        print(f"Response Payload: {response.payload.decode('utf-8')}")
    except Exception as e:
        print(f"Failed to send request: {e}")


if __name__ == "__main__":
    asyncio.run(main())
