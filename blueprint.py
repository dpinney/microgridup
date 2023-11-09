#!/usr/bin/env python

from flask import Blueprint

data_dir_blueprint = Blueprint('data_dir_blueprint', __name__, static_url_path='/data', static_folder='data')