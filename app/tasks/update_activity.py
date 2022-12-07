import json
import traceback

from celery_once import QueueOnce
from django.db.models import F
from dynamic_preferences.registries import global_preferences_registry

from app.models import ServerMember
from evosbot.celery import app

global_preferences = global_preferences_registry.manager()


@app.task(name='app.tasks.update_activity', base=QueueOnce, once={'graceful': True})
def update_activity():
    try:
        with open('/tmp/evos_online.json') as f:
            members = json.load(f)
        ServerMember.objects.filter(pk__in=members).update(activity_counter=F('activity_counter') + 1)
        ServerMember.objects.filter(pk__lt=0).update(activity_counter=F('activity_counter') + 1)
    except:
        traceback.print_exc()
