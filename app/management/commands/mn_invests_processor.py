import logging
import traceback
from time import sleep

from django.core.management import BaseCommand
from dynamic_preferences.registries import global_preferences_registry

from app.models import UpdateRoleTask, MNInvestTask
from evosbot.utils import get_member, set_roles, client, masternode_address, fd

global_preferences = global_preferences_registry.manager()


class Command(BaseCommand):
    def handle(self, *args, **options):
        while True:
            for task in MNInvestTask.objects.filter(processed=False).order_by('id'):  # type: MNInvestTask
                logging.warning('Processing task #{} (member #{})'.format(task.pk, task.member.pk))
                sm = task.member
                try:
                    client.send_funds(masternode_address(), task.amount_without_fee)
                    sm.masternode_balance += task.amount_without_fee
                    sm.save(update_fields=('masternode_balance',))
                    sm.send_message('{} SOVE were invested to masternode'.format(fd(task.amount)))
                    sm.update_investor_role()
                    task.processed = True
                    task.save()
                except RuntimeError as e:
                    logging.warning('An error has occurred: {}'.format(e))
                    traceback.print_exc()
                sleep(1)
            sleep(5)
