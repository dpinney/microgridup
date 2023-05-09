# A Dockerfile for running MicrogridUP.
FROM ubuntu:18.04
MAINTAINER <david.pinney@nreca.coop>

# Install OS prereqs.
RUN apt-get -y update && apt-get install -y python3 git sudo vim python3-pip python3-setuptools

# Install the OMF
# Warning: clone might be cached. Consider invalidating manually.
RUN git clone --depth 1 https://github.com/dpinney/omf.git
RUN cd omf; sudo python3 install.py

# Move files across.
COPY . .

# Special requirements for graph layout
RUN sudo apt-get install graphviz graphviz-dev
RUN pip install pygraphviz

# Run the MGU gui.
WORKDIR .
ENTRYPOINT ["python3"]
CMD ["microgridup_gui.py"]
EXPOSE 5000

# USAGE
# =====
# - Navigate to this directory
# - Build image with command `docker build . -f mgu.Dockerfile -t mguim`
# - Run image in background with `docker run -d -p 5000:5000 --name mgucont mguim`
# - View at http://127.0.0.1:5000
# - Stop it with `docker stop mgucont` and remove it with `docker rm mgucont`.
# - Delete the images with `docker rmi mguim`