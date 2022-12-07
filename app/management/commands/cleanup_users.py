from django.core.management import BaseCommand
from dynamic_preferences.registries import global_preferences_registry

from app.models import ServerMember
from evosbot.utils import get_members


global_preferences = global_preferences_registry.manager()


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument(
            '--execute',
            action='store_true',
            help='Perform cleanup',
        )

    def handle(self, *args, **options):
        member_ids = [0]
        while True:
            members = get_members(global_preferences['general__guild_id'], max(member_ids))
            if not members:
                break
            member_ids.extend([int(u['user']['id']) for u in members])
        qs = ServerMember.objects.exclude(pk__in=member_ids)\
                                 .exclude(balance__gt=0)\
                                 .exclude(masternode_balance__gt=0)\
                                 .exclude(staking_pool_amount__gt=0)\
                                 .exclude(bitcoin_balance__gt=0)\
                                 .exclude(usernodes__pk__isnull=False)\
                                 .exclude(mn_withdraws__pk__isnull=False)\
                                 .exclude(unstakings__pk__isnull=False)
        if options['execute']:
            rows, _ = qs.delete()
            print('Deleted {} members'.format(rows))
        else:
            total_members = ServerMember.objects.count()
            rows = qs.count()
            print('{} out of {} members will be deleted on execution'.format(rows, total_members))
