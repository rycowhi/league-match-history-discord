import discord
import dotenv

if __name__ == "__main__":
    config = dotenv.dotenv_values(".env")
    api_key = config["RIOT_API_KEY"]
    discord_token = config["DISCORD_TOKEN"]

    bot = discord.Bot()
    bot.load_extension("cogs.league")
    bot.run(discord_token)
