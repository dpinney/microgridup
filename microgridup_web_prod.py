"""
MicrogridUP Production Web Server
"""

from flask import Flask, redirect, request, send_from_directory
import os
from subprocess import Popen

mgu_path = os.path.abspath(os.path.dirname(__file__))

reApp = Flask("HTTPS_REDIRECT")

@reApp.route("/")
def index():
	return "NA"

@reApp.before_request
def before_request():
	# Handle ACME challenges for letsencrypt to keep SSL renewing.
	if '/.well-known/acme-challenge' in request.url:
		try:
			filename = request.url.split('/')[-1]
		except:
			filename = 'none'
		return send_from_directory(f'/{mgu_path}/.well-known/acme-challenge', filename)
	# Redirect http -> https
	elif request.url.startswith("http://"):
		url = request.url.replace("http://", "https://", 1)
		return redirect(url, code=301)

if __name__ == "__main__":
	# Start redirector:
	redirProc = Popen(['gunicorn', '-w', '5', '-b', '0.0.0.0:80', 'webProd:reApp'])
	# Start application:
	appProc = Popen(['gunicorn', '-w', '5', '-b', '0.0.0.0:443', '--certfile=microgridupDevCert.pem', '--ca-certs=certChain.ca-bundle', '--keyfile=microgridupDevKey.pem', '--preload', 'web:app','--worker-class=sync', '--access-logfile', 'microgridup.access.log', '--error-logfile', 'microgridup.error.log', '--capture-output'])
	appProc.wait()