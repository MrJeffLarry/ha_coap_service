# ha-coap-service

## Use DTLS

Please install the following packages to enable DTLS support:

```bash
apt-get install -y autoconf automake libtool build-essential
pip install DTLSSocket
```

## Development

### Devcontainer

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
