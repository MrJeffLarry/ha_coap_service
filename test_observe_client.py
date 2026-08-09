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
        "id": "device002",
        "sensors": [
            {"id": 6},
        ],
    }

    # 3. Create the GET request
    # NOTE: The path '/sensors/device001/data' matches your tree structure
    request = Message(code=POST, payload=json.dumps(payload).encode("utf-8"), observe=0)
    request.set_request_uri("coap://127.0.0.1:5683/device/observe")

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


if __name__ == "__main__":
    asyncio.run(main())
