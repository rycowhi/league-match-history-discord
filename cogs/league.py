import datetime
import itertools
from typing import Dict

import discord
import requests
from discord.ext import commands


# https://medium.com/the-esports-analyst-club-by-itero-gaming/becoming-a-lol-analyst-an-introduction-to-using-the-riot-api-bb145ec8eb50
def get_account(game_name: str, tag_line, api_key):
    uri = f"https://americas.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{game_name}/{tag_line}?api_key={api_key}"

    response = requests.get(uri)
    response.raise_for_status()

    return response.json()


def get_match_ids_window(
    puuid: str, start_time_epoch: int, end_time_epoch: int, api_key: str
):
    uri = f"https://americas.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids?startTime={start_time_epoch}&endTime={end_time_epoch}&start=0&count=20&api_key={api_key}"
    response = requests.get(uri)
    response.raise_for_status()

    return response.json()


def get_match_details(match_id: str, api_key: str):
    uri = f"https://americas.api.riotgames.com/lol/match/v5/matches/{match_id}?api_key={api_key}"
    response = requests.get(uri)
    response.raise_for_status()

    return response.json()


def determine_match_type(match_details: dict) -> str:
    game_mode = match_details["info"]["gameMode"]
    queue_id = str(match_details["info"]["queueId"])

    match (game_mode, queue_id):
        case ("CLASSIC", "400"):
            return "Summoner's Rift (Draft Pick)"
        case ("ARAM", "450"):
            return "All Random All Mid (ARAM)"
        case ("CHERRY", "1700"):
            return "Arena"
        case _:
            return f"{game_mode}{queue_id}"


def did_player_win_match(puuid: str, match_details: dict) -> bool:
    matched_participant_details = next(
        participant
        for participant in match_details["info"]["participants"]
        if participant["puuid"] == puuid
    )

    return matched_participant_details["win"]


def get_midnight_and_now_epoch() -> tuple[int, int]:
    # https://stackoverflow.com/a/76317438
    current_time = datetime.datetime.now()
    midnight = datetime.datetime.combine(current_time, datetime.datetime.min.time())

    # TODO remove week override
    # midnight = midnight - datetime.timedelta(days=14)

    midnight_time_epoch = int(midnight.timestamp())
    current_time_epoch = int(current_time.timestamp())

    return (midnight_time_epoch, current_time_epoch)


class League(commands.Cog):
    league_slash_command_group = discord.SlashCommandGroup(
        name="league", description="League of Legends-related commands."
    )

    def __init__(self, bot: discord.bot.Bot, config: Dict[str, str]):
        """xd

        :param discord.bot.Bot bot: _description_
        :param Dict[str, str] config: _description_
        """
        self.bot = bot
        self.config = config

    @league_slash_command_group.command(
        description="Give a summary about a player's daily matches."
    )
    async def daily_matches(
        self,
        ctx: discord.commands.context.ApplicationContext,
        player_name: discord.Option(
            input_type=str,
            description="The name of the player to lookup matches for. Should be in format PlayerName#TagLine.",
        ),  # type: ignore - this is simply how py-cord does options
    ):
        # TODO get an embed?
        # https://guide.pycord.dev/getting-started/more-features eventually... todo
        print(f"USER PROVIDED {player_name}")

        # RIOT API serach can take a while, this takes us past the 3 second default wait
        await ctx.defer()

        api_key = self.config["RIOT_API_KEY"]
        midnight_epoch, current_time_epoch = get_midnight_and_now_epoch()

        if "#" not in player_name:
            await ctx.respond(
                f"The supplied name '{player_name}' is not in the expected format 'PlayerName#TagLine'."
            )
        else:
            (player_name, tag_line) = player_name.split("#")

            account = get_account(player_name, tag_line, api_key)
            puuid = account["puuid"]

            match_ids = get_match_ids_window(
                puuid=puuid,
                start_time_epoch=midnight_epoch,
                end_time_epoch=current_time_epoch,
                api_key=api_key,
            )
            match_details = [
                get_match_details(match_id, api_key) for match_id in match_ids
            ]
            match_results = [
                (determine_match_type(match), did_player_win_match(puuid, match))
                for match in match_details
            ]

            matches_played = len(match_results)
            wins = len(list(filter(lambda result: result[1], match_results)))

            message = f"***{player_name}#{tag_line}*** played {matches_played} games and won {wins} today."
            # Thumbnail?
            embed = discord.Embed(
                title=f"Match Overview for {player_name}#{tag_line}",
                description=message,
                color=discord.Colour.blurple(),  # Pycord provides a class with default colors you can choose from,
                thumbnail="https://static.wikia.nocookie.net/leagueoflegends/images/9/9a/League_of_Legends_Update_Logo_Concept_05.jpg/revision/latest/scale-to-width-down/250?cb=20191029062637",  # TODO maybe this?
            )

            match_results_by_type = itertools.groupby(match_results, key=lambda x: x[0])
            for match_type, match_type_and_results in match_results_by_type:
                match_type_match_results = [
                    item[1] for item in list(match_type_and_results)
                ]
                print(match_type_match_results)
                total_games = len(match_type_match_results)
                wins = len([result for result in match_type_match_results if result])
                losses = total_games = total_games - wins
                print("===")

                embed.add_field(
                    name=f"{match_type}",
                    value=f"***Wins:*** {wins} - ***Losses:*** {losses}",
                    inline=False,
                )

            embed.set_footer(
                text="Jolly Bot - a homegrown Discord bot by RyCo"
            )  # footers can have icons too
            embed.set_image(
                url="https://ddragon.leagueoflegends.com/cdn/img/champion/splash/Briar_0.jpg"
            )

            await ctx.respond(embed=embed)  # Send the embed with some text


# TODO docs, required by add cog
def setup(bot: discord.bot.Bot):
    """_summary_
    Setup function for
    :param bot: _description_
    :type bot: discord.bot.Bot
    """
    import dotenv

    # TODO hwo does shpnix or other do a click thru to the other bit?

    config = dotenv.dotenv_values(".env")
    bot.add_cog(League(bot=bot, config=config))
