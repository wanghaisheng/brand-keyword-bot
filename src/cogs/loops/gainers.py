# > 3rd party dependencies
import yahoo_fin.stock_info as si
import pandas as pd
import datetime

# > Discord dependencies
import discord
from discord.ext import commands
from discord.ext.tasks import loop

# Local dependencies
from util.vars import config, get_json_data
from util.disc_util import get_channel
from util.afterhours import afterHours
from util.formatting import format_embed


class Gainers(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        if config["LOOPS"]["GAINERS"]["STOCKS"]["ENABLED"]:
            self.stocks_channel = get_channel(self.bot, config["LOOPS"]["GAINERS"]["STOCKS"]["CHANNEL"])
            self.stocks.start()
            
        if config["LOOPS"]["GAINERS"]["CRYPTO"]["ENABLED"]:
            self.crypto_gainers_channel = get_channel(self.bot, config["LOOPS"]["GAINERS"]["CRYPTO"]["CHANNEL"])
            
        if config["LOOPS"]["LOSERS"]["CRYPTO"]["ENABLED"]:
            self.crypto_losers_channel = get_channel(self.bot, config["LOOPS"]["LOSERS"]["CRYPTO"]["CHANNEL"])
            
        if config["LOOPS"]["GAINERS"]["CRYPTO"]["ENABLED"] or config["LOOPS"]["LOSERS"]["CRYPTO"]["ENABLED"]:
            self.crypto.start()

    @loop(hours=2)
    async def crypto(self):
        """
        This loop will check the gainers and losers on Binance, using USDT as the base currency.
        To prevent too many calls the losers are also done in this section.
        """
        
        binance_data = await get_json_data("https://api.binance.com/api/v3/ticker/24hr")

        # If the call did not work
        if not binance_data:
            return

        # Cast to dataframe
        df = pd.DataFrame(binance_data)

        # Keep only the USDT pairs
        df = df[df["symbol"].str.contains("USDT")]

        # Remove USDT from the symbol
        df["symbol"] = df["symbol"].str.replace("USDT", "")

        df[["priceChangePercent", "weightedAvgPrice", "volume"]] = df[
            ["priceChangePercent", "weightedAvgPrice", "volume"]
        ].apply(pd.to_numeric)

        # Sort on priceChangePercent
        sorted = df.sort_values(by="priceChangePercent", ascending=False)

        sorted.rename(
            columns={
                "symbol": "Symbol",
                "priceChangePercent": "% Change",
                "weightedAvgPrice": "Price",
                "volume": "Volume",
            },
            inplace=True,
        )

        # Post the top 10 highest
        gainers = sorted.head(10)

        # Post the top 10 lowest
        losers = sorted.tail(10)
        losers = losers.iloc[::-1]

        # Format the embed
        e_gainers = await format_embed(gainers, "Gainers", "binance")
        e_losers = await format_embed(losers, "Losers", "binance")

        # Post the embed in the channel
        if config["LOOPS"]["GAINERS"]["CRYPTO"]["ENABLED"]:
            await self.crypto_gainers_channel.send(embed=e_gainers)
        
        if config["LOOPS"]["LOSERS"]["CRYPTO"]["ENABLED"]:
            await self.crypto_losers_channel.send(embed=e_losers)

    @loop(hours=2)
    async def stocks(self):

        # Dont send if the market is closed
        if afterHours():
            return

        gainers = si.get_day_gainers()[
            ["Symbol", "Price (Intraday)", "% Change", "Volume"]
        ].head(50)

        gainers.rename(columns={"Price (Intraday)": "Price"}, inplace=True)

        e = await format_embed(gainers, "Gainers", "yahoo")

        await self.stocks_channel.send(embed=e)


def setup(bot):
    bot.add_cog(Gainers(bot))
