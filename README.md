# ha-coap-service

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
