#!/usr/bin/env bash

set -xe

git pull
source venv/bin/activate
pip install -r requirements.txt
./manage.py migrate
./manage.py collectstatic --noinput
supervisorctl restart evosbot:*
