import logging
import traceback
from time import sleep

from django.core.management import BaseCommand
from dynamic_preferences.registries import global_preferences_registry

from app.models import AirdropTask
from evosbot.utils import tx_logger, fd

global_preferences = global_preferences_registry.manager()


class Command(BaseCommand):
    def handle(self, *args, **options):
        while True:
            for task in AirdropTask.objects.filter(processed=False).order_by('id'):  # type: AirdropTask
                is_rain = task.is_rain

                if not is_rain and global_preferences['general__feeder_balance'] < task.amount:
                    continue

                try:
                    sm = task.member
                    sm.refresh_from_db()
                    sm.balance += task.amount
                    sm.save(update_fields=('balance',))

                    if is_rain:
                        tx_logger.warning('RAIN,{},+{:.8f}'.format(sm, task.amount))
                        if not sm.noinform:
                            sm.send_message('You have been rained the amount of {} SOVE\n'.format(fd(task.amount)) +
                                            'In order to stop receiving these notifications just type `noinform`')
                    else:
                        global_preferences['general__feeder_balance'] -= task.amount
                        tx_logger.warning('AIRDROP,{},+{:.8f}'.format(sm, task.amount))
                        if not sm.noinform:
                            sm.send_message('Airdrop of {} SOVE was added to your balance!'.format(fd(task.amount)))

                    task.processed = True
                    task.save()
                except KeyboardInterrupt:
                    return
                except:
                    logging.error('Task #{} (member {}) error:'.format(task.pk, task.member))
                    traceback.print_exc()
            sleep(5)
