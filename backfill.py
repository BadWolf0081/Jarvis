import discord
import json
import os
from datetime import datetime

# Bot setup
intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
client = discord.Client(intents=intents)

# Configuration
CACHE_FILE = "word_list_cache.json"
MONITOR_CHANNEL_ID = 1234565789  # Channel to scan for valid words

# Data storage
word_list = {}

# Load cached words and message IDs on startup
def load_cache():
    global word_list
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r") as file:
            word_list = json.load(file)
    else:
        word_list = {}

# Save current word list to cache
def save_cache():
    with open(CACHE_FILE, "w") as file:
        json.dump(word_list, file)

@client.event
async def on_ready():
    print(f"{client.user} is connected and starting backfill...")

    # Load existing cache
    load_cache()

    # Fetch and process messages in the specified channel
    monitor_channel = client.get_channel(MONITOR_CHANNEL_ID)
    if not monitor_channel:
        print("Monitor channel not found")
        await client.close()
        return

    async for message in monitor_channel.history(limit=500, oldest_first=True):
        # Check if the message is a valid single word with 5 to 30 alphanumeric characters
        if message.content.isalnum() and 5 <= len(message.content) <= 30:
            word = message.content.upper()
            timestamp = message.created_at.strftime("%Y-%m-%d %H:%M:%S")
            # Only add to word_list if it doesn't already exist
            if message.id not in word_list:
                word_list[message.id] = {
                    "word": word,
                    "time": timestamp,
                    "user": str(message.author)
                }

    # Save updated cache
    save_cache()
    print("Backfill complete!")
    await client.close()

# Run the backfill script with your bot token
client.run("YOUR_CODE_HERE")
