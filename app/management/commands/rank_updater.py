import logging
from time import sleep

from django.core.management import BaseCommand
from dynamic_preferences.registries import global_preferences_registry

from app.models import UpdateRoleTask
from evosbot.utils import get_member, set_roles

global_preferences = global_preferences_registry.manager()


class Command(BaseCommand):
    def handle(self, *args, **options):
        while True:
            for task in UpdateRoleTask.objects.filter(processed=False).order_by('id'):  # type: UpdateRoleTask
                logging.warning('Processing task #{} (member #{})'.format(task.pk, task.member.pk))
                m = get_member(global_preferences['general__guild_id'], task.member.pk)
                if 'roles' not in m:
                    logging.error('Received member object does not have `roles` field: {}'.format(m))
                    if 'code' in m and m['code'] == 10007:  # unknown member
                        logging.warning('Unknown member, possibly banned')
                    else:
                        break
                else:
                    changed = False
                    current_roles = set(m['roles'])
                    if task.remove_roles:
                        remove_roles = set(task.remove_roles.split('|'))
                        if remove_roles.intersection(current_roles):
                            changed = True
                            current_roles -= remove_roles
                    if task.add_roles:
                        add_roles = set(task.add_roles.split('|'))
                        if not add_roles.issubset(current_roles):
                            changed = True
                            current_roles.update(add_roles)
                    if changed:
                        r = set_roles(global_preferences['general__guild_id'], task.member.pk, list(current_roles))
                        if r.status_code != 204:
                            logging.error('Could not update roles: {}'.format(r.json()))
                            break
                        logging.warning('Roles updated successfully')
                    else:
                        logging.warning('Nothing to update')
                task.processed = True
                task.save()
                sleep(.2)
            sleep(5)
