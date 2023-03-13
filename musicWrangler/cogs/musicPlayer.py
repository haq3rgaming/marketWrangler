from discord.ext import commands
from discord import app_commands

async def setup(bot):
    print("musicPlayer setup")
    await bot.add_cog(musicPlayer(bot))

class musicPlayer(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    @app_commands.command(name = "wakeupcog", description = "My first application Command from a Cog")
    async def wakeupcog(self, interaction, custom: str):
        await interaction.channel.send(f"I'm awake from a Cog!\nCustom: {custom}")
        #await interaction.response.send_message(f"I'm awake from a Cog!\nCustom: {custom}")

