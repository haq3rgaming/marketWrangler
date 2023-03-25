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
import matplotlib.pyplot as plt
from matplotlib.dates import DateFormatter as df, MinuteLocator as ml
import io
import logFunctions as log

import tracemalloc
tracemalloc.start()

aviableCommodities = json.load(open(r"database\commodities.json", "r"))
selectOptions = [discord.SelectOption(label=aviableCommodities[i], value=i) for i in aviableCommodities.keys()]
alertOptions = [discord.app_commands.Choice(name=aviableCommodities[i], value=i) for i in aviableCommodities.keys()]

plt.rcParams["figure.figsize"] = [7.5, 5]
plt.rcParams["figure.autolayout"] = True
xfmt = df("%H:00")
xfml = ml(interval=60)
plotFont = {"family": "Consolas", "size": 14}

class database(object):
    def __init__(self, path):
        self.databasePath = path
        self.databaseObject = open(self.databasePath, "r")
        self.database = json.load(self.databaseObject)
        self.latestUpdate = 0
    
    def get(self, key): return self.database[key]
    
    def getLatest(self, key, index=-1): return self.database[key][index:]

    def getLatestByTime(self, key, latestTime = 72):
        latestTimeGet = self.getLatest(key)[0]["timestamp"] - latestTime * 60 * 60
        return [i for i in self.database[key] if i["timestamp"] > latestTimeGet]

    def add(self, key, value, replaceIdentical=False):
        if replaceIdentical:
            if self.getLatest(key)[0]["price"] == value["price"]:
                self.setLatest(key, value)
            else: self.append(key, value)
        else: self.append(key, value)

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
        self.latestUpdate = time.time()
        if reopen: self.load()
    
    def load(self):
        self.databaseObject = open(self.databasePath, "r")
        self.database = json.load(self.databaseObject)

    def close(self):
        self.databaseObject.close()
    
    def exists(self, key):
        return key in self.database.keys()

class commodityTableView(View):
    def __init__(self, createTableFromCommodityData, latestUpdate):
        super().__init__()
        self.add_item(commodityTableSelect(
            options=[discord.SelectOption(label="All", value="all"), *selectOptions],
            placeholder="Select a commodity",
            min_values=1,
            max_values=len(selectOptions),
            createTableFromCommodityData=createTableFromCommodityData,
            latestUpdate=latestUpdate
        ))

class commodityTableSelect(Select):
    def __init__(self, createTableFromCommodityData, latestUpdate, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.callback = self.commoditySelectCallback
        self.createTableFromCommodityData = createTableFromCommodityData
        self.latestUpdate = latestUpdate

    async def commoditySelectCallback(self, interaction):
            await interaction.response.defer()
            if len(self.values) == 1 and self.values[0] == "all":
                selectedResources = aviableCommodities.keys()
            else:
                selectedResources = self.values
                if "all" in selectedResources: selectedResources.remove("all")

            updateTime = time.strftime("%H:%M:%S %d-%m-%Y", self.latestUpdate)
            dataTable = self.createTableFromCommodityData(selectedResources)
            await interaction.edit_original_response(content=f"```{dataTable}\n  Data updated at: {updateTime}```", embed=None, view=None)

class commodityGraphView(View):
    def __init__(self, createGraphFromCommodityData):
        super().__init__()
        self.add_item(commodityGraphSelect(
            options=selectOptions,
            placeholder="Select a commodity",
            min_values=1,
            max_values=len(selectOptions),
            createGraphFromCommodityData = createGraphFromCommodityData
        ))

class commodityGraphSelect(Select):
    def __init__(self, createGraphFromCommodityData, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.callback = self.graphSelectCallback
        self.createGraphFromCommodityData = createGraphFromCommodityData
    
    async def graphSelectCallback(self, interaction):
        await interaction.response.defer()
        selectedResources = self.values
        await interaction.edit_original_response(content="Generating graph...", embed=None, view=None)
        graphImage = self.createGraphFromCommodityData(selectedResources)
        graphFile = discord.File(graphImage, filename="graph.png")
        await interaction.edit_original_response(content=None, embed=None, view=None, attachments=[graphFile])

class alertMessageView(View):
    def __init__(self, alertDatabase, commodityID):
        super().__init__()
        self.alertDatabase = alertDatabase
        self.commodityID = commodityID

    @discord.ui.button(label="Keep alert", style=discord.ButtonStyle.gray)
    async def keepAlert(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(view=None)

    @discord.ui.button(label="Dismiss", style=discord.ButtonStyle.gray)
    async def dismiss(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(content=f"Alert for {aviableCommodities[self.commodityID]} dismissed!", embed=None, view=None, delete_after=10)
        guildAlerts = self.alertDatabase.get(str(interaction.guild.id))
        del guildAlerts[self.commodityID]
        self.alertDatabase.set(str(interaction.guild.id), guildAlerts)
    
    @discord.ui.button(label="Alert me again", style=discord.ButtonStyle.gray)
    async def alertAgain(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(content=f"Alert for {aviableCommodities[self.commodityID]} has been reset!", embed=None, view=None, delete_after=10)

class eliteData(commands.Cog):
    def __init__(self, bot):
        self.bot: commands.Bot = bot

        self.mainDatabase = database(r"database\main.json")
        self.guildInfoDatabase = database(r"database\guildInfo.json")
        self.alertDatabase = database(r"database\alerts.json")
        
        self.updating = False
        self.latestUpdate = 0
        self.updateCommodityDatabase.start()

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
        data = []
        for id in selectedResources:
            name = aviableCommodities[id]
            record = self.mainDatabase.getLatest(id)[0]
            price = f"{('{:,}'.format(record['price']))} Cr"
            station, system = record["station"], record["system"]
            data.append([name, price, station, system])
        dataTable = t2a.table2ascii(
            header=headers,
            body=data,
            alignments=[0,0,0,0],
        )
        return dataTable

    def createGraphFromCommodityData(self, commodities):
        fig = plt.figure(clear=True, figsize=(7.5, 5), dpi=100)
        ax = fig.gca()
        ax.grid(True)
        
        ax.xaxis.set_major_formatter(xfmt)
        #ax.xaxis.set_major_locator(xfml)
        
        #set rotation for x axis
        plt.xticks(**{"family": "Consolas", "size": 10})
        plt.yticks(**{"family": "Consolas", "size": 10})

        unixTimeOfData = []

        for id in commodities:
            latestData = self.mainDatabase.getLatestByTime(id, 24)
            x, y = [], []
            
            for record in latestData:
                unixTimeOfData.append(record["timestamp"])
                x.append(datetime.datetime.fromtimestamp(record["timestamp"]))
                y.append(record["price"])
           
            #add annotations
            #plt.annotate(f"{y[0]} Cr", (x[0], y[0]), **{"family": "Consolas", "size": 10})
            plt.annotate(f"{y[-1]} Cr", (x[-1], y[-1]), **{"family": "Consolas", "size": 10})

            #plot data
            ax.plot(x, y, label=aviableCommodities[id])
            ax.scatter(x, y, s=5)

        #set graph properties
        timeFrom = time.strftime("%d/%m/%Y", time.localtime(min(unixTimeOfData)))
        timeTo = time.strftime("%d/%m/%Y", time.localtime(max(unixTimeOfData)))

        plt.title("Commodity Prices", **plotFont)
        plt.xlabel(f"Time({timeFrom} to {timeTo})", **plotFont)
        plt.ylabel("Price", **plotFont)
        ax.legend()

        #save graph to buffer
        buf = io.BytesIO()
        fig.savefig(buf, format="png")
        buf.seek(0)
        return buf

    async def alertChecker(self):
        for guild in self.alertDatabase.database.keys():
            for commodity in self.alertDatabase.get(guild).keys():
                alert = self.alertDatabase.get(guild)[commodity]
                latestRecord = self.mainDatabase.getLatest(commodity)[0]
                if latestRecord["price"] >= alert["alertPrice"]:
                    channelID = self.guildInfoDatabase.get(guild)["updateChannelID"]
                    channel = self.bot.get_channel(channelID)
                    embed = discord.Embed(title=f"Alert for {aviableCommodities[commodity]}:", color=0x00ff00)
                    embed.description = f"Price is now {'{:,}'.format(latestRecord['price'])} Cr\nStation: {latestRecord['station']}\nSystem: {latestRecord['system']}"
                    embed.set_footer(text=f"Alert set by {self.bot.get_user(alert['alertUserID']).name}")
                    await channel.send(content=f"Alert <@&{alert['alertRoleID']}>!", embed=embed, view=alertMessageView(self.alertDatabase, commodity))

    @app_commands.command(name="debug", description="Debug command")
    async def debug(self, interaction):
        await interaction.response.defer()
        await interaction.edit_original_response(content="Debugging...", view=alertMessageView(self.alertDatabase, aviableCommodities, "350"))

    @app_commands.command(name="commodity", description="Shows the commodity data from EDDB.IO")
    async def commodity(self, interaction):
        await interaction.response.defer()
        embed = discord.Embed(title="Select commodities you want data from:", color=0x00ff00)
        await interaction.edit_original_response(embed=embed, view=commodityTableView(self.createTableFromCommodityData, self.latestUpdate))
    
    @app_commands.command(name="update", description="Updates the commodity data")
    async def update(self, interaction):
        await interaction.response.defer()
        #remove last message
        channel = self.bot.get_channel(interaction.channel_id)
        await interaction.followup.send(content="Updating data...")
        #update data
        dataTable = self.createTableFromCommodityData(aviableCommodities.keys())
      
        if self.guildInfoDatabase.exists(str(interaction.guild.id)):
            channelID = self.guildInfoDatabase.get(str(interaction.guild.id))["updateChannelID"]
            messageID = self.guildInfoDatabase.get(str(interaction.guild.id))["updateMessageID"]
            channel = self.bot.get_channel(channelID)
            if int(channelID) == interaction.channel_id: await interaction.delete_original_response()
            else: await interaction.edit_original_response(content=f"Data updated in <#{channelID}>!", embed=None, view=None)
            message = await channel.fetch_message(messageID)
            await message.edit(content=f"```{dataTable}\nLatest database update: {time.strftime('%H:%M:%S %d-%m-%Y', self.latestUpdate)}```", embed=None, view=None)
        else:
            await interaction.edit_original_response("No update channel set! Use the `/setupdatechannel` command to set one!")

    @app_commands.command(name="setupdatechannel", description="Sets the channel where the update command will post the data")
    async def setUpdateChannel(self, interaction):
        await interaction.response.defer()
        await interaction.edit_original_response(content="Set update channel to this channel!", embed=None, view=None)
        await interaction.channel.send(content="This is the message that will contain update data!")
        async for msg in interaction.channel.history(limit=1):
            msgID = msg.id
        self.guildInfoDatabase.set(str(interaction.guild.id), {"updateChannelID": interaction.channel_id, "updateMessageID": msgID})
        await interaction.delete_original_response()

    @app_commands.command(name="graph", description="Shows the graph of a commodity/commodities")
    async def graph(self, interaction):
        await interaction.response.defer()
        embed = discord.Embed(title="Select commodities you want data from:", color=0x00ff00)
        await interaction.edit_original_response(embed=embed, view=commodityGraphView(self.createGraphFromCommodityData))

    @app_commands.command(name="alert", description="Sets an alert for a commodity")
    @app_commands.choices(commodity=alertOptions)
    async def alert(self, interaction, commodity: str, price: int, role: discord.Role):
        await interaction.response.defer()
        if not self.alertDatabase.exists(str(interaction.guild.id)): self.alertDatabase.set(str(interaction.guild.id), {})
        self.alertDatabase.set(str(interaction.guild.id), {commodity: {"alertPrice": price, "alertRoleID": role.id, "alertUserID": interaction.user.id}})
        await interaction.edit_original_response(content=f"Alert set for {aviableCommodities[commodity]} at {'{:,}'.format(price)} Cr!", embed=None, view=None)

    @tasks.loop(hours=1, reconnect=True)
    async def updateCommodityDatabase(self):
        await self.bot.wait_until_ready()
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
        for id in aviableCommodities.keys(): self.mainDatabase.add(id, updateData[id], False)
        
        self.latestUpdate = time.localtime()
        self.updating = False
        log.logInfo("Updated commodity database", "eliteData.database")
        await self.alertChecker()

async def setup(bot):
    log.logInfo("Loading eliteData", "setup.cogs")
    await bot.add_cog(eliteData(bot))