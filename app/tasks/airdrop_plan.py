import logging
import os
import random
from datetime import timedelta
from random import randint

from django.utils import timezone

from evosbot.celery import app
from .airdrop import airdrop


def get_random_time():
    return timezone.now() + timedelta(seconds=randint(0, 60*60*24))


@app.task(name='app.tasks.airdrop_plan')
def airdrop_plan():
    for i in range(3):
        random.seed(os.urandom(255))
        eta = get_random_time()
        task = airdrop.apply_async(args=('small',), eta=eta)
        logging.warning('Planning small airdrop #{} at {}'.format(task.id, eta))
    for i in range(2):
        random.seed(os.urandom(255))
        eta = get_random_time()
        task = airdrop.apply_async(args=('medium',), eta=eta)
        logging.warning('Planning medium airdrop #{} at {}'.format(task.id, eta))
    random.seed(os.urandom(255))
    eta = get_random_time()
    task = airdrop.apply_async(args=('large',), eta=eta)
    logging.warning('Planning large airdrop #{} at {}'.format(task.id, eta))
