#!/bin/bash

protoc --proto_path=proto --python_out=custom_components/coap_server proto/coap.proto
