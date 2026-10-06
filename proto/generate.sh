#!/bin/bash

protoc --proto_path=proto --python_out=custom_components/coap_server proto/coap.proto

cp -r custom_components/coap_server/coap_pb2.py proto/coap_pb2.py
