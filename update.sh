#!/bin/bash
localdir="/root/config/coap_server/custom_components/coap_server"
component="/root/config/custom_components/coap_server"

git pull origin main

rm -r "$component"
cp -r "$localdir" "$component"
