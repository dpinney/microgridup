#!/bin/sh

# install docker
sudo apt-get remove docker docker-engine docker.io containerd runc
sudo apt-get update
sudo apt-get install ca-certificates curl gnupg
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg
echo \
	"deb [arch="$(dpkg --print-architecture)" signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
	"$(. /etc/os-release && echo "$VERSION_CODENAME")" stable" | \
	sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update
sudo apt-get install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo docker run hello-world

# install and set up certbot
sudo apt-get remove letsencrypt
sudo apt-get install letsencrypt
sudo certbot certonly --standalone --agree-tos -n -m david.pinney@nreca.coop -d app.microgridup.org
# certbot as of 2023 should renew automatically via its crontab... let's pray...

# get our container
sudo docker pull ghcr.io/dpinney/microgridup:main
sudo docker run -d -p 80:5000 --name mgucont ghcr.io/dpinney/microgridup:main