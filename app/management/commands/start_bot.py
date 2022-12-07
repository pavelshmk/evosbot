from django.core.management import BaseCommand
from dynamic_preferences.registries import global_preferences_registry

from app.bot.discord import bot


global_preferences = global_preferences_registry.manager()


class Command(BaseCommand):
    def handle(self, *args, **options):
        bot.run(global_preferences['general__bot_token'])
