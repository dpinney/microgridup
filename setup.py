''' Install microgridup.
 usage: `python setup.py develop`
 '''

from setuptools import setup
from setuptools.command.develop import develop
from setuptools.command.install import install
from subprocess import check_call

def pre_install():
	try:
		import omf
	except:
		check_call("git clone --depth=1 https://github.com/dpinney/omf.git".split())
		check_call("cd omf; python install.py".split())

class PreDevelopCommand(develop):
	def run(self):
		pre_install()
		develop.run(self)

class PreInstallCommand(install):
	def run(self):
		pre_install()
		install.run(self)

setup(
	name='microgridup',
	version='1.0',
	py_modules=['microgridup'],
	cmdclass={
		'develop':PreDevelopCommand,
		'install':PreInstallCommand
	}
)

install_sh = '''
#!/bin/bash

export REPO="/opt/microgridup"

# Install all packages
DEBIAN_FRONTEND=noninteractive sudo apt-get install -y systemd letsencrypt python3-pip authbind
git clone --depth 1 https://github.com/dpinney/omf.git
cd omf; sudo python3 install.py

sudo ln -s $REPO/systemd/microgridup.service /etc/systemd/system/microgridup.service
sudo ln -s $REPO/systemd/cert.service /etc/systemd/system/cert.service
sudo ln -s $REPO/systemd/cert.timer /etc/systemd/system/cert.timer

# NOTE: Make sure these environment variables are set after all the packages are installed
export EMAIL=$(python3 -c "from forecast_app.config import EMAIL; print(EMAIL)")
export DOMAIN=$(python3 -c "from forecast_app.config import DOMAIN; print(DOMAIN)")

# Setup TLS
sudo certbot certonly --standalone --agree-tos -n -m $EMAIL -d $DOMAIN

# Add microgridup user:group
sudo useradd -r microgridup
sudo chown -R microgridup:microgridup ./
sudo chown -R microgridup:microgridup /etc/letsencrypt
sudo chown -R microgridup:microgridup /var/log/letsencrypt

# configure authbind so microgridup can bind to low-numbered ports sans root.
sudo touch /etc/authbind/byport/80
sudo touch /etc/authbind/byport/443
sudo chown microgridup:microgridup /etc/authbind/byport/80
sudo chown microgridup:microgridup /etc/authbind/byport/443
sudo chmod 710 /etc/authbind/byport/80
sudo chmod 710 /etc/authbind/byport/443

# create directory for LetsEncrypt acme challenges.
sudo mkdir -p $REPO/.well-known/acme-challenge

# Ensure timezone is correct
sudo ln -sf /usr/share/zoneinfo/America/New_York /etc/localtime

# enable
sudo systemctl enable /etc/systemd/system/microgridup.service
sudo systemctl start microgridup
sudo systemctl enable /etc/systemd/system/cert.service
sudo systemctl enable /etc/systemd/system/cert.timer
'''