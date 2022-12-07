import logging

from django.core.management import BaseCommand
from dynamic_preferences.registries import global_preferences_registry

from app.bot.discord import bot
from app.bot.telegram import get_updater

global_preferences = global_preferences_registry.manager()


class Command(BaseCommand):
    def handle(self, *args, **options):
        # bot.run(global_preferences['general__bot_token'])
        logging.basicConfig(level=logging.WARNING)
        get_updater().start_polling()
