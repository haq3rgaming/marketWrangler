#library imports
import discord 
from discord.ext import commands
from discord import app_commands

from apiKeys import botToken

class musicWrangler(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix="!",
            intents=discord.Intents.all(),
        )
    
    async def setup_hook(self):
        print('Setup hook')
        await wrangler.load_extension("cogs.musicPlayer")
        print(f'{wrangler.user} has connected to Discord!')
    
    @app_commands.command(name = "wakeup", description = "My first application Command")
    async def wakeupmain(self, interaction, custom: str):
        await interaction.response.send_message(f"I'm awake!\nCustom: {custom}")

    @app_commands.command(name="debug", description="Debug command")
    async def debug(self, interaction):
        syncOutput = await wrangler.tree.sync()
        await interaction.response.send_message(f"{syncOutput}")

wrangler = musicWrangler()

#register the application commands
@wrangler.command(owner_only=True, name="sync", description="Syncs the bot commands")
async def sync(interaction):
    await interaction.channel.send("Syncing...")
    syncOutput = await wrangler.tree.sync()
    print(syncOutput)
    await interaction.channel.send("Done!")

#run the bot
wrangler.run(botToken)