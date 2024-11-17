import discord
from datetime import datetime
from discord.ext import commands, tasks
import mysql.connector
import asyncio

# Bot setup
intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# Configuration
CACHE_FILE = "word_list_cache.json"
MONITOR_CHANNEL_ID = 1234567891011  # Channel to monitor for valid words
LIST_CHANNEL_ID = 12345678910112  # Channel to post the word list
NOTIFY_CHANNEL_ID = 12345678910113  # Channel to notify role of new posts
NOTIFY_ROLE_ID = 123456789  # Role ID to notify in the notification channel

# Database connection function with custom port support
def get_db_connection():
    return mysql.connector.connect(
        host="localhost",  # Your database host
        user="user",  # Your database username
        password="pass",  # Your database password
        database="cache_db",  # The database to use
        port=3306,  # The custom port, if you're using one
        charset='utf8mb4',  # Ensure the correct charset
        collation='utf8mb4_unicode_ci'  # Use a compatible collation
    )

# Load active codes from the database
def load_active_codes():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT message_id, word, user, time FROM word_list WHERE active = TRUE")
    active_codes = cursor.fetchall()
    cursor.close()
    conn.close()
    return active_codes

# Insert a new code into the database (with active status)
def insert_code_to_db(message_id, word, user, timestamp):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Insert new word with active status as True and no removal time
    cursor.execute("""
        INSERT INTO word_list (message_id, word, user, time, active)
        VALUES (%s, %s, %s, %s, %s)
    """, (message_id, word, user, timestamp, True))
    
    conn.commit()
    cursor.close()
    conn.close()

# Mark a code as inactive (and set removed_at timestamp)
def mark_code_inactive(message_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Update the code to be inactive and set the removal time
    cursor.execute("""
        UPDATE word_list
        SET active = FALSE, removed_at = NOW()
        WHERE message_id = %s
    """, (message_id,))
    
    conn.commit()
    cursor.close()
    conn.close()

# Flag to prevent multiple list updates
updating_list = False

@bot.event
async def on_ready():
    print(f"{bot.user} is now online!")
    await update_list_channel()  # Update the word list on startup
    check_deleted_messages.start()  # Start checking for deleted messages periodically

async def update_list_channel():
    """Update the word list in the specified list channel."""
    global updating_list
    if updating_list:
        return  # Prevent redundant updates

    updating_list = True

    list_channel = bot.get_channel(LIST_CHANNEL_ID)
    if not list_channel:
        print("List channel not found")
        updating_list = False
        return

    # Fetch active words from the database
    active_codes = load_active_codes()

    # Split active codes into 1900-character chunks and send each as a separate message
    message_content = ""
    messages = []

    for row in active_codes:
        message_id, word, user, timestamp = row
        word_entry = f"```{word}``` by {user} at {timestamp}\n"
        if len(message_content + word_entry) > 1900:
            messages.append(message_content)
            message_content = word_entry
        else:
            message_content += word_entry

    if message_content:  # Append the remaining content
        messages.append(message_content)

    # Delete previous messages
    async for msg in list_channel.history(limit=500):
        await msg.delete()

    # Send each chunk as a new message
    for i, content in enumerate(messages):
        await list_channel.send(f"**Passcode List - Part {i + 1}:**\n{content}")

    updating_list = False  # Allow future updates after the current update

@bot.event
async def on_message(message):
    """Add valid word messages to the list and notify in notify channel."""
    if message.author.bot or message.channel.id != MONITOR_CHANNEL_ID:
        return

    # Check if the message is a single word with 5 to 30 alphanumeric characters
    if message.content.isalnum() and 5 <= len(message.content) <= 30:
        word = message.content.upper()
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Insert into the database
        insert_code_to_db(message.id, word, str(message.author), timestamp)

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
    """Mark a word as inactive when the message is deleted."""
    if message.id:
        mark_code_inactive(message.id)  # Mark the code as inactive in the database
        await update_list_channel()  # Only update list if necessary

@tasks.loop(seconds=5)
async def check_deleted_messages():
    """Periodically check for deleted messages from the database."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT message_id FROM word_list WHERE active = TRUE")
    active_ids = cursor.fetchall()
    cursor.close()
    conn.close()

    deleted_ids = []
    for message_id, in active_ids:
        try:
            # Attempt to fetch the message; if it fails, it was deleted
            channel = bot.get_channel(MONITOR_CHANNEL_ID)
            await channel.fetch_message(message_id)
        except discord.NotFound:
            # Mark the message as deleted
            deleted_ids.append(message_id)

    # Remove deleted messages from the database and update list channel
    for message_id in deleted_ids:
        mark_code_inactive(message_id)  # Mark as inactive in the database
    if deleted_ids:
        await update_list_channel()  # Only update if there were deleted messages

# Run the bot with your token
bot.run("YOUR_TOKEN")
