# Care NHCX

[![Release Status](https://img.shields.io/pypi/v/care_nhcx.svg)](https://pypi.python.org/pypi/care_nhcx)
[![Build Status](https://github.com/ohcnetwork/care_nhcx/actions/workflows/build.yaml/badge.svg)](https://github.com/ohcnetwork/care_nhcx/actions/workflows/build.yaml)

Care NHCX is a sample plugin, a plugin boilerplate to begin developing the plugin for care.

## Local Development

To develop the plug in local environment along with care, follow the steps below:

1. Go to the care root directory and clone the plugin repository:

```bash
cd care
git clone git@github.com:ohcnetwork/care_nhcx.git
```

2. Add the plugin config in plug_config.py

```python
...

nhcx_plugin = Plug(
    name="nhcx", # name of the django app in the plugin
    package_name="/app/care_nhcx", # this has to be /app/ + plugin folder name
    version="", # keep it empty for local development
    configs={}, # plugin configurations if any
)
plugs = [nhcx_plug]

...
```

3. Tweak the code in plugs/manager.py, install the plugin in editable mode

```python
...

subprocess.check_call(
    [sys.executable, "-m", "pip", "install", "-e", *packages] # add -e flag to install in editable mode
)

...
```

4. Rebuild the docker image and run the server

```bash
make re-build
make up
```

> [!IMPORTANT]
> Do not push these changes in a PR. These changes are only for local development.

## Production Setup

To install care nhcx, you can add the plugin config in [care/plug_config.py](https://github.com/ohcnetwork/care/blob/develop/plug_config.py) as follows:

```python
...

nhcx_plug = Plug(
    name="nhcx",
    package_name="git+https://github.com/ohcnetwork/care_nhcx.git",
    version="@master",
    configs={},
)
plugs = [nhcx_plug]
...
```

[Extended Docs on Plug Installation](https://care-be-docs.ohc.network/pluggable-apps/configuration.html)

## Configuration

The following configurations variables are available for Care NHCX:

- `NHCX_DUMMY_ENV`: Dummy environment variable for testing

The plugin will try to find the API key from the config first and then from the environment variable.

## License

This project is licensed under the terms of the [MIT license](LICENSE).

---

This plugin was created with [Cookiecutter](https://github.com/audreyr/cookiecutter) using the [ohcnetwork/care-plugin-cookiecutter](https://github.com/ohcnetwork/care-plugin-cookiecutter).
