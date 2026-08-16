
import custom_components.coap_server.coap_pb2 as coap_pb2

device = coap_pb2.NewDevice()
device.version = 1
device.id = "device_123"

print("Device object:")
print(device)

print("Serialized device (bytes):")
dev = device.SerializeToString()
print(dev)

print("Serialized device (hex):")
hex = device.SerializeToString().hex()
print(hex)

print("Deserialized device object:")
newdevice = coap_pb2.NewDevice()
newdevice.ParseFromString(dev)
print(newdevice)

print("Deserialized device (hex):")
new2device = coap_pb2.NewDevice()
new2device.ParseFromString(bytes.fromhex(hex))
print(new2device)

print(coap_pb2.EntityType.ENTITY_TYPE_UNSPECIFIED)
