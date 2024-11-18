import discord
from discord.ext import commands, tasks
from datetime import datetime
import mysql.connector

# Bot setup
intents = discord.Intents.default()
intents.messages = True
intents.message_content = True  # Required for reading message content
intents.dm_messages = True      # Required for DM functionality
bot = commands.Bot(command_prefix="!", intents=intents)

# Configuration
CACHE_FILE = "word_list_cache.json"
MONITOR_CHANNEL_ID = 123456  # Channel to monitor for valid words
LIST_CHANNEL_ID = 123456   # Channel to post the word list
NOTIFY_CHANNEL_ID = 123456  # Channel to notify role of new posts
NOTIFY_ROLE_ID = 123456    # Role ID to notify in the notification channel

# Authorized users for manual code addition
AUTHORIZED_USER_IDS = [123456]  # Replace with actual Discord user IDs

# Database connection function
def get_db_connection():
    return mysql.connector.connect(
        host="localhost",
        user="jarvis",
        password="pass",
        database="cache_db",
        port=3306,
        charset='utf8mb4',
        collation='utf8mb4_unicode_ci'
    )

# Load active codes from the database
def load_active_codes():
    conn = get_db_connection()
    cursor = conn.cursor()
    # Modify the query to sort by the `time` column in ascending order
    cursor.execute("""
        SELECT id, message_id, word, user, time
        FROM word_list
        WHERE active = TRUE
        ORDER BY time ASC
    """)
    active_codes = cursor.fetchall()
    cursor.close()
    conn.close()
    return active_codes

# Insert a new code into the database
def insert_code_to_db(message_id, word, user, timestamp):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO word_list (message_id, word, user, time, active)
            VALUES (%s, %s, %s, %s, %s)
        """, (message_id, word, user, timestamp, True))
        conn.commit()
    except Exception as e:
        raise e
    finally:
        cursor.close()
        conn.close()

# Mark a code as inactive (and set removed_at timestamp)
def mark_code_inactive(message_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            UPDATE word_list
            SET active = FALSE, removed_at = NOW()
            WHERE message_id = %s
        """, (message_id,))
        conn.commit()
    except Exception as e:
        raise e
    finally:
        cursor.close()
        conn.close()

def check_existing_code(word):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT active, removed_at
            FROM word_list
            WHERE word = %s
        """, (word,))
        result = cursor.fetchone()  # Fetch the first result
        cursor.fetchall()  # Clear any unread results
        return result
    finally:
        cursor.close()
        conn.close()

# Update list channel
async def update_list_channel():
    """Update the word list in the specified list channel."""
    list_channel = bot.get_channel(LIST_CHANNEL_ID)
    if not list_channel:
        print("List channel not found")
        return

    # Fetch active words from the database
    active_codes = load_active_codes()

    # Format the list
    messages = []
    message_content = ""
    for row in active_codes:
        _, message_id, word, user, timestamp = row
        word_entry = f"```{word}``` by {user} at {timestamp}\n"
        if len(message_content + word_entry) > 1900:
            messages.append(message_content)
            message_content = word_entry
        else:
            message_content += word_entry
    if message_content:
        messages.append(message_content)

    # Clear previous messages
    async for msg in list_channel.history(limit=500):
        await msg.delete()

    # Send updated list
    for i, content in enumerate(messages):
        await list_channel.send(f"**Passcode List - Part {i + 1}:**\n{content}")

# Event: Bot is ready
@bot.event
async def on_ready():
    print(f"{bot.user} is now online!")
    await update_list_channel()
    check_deleted_messages.start()

# Event: Add valid word messages from the monitored channel
@bot.event
async def on_message(message):
    if message.author.bot:
        return

    if message.channel.id == MONITOR_CHANNEL_ID:
        word = message.content.upper()

        if word.isalnum() and 5 <= len(word) <= 30:
            existing_code = check_existing_code(word)

            if existing_code:
                is_active, removed_at = existing_code
                if is_active:
                    await message.delete()
                    await message.author.send(f"The code `{word}` is already active.")
                else:
                    await message.delete()
                    inactive_date = removed_at.strftime("%Y-%m-%d %H:%M:%S") if removed_at else "unknown date"
                    await message.author.send(
                        f"The code `{word}` is inactive. It was deactivated on {inactive_date}."
                    )
                return

            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            insert_code_to_db(message.id, word, str(message.author), timestamp)

            # Add custom emoji to the original message
            custom_emoji = ":verified:561729566196891650"  # Replace with your custom emoji if you want to use one
            await message.add_reaction(custom_emoji)  # Add emoji to the original message

            # Notify in the notify channel
            notify_channel = bot.get_channel(NOTIFY_CHANNEL_ID)
            if notify_channel:
                notify_role = notify_channel.guild.get_role(NOTIFY_ROLE_ID)
            await notify_channel.send(f"{notify_role.mention} **New Passcode Added By:** {message.author.mention}")

            await notify_channel.send(f"```{word}```")

            await update_list_channel()

    await bot.process_commands(message)

# Command: Add passcode manually
@bot.command(name="add_code")
async def add_code(ctx, passcode: str, message_id: str):
    if not isinstance(ctx.channel, discord.DMChannel):
        return

    if ctx.author.id not in AUTHORIZED_USER_IDS:
        await ctx.send("You are not authorized to use this command.")
        return

    passcode = passcode.upper()
    existing_code = check_existing_code(passcode)

    if existing_code:
        is_active, removed_at = existing_code
        if is_active:
            await ctx.send(f"The passcode `{passcode}` is already active.")
        else:
            inactive_date = removed_at.strftime("%Y-%m-%d %H:%M:%S") if removed_at else "unknown date"
            await ctx.send(f"The passcode `{passcode}` is inactive. It was deactivated on {inactive_date}.")
        return

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    insert_code_to_db(message_id, passcode, ctx.author.name, timestamp)
    await ctx.send(f"Passcode `{passcode}` associated with Message ID `{message_id}` added successfully!")

# Task: Periodically check for deleted messages
@tasks.loop(seconds=5)
async def check_deleted_messages():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, message_id FROM word_list WHERE active = TRUE")
    active_ids = cursor.fetchall()
    cursor.close()
    conn.close()

    deleted_ids = []
    for _, message_id in active_ids:
        try:
            channel = bot.get_channel(MONITOR_CHANNEL_ID)
            await channel.fetch_message(message_id)
        except discord.NotFound:
            deleted_ids.append(message_id)

    for message_id in deleted_ids:
        mark_code_inactive(message_id)
    if deleted_ids:
        await update_list_channel()

# Run the bot
bot.run("YOUR_TOKEN")
