from discord.ext import commands, tasks
from discord import app_commands
import discord
import table2ascii as t2a
import requests
import lxml.html

class eliteData(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.mainDatabaseLink = "http://haq3rgaming.pythonanywhere.com/api"
        self.edsmDatabaseLink = "https://www.edsm.net/api-v1"
        self.eddbCommodityLink = "https://eddb.io/commodity/"
    
    def scrapePrice(self, resourceID):
        nameXpath = "/html/body/div[1]/div/div[1]/h1/text()"
        priceXpath = "/html/body/div[1]/div/div[2]/div[2]/div/div[3]/div[3]"
        stationXpath = "/html/body/div[1]/div/div[2]/div[2]/div/div[3]/div[4]/strong/a"
        systemXpath = "/html/body/div[1]/div/div[2]/div[2]/div/div[3]/div[5]/strong/a"

        url = self.eddbCommodityLink + str(resourceID)
        response = requests.get(url, stream=True)
        response.raw.decode_content = True
        tree = lxml.html.parse(response.raw)
        
        name = tree.xpath(nameXpath)
        priceElement = tree.xpath(priceXpath)
        sellingStation = tree.xpath(stationXpath)
        stationSystem = tree.xpath(systemXpath)
        
        displayName = name[0] if len(name) > 0 else "N/A"
        displayPrice = priceElement[0].text if len(priceElement) > 0 else "N/A"
        displayStation = sellingStation[0].text if len(sellingStation) > 0 else "N/A"
        displaySystem = stationSystem[0].text if len(stationSystem) > 0 else "N/A"

        return [displayName, displayPrice, displayStation, displaySystem]

    @app_commands.command(name="commodity", description="Shows the commodity data")
    @app_commands.describe(commodityid="Enter the commodity ID from eddb.io")
    async def commodity(self, interaction, commodityid: str):
        commodityData = []
        embed = discord.Embed(title="Commodity data", color=0x00ff00)
        await interaction.response.send_message(embed=embed)
        if "," in commodityid:
            for commodity in commodityid.split(","):
                commodityData.append([*self.scrapePrice(commodity)])
        else:
            commodityData.append([*self.scrapePrice(commodityid)])
        embedTable = t2a.table2ascii(
            header=["Name", "Price", "Station", "System"],
            body=commodityData,
        )
        embed.description = f"```{embedTable}```"
        await interaction.edit_original_response(embed=embed)

async def setup(bot):
    print("Loaded cog: eliteData")
    await bot.add_cog(eliteData(bot))