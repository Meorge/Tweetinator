#!/bin/bash
export FLASK_APP="`dirname "$0"`/flask_server.py"
export FLASK_ENV=development
flask run --host=0.0.0.0