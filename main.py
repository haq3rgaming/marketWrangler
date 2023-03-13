import os

import discord
from discord.ext import commands
from discord import app_commands

from apiKeys import *

class musicWrangler(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=discord.Intents.all())
    
    async def setup_hook(self):
        print('Setup hook')
        await wrangler.load_extension("cogs.musicPlayer")

wrangler = musicWrangler()

@wrangler.command(name="sync", description="Syncs the bot commands")
async def sync(interaction):
    if interaction.author.id == ownerID:
        await interaction.channel.send("Syncing...")
        await wrangler.tree.sync()
        await interaction.channel.send("Done!")
    else: pass

@wrangler.command(name="loadCog", description="Loads a cog")
async def loadCog(interaction, cogName):
    await wrangler.load_extension(f"cogs.{cogName}")

@wrangler.command(name="unloadCog", description="Unloads a cog")
async def unloadCog(interaction, cogName):
    await wrangler.unload_extension(f"cogs.{cogName}")

@wrangler.command(name="reloadCog", description="Reloads a cog")
async def reloadCog(interaction, cogName):
    await wrangler.reload_extension(f"cogs.{cogName}")

@wrangler.command(name="reload", description="Reloads all cogs")
async def reload(interaction):
    cogs = [i[:-3] for i in os.listdir(r".\cogs") if i.endswith(".py")]
    for cog in cogs: await wrangler.reload_extension(f"cogs.{cog}")
    await interaction.channel.send("Reloaded all cogs")

#run the bot
wrangler.run(botToken)