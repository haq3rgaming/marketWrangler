from discord.ext import commands
from discord import app_commands
import discord

async def setup(bot):
    print("musicPlayer setup")
    await bot.add_cog(musicPlayer(bot))

class playerButtons(discord.ui.View):
    def __init__(self):
        super().__init__()
        self.add_item(discord.ui.Button(label="Play", style=discord.ButtonStyle.green))
        self.add_item(discord.ui.Button(label="Pause", style=discord.ButtonStyle.grey))
        self.add_item(discord.ui.Button(label="Stop", style=discord.ButtonStyle.red))

class musicPlayer(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    @app_commands.command(name = "join", description = "Joins the voice channel you are currently in")
    async def join(self, interaction):
        await interaction.response.send_message(f"Joining: {interaction.user.voice.channel.name}")
    
    @app_commands.command(name="menu", description="Sends a simple embed")
    async def menu(self, interaction):
        embed = discord.Embed(title="Simple Embed", description="This is a simple embed", color=0x00ff00)
        await interaction.response.send_message(embed=embed, view=playerButtons())

