import discord
from discord.ext import commands, tasks
import requests
import datetime
import config

intents = discord.Intents.default()
intents.messages = True

bot = commands.Bot(command_prefix="!", intents=intents)

def get_economic_calendar(country):
    url = f"https://api.tradingeconomics.com/calendar/country/{country}?c={config.TRADING_ECONOMICS_API_KEY}"
    response = requests.get(url)
    if response.status_code == 200:
        return response.json()
    else:
        return None

@bot.event
async def on_ready():
    print(f"Bot ist eingeloggt als {bot.user}")
    economic_calendar.start()

@tasks.loop(minutes=30)
async def economic_calendar():
    now = datetime.datetime.now()
    current_hour = now.hour

    if 8 <= current_hour <= 22:
        channel = bot.get_channel(config.CHANNEL_ID)
        today = now.strftime("%Y-%m-%d")
        
        germany_data = get_economic_calendar('Germany')
        usa_data = get_economic_calendar('United States')

        message = f"📅 **Wirtschaftskalender Update {now.strftime('%H:%M')} Uhr**\n\n"
        
        if germany_data:
            message += "🇩🇪 **Deutschland**:\n"
            for event in germany_data:
                if event['Date'].startswith(today):
                    message += f"- {event['Date'][11:16]} Uhr: {event['Event']}\n"
        else:
            message += "Keine Termine für Deutschland gefunden.\n"

        message += "\n"
        
        if usa_data:
            message += "🇺🇸 **USA**:\n"
            for event in usa_data:
                if event['Date'].startswith(today):
                    message += f"- {event['Date'][11:16]} Uhr: {event['Event']}\n"
        else:
            message += "Keine Termine für USA gefunden.\n"

        await channel.send(message)
    else:
        print(f"Ignoriert um {now.strftime('%H:%M')} (außerhalb 8-22 Uhr)")

bot.run(config.DISCORD_TOKEN)
