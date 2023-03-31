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
    def __init__(self, path: str) -> None:
        self.databasePath: str = path
        self.databaseObject = open(self.databasePath, "r")
        self.database: dict = json.load(self.databaseObject)
        self.latestUpdate: int = 0
    
    def get(self, key: str) -> dict: return self.database[key]
    
    def getLatest(self, key: str, index: int = -1) -> dict: return self.database[key][index:]

    def getLatestByTime(self, key: str, latestTime: int = 24) -> list:
        latestTimeGet = self.getLatest(key)[0]["timestamp"] - latestTime * 60 * 60
        return [i for i in self.database[key] if i["timestamp"] > latestTimeGet]

    def add(self, key: str, value: any, replaceIdentical: bool = False) -> None:
        if replaceIdentical:
            if self.getLatest(key)[0]["price"] == value["price"]:
                self.setLatest(key, value)
            else: self.append(key, value)
        else: self.append(key, value)

    def set(self, key: str, value: any) -> None:
        if key not in self.database.keys(): self.create(key, value)
        else: self.database[key] = value
        self.save()
    
    def setLatest(self, key: str, value: any) -> None:
        self.database[key][-1] = value
        self.save()
    
    def create(self, key: str, value: any) -> None:
        self.database[key] = value
        self.save()

    def append(self, key: str, value: any) -> None:
        self.database[key].append(value)
        self.save()
    
    def appendDict(self, key: str, dictKey: str, dictValues: dict) -> None:
        self.database[key][dictKey] = dictValues
        self.save()
    
    def save(self, reopen: bool = True) -> None:
        self.databaseObject = open(self.databasePath, "w")
        json.dump(self.database, self.databaseObject, indent=4)
        self.databaseObject.close()
        self.latestUpdate = time.time()
        if reopen: self.load()
    
    def load(self) -> None:
        self.databaseObject = open(self.databasePath, "r")
        self.database = json.load(self.databaseObject)

    def close(self) -> None: self.databaseObject.close()
    
    def exists(self, key: str) -> bool: return key in self.database.keys()

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
    def __init__(self, createTableFromCommodityData, latestUpdate: int, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.callback = self.commoditySelectCallback
        self.createTableFromCommodityData = createTableFromCommodityData
        self.latestUpdate = latestUpdate

    async def commoditySelectCallback(self, interaction: discord.Interaction) -> None:
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
    def __init__(self, createGraphFromCommodityData, hours: int = 24):
        super().__init__()
        self.add_item(commodityGraphSelect(
            options=selectOptions,
            placeholder="Select a commodity",
            min_values=1,
            max_values=len(selectOptions),
            createGraphFromCommodityData = createGraphFromCommodityData,
            hours = hours
        ))

class commodityGraphSelect(Select):
    def __init__(self, options, placeholder, min_values, max_values, createGraphFromCommodityData, hours):
        super().__init__(options=options, placeholder=placeholder, min_values=min_values, max_values=max_values)
        self.callback = self.graphSelectCallback
        self.createGraphFromCommodityData = createGraphFromCommodityData
        self.hours = hours
    
    async def graphSelectCallback(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        selectedResources = self.values
        await interaction.edit_original_response(content="Generating graph...", embed=None, view=None)
        graphImage = self.createGraphFromCommodityData(selectedResources, self.hours)
        graphFile = discord.File(graphImage, filename="graph.png")
        await interaction.edit_original_response(content=None, embed=None, view=None, attachments=[graphFile])

class alertMessageView(View):
    def __init__(self, alertDatabase, commodityID):
        super().__init__()
        self.alertDatabase = alertDatabase
        self.commodityID = commodityID

    @discord.ui.button(label="Keep alert", style=discord.ButtonStyle.gray)
    async def keepAlert(self, interaction: discord.Interaction, button: discord.ui.Button):
        guildAlerts = self.alertDatabase.get(str(interaction.guild.id))
        del guildAlerts[self.commodityID]
        self.alertDatabase.set(str(interaction.guild.id), guildAlerts)
        await interaction.response.edit_message(view=None)

    @discord.ui.button(label="Dismiss", style=discord.ButtonStyle.gray)
    async def dismiss(self, interaction: discord.Interaction, button: discord.ui.Button):
        commodityName = aviableCommodities[self.commodityID] if self.commodityID != "all" else "all commodities"
        await interaction.response.edit_message(content=f"Alert for {commodityName} dismissed!", embed=None, view=None, delete_after=10)
        guildAlerts = self.alertDatabase.get(str(interaction.guild.id))
        del guildAlerts[self.commodityID]
        self.alertDatabase.set(str(interaction.guild.id), guildAlerts)
    
    @discord.ui.button(label="Alert me again", style=discord.ButtonStyle.gray)
    async def alertAgain(self, interaction: discord.Interaction, button: discord.ui.Button):
        commodityName = aviableCommodities[self.commodityID] if self.commodityID != "all" else "all commodities"
        await interaction.response.edit_message(content=f"Alert for {commodityName} has been reset!", embed=None, view=None, delete_after=10)

class eliteData(commands.Cog):
    def __init__(self: commands.Cog, bot: commands.Bot) -> None:
        self.bot: commands.Bot = bot

        self.mainDatabase: database = database(r"database\main.json")
        self.guildInfoDatabase: database = database(r"database\guildInfo.json")
        self.alertDatabase: database = database(r"database\alerts.json")
        
        self.updating: bool = False
        self.latestUpdate: int = 0
        self.updateCommodityDatabase.start()

        self.edsmDatabaseLink: str = "https://www.edsm.net/api-v1"
        self.eddbCommodityLink: str = "https://eddb.io/commodity/"
    
    def isApprovedGuild() -> app_commands.check:
        def predicate(interaction: discord.Interaction):
            return interaction.guild.id in approvedGuilds
        return app_commands.check(predicate)

    def scrapePriceFromEDDB(self: commands.Cog, resourceID: str) -> list[str]:
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
    
    def createTableFromCommodityData(self: commands.Cog, selectedResources: list[str]) -> t2a.table2ascii:
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

    def createGraphFromCommodityData(self: commands.Cog, commodities: list[str], hours: int = 24) -> io.BytesIO:
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
            latestData = self.mainDatabase.getLatestByTime(id, hours)
            x, y = [], []
            
            for record in latestData:
                unixTimeOfData.append(record["timestamp"])
                x.append(datetime.datetime.fromtimestamp(record["timestamp"]))
                y.append(record["price"])

            #plot data
            ax.plot(x, y, label=aviableCommodities[id])

        #set graph properties
        timeFrom = time.strftime("%d/%m/%Y", time.localtime(min(unixTimeOfData)))
        timeTo = time.strftime("%d/%m/%Y", time.localtime(max(unixTimeOfData)))

        plt.title("Commodity Prices", **plotFont)
        plt.xlabel(f"Time({timeFrom} to {timeTo})", **plotFont)
        plt.ylabel("Price", **plotFont)
        ax.legend()

        #save graph to buffer
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=300)
        buf.seek(0)
        return buf

    async def alertChecker(self: commands.Cog) -> None:
        for guild in self.alertDatabase.database.keys():
            for commodity in self.alertDatabase.get(guild).keys():
                alert = self.alertDatabase.get(guild)[commodity]
                if commodity == "all":
                    embed = discord.Embed(title=f"Alert for all commodities has been triggered!", color=0x00ff00)
                    channelID = self.guildInfoDatabase.get(guild)["updateChannelID"]
                    channel = self.bot.get_channel(channelID)
                    for id in aviableCommodities:
                        latestRecord = self.mainDatabase.getLatest(id)[0]
                        if latestRecord["price"] >= alert["alertPrice"]:
                            embed.add_field(name=aviableCommodities[id], value=f"Price is now {'{:,}'.format(latestRecord['price'])} Cr\nStation: {latestRecord['station']}\nSystem: {latestRecord['system']}", inline=False)
                    embed.set_footer(text=f"Alert set by {self.bot.get_user(alert['alertUserID']).name}")
                    if embed.fields:
                        await channel.send(content=f"Alert <@&{alert['alertRoleID']}>!", embed=embed, view=alertMessageView(self.alertDatabase, commodity))
                else:
                    latestRecord = self.mainDatabase.getLatest(commodity)[0]
                    if latestRecord["price"] >= alert["alertPrice"]:
                        channelID = self.guildInfoDatabase.get(guild)["updateChannelID"]
                        channel = self.bot.get_channel(channelID)
                        embed = discord.Embed(title=f"Alert for {aviableCommodities[commodity]} has been triggered!", color=0x00ff00)
                        embed.add_field(name=aviableCommodities[commodity], value=f"Price is now {'{:,}'.format(latestRecord['price'])} Cr\nStation: {latestRecord['station']}\nSystem: {latestRecord['system']}")
                        embed.set_footer(text=f"Alert set by {self.bot.get_user(alert['alertUserID']).name}")
                        await channel.send(content=f"Alert <@&{alert['alertRoleID']}>!", embed=embed, view=alertMessageView(self.alertDatabase, commodity))

    @app_commands.command(name="debug", description="Debug command")
    @isApprovedGuild()
    async def debug(self: commands.Cog, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        await interaction.edit_original_response(content="Debugging...", view=alertMessageView(self.alertDatabase, aviableCommodities, "350"))

    @app_commands.command(name="commodity", description="Shows the commodity data from EDDB.IO")
    async def commodity(self: commands.Cog, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        embed = discord.Embed(title="Select commodities you want data from:", color=0x00ff00)
        await interaction.edit_original_response(embed=embed, view=commodityTableView(self.createTableFromCommodityData, self.latestUpdate))
    
    @app_commands.command(name="update", description="Updates the commodity data")
    async def update(self: commands.Cog, interaction: discord.Interaction) -> None:
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
    async def setUpdateChannel(self: commands.Cog, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        await interaction.edit_original_response(content="Set update channel to this channel!", embed=None, view=None)
        await interaction.channel.send(content="This is the message that will contain update data!")
        async for msg in interaction.channel.history(limit=1):
            msgID = msg.id
        self.guildInfoDatabase.set(str(interaction.guild.id), {"updateChannelID": interaction.channel_id, "updateMessageID": msgID})
        await interaction.delete_original_response()

    @app_commands.command(name="graph", description="Shows the graph of a commodity/commodities")
    async def graph(self: commands.Cog, interaction: discord.Interaction, hours: int = 24) -> None:
        await interaction.response.defer()
        embed = discord.Embed(title="Select commodities you want data from:", color=0x00ff00)
        await interaction.edit_original_response(embed=embed, view=commodityGraphView(createGraphFromCommodityData=self.createGraphFromCommodityData, hours=hours))

    @app_commands.command(name="alert", description="Sets an alert for a commodity")
    @app_commands.choices(commodity=[discord.app_commands.Choice(name="All", value="all"),*alertOptions])
    async def alert(self: commands.Cog, interaction: discord.Interaction, commodity: str, price: int, role: discord.Role) -> None:
        await interaction.response.defer()
        commodityName =  aviableCommodities[commodity] if commodity != "all" else "all commodities"
        if not self.alertDatabase.exists(str(interaction.guild.id)): self.alertDatabase.set(str(interaction.guild.id), {}); print("new guild")
        self.alertDatabase.appendDict(str(interaction.guild.id), commodity, {"alertPrice": price, "alertRoleID": role.id, "alertUserID": interaction.user.id})
        await interaction.edit_original_response(content=f"Alert set for {commodityName} at {'{:,}'.format(price)} Cr!", embed=None, view=None)
    
    @app_commands.command(name="removealert", description="Removes an alert for a commodity")
    @app_commands.choices(commodity=alertOptions)
    async def removeAlert(self: commands.Cog, interaction: discord.Interaction, commodity: str) -> None:
        guildAlerts = self.alertDatabase.get(str(interaction.guild.id))
        if commodity in guildAlerts.keys():
            alertInfo = guildAlerts[commodity]
            del guildAlerts[commodity]
            self.alertDatabase.set(str(interaction.guild.id), guildAlerts)
            interaction.edit_original_response(content=f"Alert at {alertInfo['alertPrice']} removed for {aviableCommodities[commodity]}!", embed=None, view=None)
        else:
            interaction.edit_original_response(content=f"No alert set for {aviableCommodities[commodity]}!", embed=None, view=None)
    
    @app_commands.command(name="alerts", description="Shows all alerts for the guild")
    async def alerts(self: commands.Cog, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        if not self.alertDatabase.exists(str(interaction.guild.id)): self.alertDatabase.set(str(interaction.guild.id), {})
        guildAlerts = self.alertDatabase.get(str(interaction.guild.id))
        if guildAlerts == {}: await interaction.edit_original_response(content="No alerts set!", embed=None, view=None)
        else:
            embed = discord.Embed(title="Alerts:", color=0x00ff00)
            for commodity in guildAlerts.keys():
                embed.add_field(name=aviableCommodities[commodity], value=f"Price: {'{:,}'.format(guildAlerts[commodity]['alertPrice'])} Cr\nRole: <@&{guildAlerts[commodity]['alertRoleID']}>\nSet by ", inline=False)
            await interaction.edit_original_response(content=None, embed=embed, view=None)

    @tasks.loop(hours=1, reconnect=True)
    async def updateCommodityDatabase(self: commands.Cog) -> None:
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