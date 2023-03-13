#library imports
import discord 
from discord.ext import commands
from discord import app_commands

from apiKeys import botToken

#bot setup
intents = discord.Intents().all()
client = commands.Bot(intents=intents, command_prefix="!")
tree = client.tree

#bot events
@client.event
async def on_ready():
    print(f'{client.user} has connected to Discord!')

async def setup_hook():
    print('Setup hook')
    await client.load_extension("cogs.musicPlayer")

@tree.command(name = "wakeup", description = "My first application Command")
async def wakeup(interaction, custom: str):
    await interaction.response.send_message(f"I'm awake!\nCustom: {custom}")

@tree.command(name="debug", description="Debug command")
async def debug(interaction):
    await interaction.response.send_message(f"Debug command")

@client.command(owner_only=True, name="sync", description="Syncs the bot commands")
async def sync(ctx):
    await ctx.channel.send("Syncing...")
    syncOutput = await tree.sync()
    print(syncOutput)
    await ctx.channel.send("Done!")

#bot run
client.run(botToken)