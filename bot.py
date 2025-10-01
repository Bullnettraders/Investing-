import os
import discord
import requests
import asyncio
from datetime import datetime, timedelta
from dotenv import load_dotenv
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from bs4 import BeautifulSoup # Neu hinzugefügt für Web Scraping

# Lädt die Umgebungsvariablen aus der .env Datei
load_dotenv()
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
# FMP_API_KEY wird nicht mehr benötigt
CHANNEL_ID = int(os.getenv('DISCORD_CHANNEL_ID'))

# --- Discord Bot Setup ---
intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

# Globale Variable, um doppelte Alarm-Nachrichten zu verhindern
gesendete_alarme = set()

# --- Web Scraping Funktion (ersetzt die alte API-Funktion) ---

def hole_wirtschaftskalender():
    """
    Liest die heutigen Wirtschaftsdaten per Web Scraping von investing.com aus.
    Diese Funktion benötigt keinen API-Schlüssel.
    """
    events_list = []
    try:
        # URL des Wirtschaftskalenders
        url = "https://www.investing.com/economic-calendar/"
        
        # Wichtig: Wir senden einen "User-Agent"-Header, um uns als Browser auszugeben.
        # Viele Webseiten blockieren Anfragen ohne diesen Header.
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        
        response = requests.get(url, headers=headers)
        response.raise_for_status() # Wirft einen Fehler bei HTTP-Problemen

        # Wir benutzen BeautifulSoup, um das HTML der Seite zu analysieren
        soup = BeautifulSoup(response.text, 'lxml')

        # Wir suchen die Tabelle mit den heutigen Events
        # Die Event-Zeilen haben eine ID, die mit 'eventRowId_' beginnt
        event_rows = soup.find_all('tr', id=lambda x: x and x.startswith('eventRowId_'))
        
        for row in event_rows:
            # Zeit des Events auslesen
            zeit_td = row.find('td', class_='time')
            zeit = zeit_td.text.strip() if zeit_td else 'N/A'

            # Währung auslesen
            waehrung_td = row.find('td', class_='flagCur')
            waehrung = waehrung_td.text.strip() if waehrung_td else 'N/A'
            
            # Wichtigkeit (Impact) auslesen
            # Die Wichtigkeit wird durch "Bullenköpfe" dargestellt. Wir zählen sie.
            impact_td = row.find('td', class_='sentiment')
            if impact_td:
                bulls = len(impact_td.find_all('i', class_='grayFullBull'))
                if bulls == 3:
                    impact = "High"
                elif bulls == 2:
                    impact = "Medium"
                else:
                    impact = "Low"
            else:
                impact = 'N/A'

            # Name des Events auslesen
            event_td = row.find('td', class_='event')
            ereignis_name = event_td.text.strip() if event_td else 'Unbekanntes Ereignis'
            
            events_list.append({
                'time': zeit,
                'currency': waehrung,
                'impact': impact,
                'event': ereignis_name
            })
            
        return events_list

    except requests.exceptions.RequestException as e:
        print(f"Fehler beim Abrufen der Webseite: {e}")
        return [] # Gibt eine leere Liste zurück, damit der Bot nicht abstürzt
    except Exception as e:
        print(f"Ein unerwarteter Fehler ist aufgetreten: {e}")
        return []


# --- Bot-Logik (bleibt größtenteils gleich!) ---

async def sende_tagesuebersicht():
    """Erstellt und sendet die tägliche Übersicht der Wirtschaftsereignisse."""
    global gesendete_alarme
    gesendete_alarme.clear()

    channel = client.get_channel(CHANNEL_ID)
    if not channel:
        print(f"Fehler: Kanal mit ID {CHANNEL_ID} nicht gefunden.")
        return

    events = hole_wirtschaftskalender()
    
    if not events:
        await channel.send("Für heute wurden keine Wirtschaftsereignisse gefunden oder die Seite konnte nicht gelesen werden.")
        return

    embed = discord.Embed(
        title=f"Wirtschaftskalender für {datetime.now().strftime('%d.%m.%Y')}",
        description="Hier ist die heutige Übersicht der wichtigsten Ereignisse.",
        color=discord.Color.blue()
    )

    for event in events:
        embed.add_field(
            name=f"🕒 {event['time']} - {event['currency']} - {event['event']}",
            value=f"**Wichtigkeit:** {event['impact']}",
            inline=False
        )
    
    embed.set_footer(text="Daten von investing.com")
    await channel.send(embed=embed)
    print("Tagesübersicht erfolgreich gesendet.")


async def pruefe_und_sende_alarme():
    """Prüft alle paar Minuten, ob bald ein wichtiges Ereignis ansteht."""
    global gesendete_alarme
    
    channel = client.get_channel(CHANNEL_ID)
    if not channel:
        return

    events = hole_wirtschaftskalender()
    if not events:
        return
        
    jetzt = datetime.now()

    for event in events:
        if event.get('impact') == "High" and event.get('time') and ":" in event.get('time'):
            try:
                # Kombiniere das heutige Datum mit der Event-Zeit
                stunde, minute = map(int, event['time'].split(':'))
                event_zeit = jetzt.replace(hour=stunde, minute=minute, second=0, microsecond=0)
                
                # Berechne die Zeitdifferenz
                zeit_bis_event = event_zeit - jetzt
                
                # Prüfe, ob das Event in 14-15 Minuten stattfindet
                if timedelta(minutes=14) < zeit_bis_event <= timedelta(minutes=15):
                    alarm_id = f"{event_zeit.strftime('%H:%M')}-{event.get('event')}"
                    if alarm_id not in gesendete_alarme:
                        embed = discord.Embed(
                            title="🚨 WICHTIGES EREIGNIS IN 15 MINUTEN 🚨",
                            description=f"**Ereignis:** {event.get('event')}\n**Währung:** {event.get('currency')}",
                            color=discord.Color.red()
                        )
                        await channel.send(embed=embed)
                        gesendete_alarme.add(alarm_id)
                        print(f"Alarm für '{event.get('event')}' gesendet.")
            except (ValueError, IndexError):
                # Ignoriere Events mit ungültigem Zeitformat
                continue


# --- Discord Event Handler und Bot Start (bleibt unverändert) ---

@client.event
async def on_ready():
    """Wird ausgeführt, wenn der Bot erfolgreich mit Discord verbunden ist."""
    print(f'{client.user} ist jetzt online!')
    
    scheduler = AsyncIOScheduler(timezone="Europe/Berlin")
    scheduler.add_job(sende_tagesuebersicht, CronTrigger(hour=8, minute=0))
    scheduler.add_job(pruefe_und_sende_alarme, 'interval', minutes=1)
    scheduler.start()

client.run(DISCORD_TOKEN)
