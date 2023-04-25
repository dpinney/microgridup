## microgridup

MicrogridUp Design Tool - for a given circuit, determine an optimal set of microgrids that will provide cost savings and resilience.

## Installation (for Users)

1. Install [Docker](https://docs.docker.com/get-docker/)
1. Get the app `docker pull ghcr.io/dpinney/microgridup:main`
1. Create the container and start it with `docker run -d -p 5001:5000 --name mgucont ghcr.io/dpinney/microgridup:main`
1. The web app will then be running at http://127.0.0.1:5001
1. You can stop/start the app via `docker stop mgucont`/`docker start mgucont`

## Installation (for Developers)

1. You'll need python v3.6 or later.
1. `pip install -e git+https://github.com/dpinney/microgridup`
1. Test the code by running `python microgrid_test_3mg.py`
1. Start the GUI with `python microgridup_gui.py`
