from discord.ext import commands, tasks
from discord import app_commands
from discord.ui import Select, View
import discord
import table2ascii as t2a
import requests
import lxml.html
import json
import time, datetime
from botConfig import *
from colorama import Fore, Back, Style
import matplotlib.pyplot as plt
from matplotlib.dates import DateFormatter as df, MinuteLocator as ml
import io

import tracemalloc
tracemalloc.start()

aviableCommodities = json.load(open(r"database\commodities.json", "r"))
selectOptions = [discord.SelectOption(label=aviableCommodities[i], value=i) for i in aviableCommodities.keys()]
selectOptions.insert(0, discord.SelectOption(label="All", value="all"))

plt.rcParams["figure.figsize"] = [7.5, 5]
plt.rcParams["figure.autolayout"] = True
plt.grid(True)
xfmt = df("%H:00")
xfml = ml(interval=60)
plotFont = {"family": "Consolas", "size": 14}

class database(object):
    def __init__(self, path):
        self.databasePath = path
        self.databaseObject = open(self.databasePath, "r")
        self.database = json.load(self.databaseObject)
    
    def get(self, key): return self.database[key]
    
    def getLatest(self, key, index=-1): return self.database[key][index:]

    def set(self, key, value):
        if key not in self.database.keys(): self.create(key, value)
        else: self.database[key] = value
        self.save()
    
    def setLatest(self, key, value):
        self.database[key][-1] = value
        self.save()
    
    def create(self, key, value):
        self.database[key] = value
        self.save()

    def append(self, key, value):
        self.database[key].append(value)
        self.save()
    
    def save(self, reopen=True):
        self.databaseObject = open(self.databasePath, "w")
        json.dump(self.database, self.databaseObject, indent=4)
        self.databaseObject.close()
        if reopen: self.load()
    
    def load(self):
        self.databaseObject = open(self.databasePath, "r")
        self.database = json.load(self.databaseObject)

    def close(self):
        self.databaseObject.close()
    
    def exists(self, key):
        return key in self.database.keys()

class eliteData(commands.Cog):
    def __init__(self, bot):
        self.bot: commands.Bot = bot
        self.mainDatabase = database(r"database\main.json")
        self.updateCommodityDatabase.start()
        self.updating = False
        self.latestUpdate = 0
        self.guildInfoDatabase = database(r"database\guildInfo.json")

        self.edsmDatabaseLink = "https://www.edsm.net/api-v1"
        self.eddbCommodityLink = "https://eddb.io/commodity/"
    
    def isApprovedGuild():
        def predicate(interaction):
            return interaction.guild.id in approvedGuilds
        return app_commands.check(predicate)

    def scrapePriceFromEDDB(self, resourceID):
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
    
    def createTableFromCommodityData(self, selectedResources):
        headers = ["Name", "Price", "Station", "System"]
        dataTable = t2a.table2ascii(
            header=headers,
            body=[self.scrapePriceFromEDDB(id) for id in selectedResources],
            alignments=[0,0,0,0],
        )
        return dataTable

    def createGraphFromCommodityData(self, commodities):
        ax = plt.gca()

        ax.xaxis.set_major_formatter(xfmt)
        ax.xaxis.set_major_locator(xfml)
        
        #set rotation for x axis
        plt.xticks(rotation=90, **{"family": "Consolas", "size": 10})
        plt.yticks(**{"family": "Consolas", "size": 10})

        unixTimeOfData = []

        for id in commodities:
            latestData = self.mainDatabase.getLatest(id, -5)
            x, y = [], []
            
            for record in latestData:
                unixTimeOfData.append(record["timestamp"])
                x.append(datetime.datetime.fromtimestamp(record["timestamp"]))
                y.append(record["price"])
           
            #add annotations
            plt.annotate(f"{y[0]} Cr", (x[0], y[0]), **{"family": "Consolas", "size": 10})
            plt.annotate(f"{y[-1]} Cr", (x[-1], y[-1]), **{"family": "Consolas", "size": 10})

            #plot data
            plt.plot(x, y, label=aviableCommodities[id])
            plt.scatter(x, y, s=5)

        #set graph properties
        timeFrom = time.strftime("%d/%m/%Y", time.localtime(min(unixTimeOfData)))
        timeTo = time.strftime("%d/%m/%Y", time.localtime(max(unixTimeOfData)))

        plt.title("Commodity Prices", **plotFont)
        plt.xlabel(f"Time({timeFrom} to {timeTo})", **plotFont)
        plt.ylabel("Price", **plotFont)
        plt.legend()

        #save graph to buffer
        buf = io.BytesIO()
        plt.savefig(buf, format="png")
        buf.seek(0)
        return buf

    @app_commands.command(name="commodity", description="Shows the commodity data from EDDB.IO")
    async def commodity(self, interaction):
        await interaction.response.defer()
        async def commoditySelectCallback(interaction):
            await interaction.response.defer()
            
            if len(select.values) == 1 and select.values[0] == "all":
                selectedResources = aviableCommodities.keys()
            else:
                selectedResources = select.values
                if "all" in selectedResources: selectedResources.remove("all")

            updateTime = time.strftime("%H:%M:%S %d-%m-%Y", time.localtime())
            dataTable = self.createTableFromCommodityData(selectedResources)
            await interaction.edit_original_response(content=f"```{dataTable}\n   Data updated at: {updateTime}```", embed=None, view=None)

        view = View()
        select = Select(options=selectOptions, placeholder="Select a commodity", max_values=len(aviableCommodities))
        embed = discord.Embed(title="Select commodities you want data from:", color=0x00ff00)
        
        select.callback = commoditySelectCallback
        view.add_item(select)

        await interaction.edit_original_response(embed=embed, view=view)
    
    @commodity.error
    async def commodity_error(self, interaction, error):
        if isinstance(error, app_commands.CheckFailure):
            await interaction.response.send_message("This command is not allowed on this server!", ephemeral=True)
        else:
            await interaction.response.send_message("Something went wrong!", ephemeral=True)
    
    @app_commands.command(name="update", description="Updates the commodity data")
    async def update(self, interaction):
        await interaction.response.defer()
        #remove last message
        channel = self.bot.get_channel(interaction.channel_id)
        await interaction.followup.send(content="Updating data ...")
        #update data
        dataTable = self.createTableFromCommodityData(aviableCommodities.keys())
      
        if self.guildInfoDatabase.exists(str(interaction.guild_id)):
            channelID = self.guildInfoDatabase.get(str(interaction.guild_id))["updateChannelID"]
            messageID = self.guildInfoDatabase.get(str(interaction.guild_id))["updateMessageID"]
            channel = self.bot.get_channel(channelID)
            if int(channelID) == interaction.channel_id: await interaction.delete_original_response()
            else: await interaction.edit_original_response(content=f"Data updated in <#{channelID}>!", embed=None, view=None)
            message = await channel.fetch_message(messageID)
            await message.edit(content=f"```{dataTable}\nLatest database update: {time.strftime('%H:%M:%S %d-%m-%Y', self.latestUpdate)}```", embed=None, view=None)
        else:
            await interaction.edit_original_response("No update channel set! Use the `/setupdatechannel` command to set one!")

    @update.error
    async def update_error(self, interaction, error):
        if isinstance(error, app_commands.CheckFailure):
            await interaction.response.send_message("This command is not allowed on this server!", ephemeral=True)
        else:
            await interaction.response.send_message("Something went wrong!", ephemeral=True)

    @app_commands.command(name="setupdatechannel", description="Sets the channel where the update command will post the data")
    async def setUpdateChannel(self, interaction):
        await interaction.response.defer()
        await interaction.edit_original_response(content="Set update channel to this channel!", embed=None, view=None)
        await interaction.channel.send(content="This is the message that will contain update data!")
        async for msg in interaction.channel.history(limit=1):
            msgID = msg.id
        self.guildInfoDatabase.set(str(interaction.guild_id), {"updateChannelID": interaction.channel_id, "updateMessageID": msgID})
        await interaction.delete_original_response()

    @app_commands.command(name="graph", description="Shows the graph of a commodity/commodities")
    async def graph(self, interaction):
        async def graphSelectCallback(interaction):
            await interaction.response.defer()
            if len(select.values) == 1 and select.values[0] == "all":
                selectedResources = aviableCommodities.keys()
            else:
                selectedResources = select.values
                if "all" in selectedResources: selectedResources.remove("all")
            await interaction.edit_original_response(content="Generating graph ...", embed=None, view=None)
            graphImage = self.createGraphFromCommodityData(selectedResources)
            graphFile = discord.File(graphImage, filename="graph.png")
            await interaction.edit_original_response(content=None, embed=None, view=None, attachments=[graphFile])

        await interaction.response.defer()
        view = View()
        select = Select(options=selectOptions, placeholder="Select a commodity", max_values=len(aviableCommodities))
        embed = discord.Embed(title="Select commodities you want data from:", color=0x00ff00)
        
        select.callback = graphSelectCallback
        view.add_item(select)

        await interaction.edit_original_response(embed=embed, view=view)

    @tasks.loop(hours=1, reconnect=True)
    async def updateCommodityDatabase(self):
        if self.updating: return
        self.updating = True
        
        #get data
        updateData = {id:self.scrapePriceFromEDDB(id) for id in aviableCommodities.keys()}
        
        #format data
        for id in updateData.keys():
            updateData[id] = {
                "timestamp": int(time.time()),
                "price": int(updateData[id][1].replace(",", "").replace("Cr", "")),
                "station": updateData[id][2],
                "system": updateData[id][3]
            }

        #update database
        for id in aviableCommodities.keys():
            if self.mainDatabase.getLatest(id)[0]["price"] == updateData[id]["price"]:
                self.mainDatabase.setLatest(id, updateData[id])
            else:
                self.mainDatabase.append(id, updateData[id])
        
        self.latestUpdate = time.localtime()
        self.updating = False
        bold = '\033[1m'
        normal = "\033[0m"
        print(f"{Fore.LIGHTBLACK_EX}{bold}{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}{normal} {Fore.BLUE}{Style.BRIGHT}INFO", end=f"     {Style.RESET_ALL}")
        print(f"{normal}{Fore.MAGENTA}database{Style.RESET_ALL} {Style.RESET_ALL}Database updated")

async def setup(bot):
    print("Loaded cog: eliteData")
    await bot.add_cog(eliteData(bot))