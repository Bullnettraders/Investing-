import discord
import os

intents = discord.Intents.default()
intents.message_content = True

client = discord.Client(intents=intents)

# Keywords aus keywords.txt laden
def load_keywords():
    with open('keywords.txt', 'r', encoding='utf-8') as f:
        return [line.strip().lower() for line in f if line.strip()]

KEYWORDS = load_keywords()

# Channel-ID aus Umgebungsvariable
TARGET_CHANNEL_ID = int(os.getenv("TARGET_CHANNEL_ID"))

@client.event
async def on_ready():
    print(f'Eingeloggt als {client.user}')
    print(f'Geladene Keywords: {KEYWORDS}')

@client.event
async def on_message(message):
    if message.author == client.user:
        return

    if message.channel.id != TARGET_CHANNEL_ID:
        return

    content_lower = message.content.lower()
    if any(word in content_lower for word in KEYWORDS):
        try:
            await message.add_reaction("🤗")
        except discord.HTTPException:
            pass

client.run(os.getenv("DISCORD_TOKEN"))