"""Criação e configuração do bot Discord."""
import discord
from discord.ext import commands

from bot.commands import setup_commands
from config.settings import get_settings
from database.connection import make_database


def build_bot() -> commands.Bot:
    settings = get_settings()

    intents = discord.Intents.default()
    intents.members = True  # necessário para fetch_member / add_roles

    bot = commands.Bot(command_prefix="!", intents=intents)

    db = make_database(settings.DATABASE_PATH)
    bot.db = db  # exposto para uso em webhook/tasks

    setup_commands(bot, db)

    @bot.event
    async def on_ready():
        guild_obj = discord.Object(id=settings.GUILD_ID)
        bot.tree.copy_global_to(guild=guild_obj)
        synced = await bot.tree.sync(guild=guild_obj)
        print(f"Bot conectado como {bot.user} | {len(synced)} comando(s) sincronizado(s).")

    return bot
