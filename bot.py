import os
import discord
import requests
import asyncio
from datetime import datetime, timedelta
from dotenv import load_dotenv
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from bs4 import BeautifulSoup

load_dotenv()
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
CHANNEL_ID = int(os.getenv('DISCORD_CHANNEL_ID'))

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)
gesendete_alarme = set()

def hole_wirtschaftskalender():
    events_list = []
    try:
        url = "https://www.investing.com/economic-calendar/"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"}
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'lxml')
        event_rows = soup.find_all('tr', id=lambda x: x and x.startswith('eventRowId_'))
        for row in event_rows:
            zeit = row.find('td', class_='time').text.strip() if row.find('td', class_='time') else 'N/A'
            waehrung = row.find('td', class_='flagCur').text.strip() if row.find('td', class_='flagCur') else 'N/A'
            impact_td = row.find('td', class_='sentiment')
            if impact_td:
                bulls = len(impact_td.find_all('i', class_='grayFullBull'))
                impact = "High" if bulls == 3 else "Medium" if bulls == 2 else "Low"
            else:
                impact = 'N/A'
            ereignis_name = row.find('td', class_='event').text.strip() if row.find('td', class_='event') else 'Unbekanntes Ereignis'
            events_list.append({'time': zeit, 'currency': waehrung, 'impact': impact, 'event': ereignis_name})
        return events_list
    except Exception as e:
        print(f"Fehler beim Web Scraping: {e}")
        return []

async def sende_tagesuebersicht():
    global gesendete_alarme
    gesendete_alarme.clear()
    channel = client.get_channel(CHANNEL_ID)
    if not channel: return
    events = hole_wirtschaftskalender()
    if not events:
        await channel.send("Für heute wurden keine Wirtschaftsereignisse gefunden.")
        return
    embed = discord.Embed(title=f"Wirtschaftskalender für {datetime.now().strftime('%d.%m.%Y')}", description="Die wichtigsten Ereignisse des Tages.", color=discord.Color.blue())
    for event in events:
        embed.add_field(name=f"🕒 {event['time']} - {event['currency']} - {event['event']}", value=f"**Wichtigkeit:** {event['impact']}", inline=False)
    embed.set_footer(text="Daten von investing.com")
    await channel.send(embed=embed)
    print("Tagesübersicht gesendet.")

async def pruefe_und_sende_alarme():
    global gesendete_alarme
    channel = client.get_channel(CHANNEL_ID)
    if not channel: return
    events = hole_wirtschaftskalender()
    if not events: return
    jetzt = datetime.now()
    for event in events:
        if event.get('impact') == "High" and event.get('time') and ":" in event.get('time'):
            try:
                stunde, minute = map(int, event['time'].split(':'))
                event_zeit = jetzt.replace(hour=stunde, minute=minute, second=0, microsecond=0)
                zeit_bis_event = event_zeit - jetzt
                if timedelta(minutes=14) < zeit_bis_event <= timedelta(minutes=15):
                    alarm_id = f"{event_zeit.strftime('%H:%M')}-{event.get('event')}"
                    if alarm_id not in gesendete_alarme:
                        embed = discord.Embed(title="🚨 ALARM: WICHTIGES EREIGNIS IN 15 MINUTEN 🚨", description=f"**Ereignis:** {event.get('event')}\n**Währung:** {event.get('currency')}", color=discord.Color.red())
                        await channel.send(embed=embed)
                        gesendete_alarme.add(alarm_id)
                        print(f"Alarm für '{event.get('event')}' gesendet.")
            except (ValueError, IndexError):
                continue

@client.event
async def on_ready():
    print(f'{client.user} ist jetzt online!')
    scheduler = AsyncIOScheduler(timezone="Europe/Berlin")
    scheduler.add_job(sende_tagesuebersicht, CronTrigger(hour=8, minute=0))
    scheduler.add_job(pruefe_und_sende_alarme, 'interval', minutes=1)
    scheduler.start()

client.run(DISCORD_TOKEN)
