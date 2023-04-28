#!/bin/sh
# Deploy or update the MicrogridUP app in production mode with SSL, etc.

#TODO: explicit production variables
export CERTBOT_EMAIL=david.pinney@nreca.coop
export APP_DNS=app.microgridup.org
export DATA_DIR=/MGU_PROD

# Must be run via sudo since we're installing docker, etc.
if [[ $(/usr/bin/id -u) -ne 0 ]]; then
	echo "Not running as root"
	exit
fi

# Make required directories
mkdir -p $DATA_DIR/data
mkdir -p $DATA_DIR/logs
mkdir -p $DATA_DIR/ssl

# Install docker
if [ -x "$(command -v docker)" ]; then
	echo "Docker already installed."
else
	echo "Installing Docker"
	apt-get remove docker docker-engine docker.io containerd runc
	apt-get update
	apt-get install ca-certificates curl gnupg
	install -m 0755 -d /etc/apt/keyrings
	curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
	chmod a+r /etc/apt/keyrings/docker.gpg
	echo \
		"deb [arch="$(dpkg --print-architecture)" signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
		"$(. /etc/os-release && echo "$VERSION_CODENAME")" stable" | \
		tee /etc/apt/sources.list.d/docker.list > /dev/null
	apt-get update
	apt-get install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
	docker run hello-world
fi

# Install and set up certbot
if [ -x "$(command -v certbot)" ]; then
	echo "Certbot already installed."
else
	apt-get remove letsencrypt
	apt-get install letsencrypt
	certbot certonly --standalone --agree-tos -n -m $CERTBOT_EMAIL -d $APP_DNS
	# certbot as of 2023 should renew automatically via its crontab... let's pray...
fi

# Link the letsencrypt certs to the SSL directory
ln -s /etc/letsencrypt/live/$APP_DNS/fullchain.pem $DATA_DIR/ssl/fullchain.pem
ln -s /etc/letsencrypt/live/$APP_DNS/privkey.pem $DATA_DIR/ssl/privkey.pem
ln -s /etc/letsencrypt/live/$APP_DNS/cert.pem $DATA_DIR/ssl/cert.pem

# Get our container and run it.
docker pull ghcr.io/dpinney/microgridup:main
if [ "$(docker ps -a -q -f name=mgucont)" ]; then
	# already running, so kill it first
	docker stop mgucont
	docker rm mgucont
fi
docker run -d -p 80:80 -p 443:443 -v $DATA_DIR/data:/data -v $DATA_DIR/logs:logs -v $DATA_DIR/ssl:ssl --name mgucont ghcr.io/dpinney/microgridup:main