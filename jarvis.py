import discord
import json
import os
import asyncio
from datetime import datetime
from discord.ext import commands, tasks

# Bot setup
intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# Configuration
CACHE_FILE = "word_list_cache.json"
MONITOR_CHANNEL_ID = 123456789  # Channel to monitor for valid words
LIST_CHANNEL_ID = 123456789  # Channel to post the word list
NOTIFY_CHANNEL_ID = 123456789  # Channel to notify role of new posts
NOTIFY_ROLE_ID = 123456789  # Role ID to notify in the notification channel

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

@bot.event
async def on_ready():
    print(f"{bot.user} is now online!")
    load_cache()
    await update_list_channel()
    check_deleted_messages.start()

async def update_list_channel():
    """Update the word list in the specified list channel."""
    list_channel = bot.get_channel(LIST_CHANNEL_ID)
    if not list_channel:
        print("List channel not found")
        return

    # Split word_list into 1900-character chunks and send each as a separate message
    message_content = ""
    messages = []

    for data in word_list.values():
        word_entry = f"```{data['word']}``` by {data['user']} at {data['time']}\n"
        if len(message_content + word_entry) > 1900:
            messages.append(message_content)
            message_content = word_entry
        else:
            message_content += word_entry

    if message_content:  # Append the remaining content
        messages.append(message_content)

    # Delete previous messages and send updated messages
    async for msg in list_channel.history(limit=500):
        await msg.delete()

    for i, content in enumerate(messages):
        await list_channel.send(f"**Passcode List - Part {i + 1}:**\n{content}")

@bot.event
async def on_message(message):
    """Add valid word messages to the list and notify in notify channel."""
    if message.author.bot or message.channel.id != MONITOR_CHANNEL_ID:
        return

    # Check if the message is a single word with 5 to 30 alphanumeric characters
    if message.content.isalnum() and 5 <= len(message.content) <= 30:
        word = message.content.upper()
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        word_list[message.id] = {
            "word": word,
            "time": timestamp,
            "user": str(message.author)
        }
        save_cache()

        # Notify in the notification channel with uppercase word, timestamp, and user mention
        notify_channel = bot.get_channel(NOTIFY_CHANNEL_ID)
        if notify_channel:
            notify_role = notify_channel.guild.get_role(NOTIFY_ROLE_ID)
            await notify_channel.send(
                f"{notify_role.mention}```{word}```**New Passcode** added by {message.author.mention} on {timestamp}"
            )

        # Update the list in the list channel
        await update_list_channel()

@bot.event
async def on_message_delete(message):
    """Remove a word from the list if the message is deleted."""
    if message.id in word_list:
        del word_list[message.id]
        save_cache()
        await update_list_channel()

@tasks.loop(seconds=5)
async def check_deleted_messages():
    """Periodically check for deleted messages from cached IDs."""
    deleted_ids = []
    for message_id in list(word_list.keys()):
        try:
            # Attempt to fetch the message; if it fails, it was deleted
            channel = bot.get_channel(MONITOR_CHANNEL_ID)
            await channel.fetch_message(message_id)
        except discord.NotFound:
            # Mark the message as deleted
            deleted_ids.append(message_id)

    # Remove deleted messages from the word list and update cache and list channel
    for message_id in deleted_ids:
        del word_list[message_id]
    if deleted_ids:
        save_cache()
        await update_list_channel()

# Run the bot with your token
bot.run("YOUR_CODE_HERE")
