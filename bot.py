import discord
from discord import app_commands
from gtts import gTTS
import os
import asyncio
import logging
from collections import deque
import time  # Import time for timing purposes
import requests  # Make sure to import requests for API calls
import re  # Import regex for URL detection
import random  # Import random to select random jokes

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.voice_states = True

bot = discord.Client(intents=intents)
tree = app_commands.CommandTree(bot)

opt_out_file = "opted_out_users.txt"

def load_opted_out_users():
    """Load opted-out user IDs from a text file."""
    if os.path.exists(opt_out_file):
        with open(opt_out_file, "r") as f:
            return {line.strip() for line in f}
    return set()

opted_out_users = load_opted_out_users()

# Variable to store the channel the bot should read from
current_text_channel = None
message_queue = deque()  # Queue for incoming messages
is_speaking = False  # Flag to indicate if the bot is currently speaking
last_speaker = None  # Variable to track the last speaker
last_speak_time = 0  # Timestamp of the last message spoken
url_pattern = re.compile(r'(https?://[^\s]+)')
guild_language_settings = {}

# List of dark humor jokes
dark_humor_jokes = [
    "I told my wife she was drawing her eyebrows too high. She looked surprised.",
    "Why don't skeletons fight each other? They don’t have the guts.",
    "I have a joke about death, but it's too grave for you.",
    "Why did the scarecrow win an award? Because he was outstanding in his field, but he never saw the truck coming."
]

@bot.event
async def on_ready():
    logger.info(f"{bot.user} has connected to Discord and is ready!")  
    await tree.sync()

@tree.command(name="join", description="Join a voice channel")
async def join(ctx: discord.Interaction):
    global current_text_channel

    if ctx.user.voice:
        channel = ctx.user.voice.channel
        try:
            await channel.connect()
            current_text_channel = ctx.channel
            await ctx.response.send_message(f"Joined {channel.name}")
            logger.info(f"Bot joined the voice channel: {channel.name}")

            bot.loop.create_task(check_for_inactivity(ctx.guild))
        except discord.DiscordException as e:
            await ctx.response.send_message(f"Failed to join the voice channel: {e}")
            logger.error(f"Error joining voice channel: {e}") 
    else:
        await ctx.response.send_message("You need to be in a voice channel for me to join!")

@tree.command(name="leave", description="Leave the voice channel")
async def leave(ctx: discord.Interaction):
    global current_text_channel
    if ctx.guild.voice_client:
        try:
            await ctx.guild.voice_client.disconnect()
            current_text_channel = None
            await ctx.response.send_message("Left the voice channel.")
            logger.info("Bot left the voice channel.") 
        except discord.DiscordException as e:
            await ctx.response.send_message(f"Failed to leave the voice channel: {e}")
            logger.error(f"Error leaving voice channel: {e}") 
    else:
        await ctx.response.send_message("I'm not in a voice channel!")

# Command to stop and clear the TTS queue
@tree.command(name="stop", description="Stop speaking and clear the queue")
async def stop(ctx: discord.Interaction):
    global message_queue, is_speaking
    voice_client = ctx.guild.voice_client
    if voice_client and voice_client.is_connected():
        voice_client.stop()  # Stop any currently playing audio
        message_queue.clear()  # Clear the queue
        is_speaking = False  # Reset speaking state
        await ctx.response.send_message("Stopped speaking and cleared the queue.")
        logger.info("Cleared the TTS queue and stopped speaking.")
    else:
        await ctx.response.send_message("I'm not currently speaking!")   

paused_users = {}

@tree.command(name="pause", description="Pause TTS for your next message only.")
async def pause(ctx: discord.Interaction):
    user_id = str(ctx.user.id)
    paused_users[user_id] = True  # Mark the user as paused for one message
    await ctx.response.send_message("Your next message will not be read by the bot.")
    logger.info(f"User {ctx.user.display_name} paused TTS for the next message.")

@tree.command(name="optin", description="Opt-in to receive TTS messages")
async def optin(ctx: discord.Interaction):
    user_id = str(ctx.user.id)
    if user_id in opted_out_users:
        opted_out_users.remove(user_id)
        with open(opt_out_file, "w") as f:
            f.writelines(f"{user}\n" for user in opted_out_users)
        await ctx.response.send_message("You have opted in to receive messages.")
        logger.info(f"User {ctx.user.display_name} opted in for TTS messages.") 
    else:
        await ctx.response.send_message("You are already opted in.")

@tree.command(name="optout", description="Opt-out from receiving TTS messages")
async def optout(ctx: discord.Interaction):
    user_id = str(ctx.user.id)
    if user_id not in opted_out_users:
        opted_out_users.add(user_id)
        with open(opt_out_file, "w") as f:
            f.writelines(f"{user}\n" for user in opted_out_users)
        await ctx.response.send_message("You have opted out of receiving messages.")
        logger.info(f"User {ctx.user.display_name} opted out of TTS messages.") 
    else:
        await ctx.response.send_message("You are already opted out.")

# Command to tell a dad joke
@tree.command(name="joke", description="Tell a random dad joke")
async def joke(ctx: discord.Interaction):
    # Fetch a dad joke from an API
    joke_text = await fetch_dad_joke()
    voice_client = ctx.guild.voice_client
    if voice_client and voice_client.is_connected():
        await speak(voice_client, joke_text, "")
    else:
        await ctx.response.send_message("I'm not connected to a voice channel to tell the joke!")

@tree.command(name="chinese", description="Toggle between English and Chinese for TTS")
async def chinese(ctx: discord.Interaction):
    guild_id = ctx.guild.id
    current_language = guild_language_settings.get(guild_id, 'en')  # Default is English ('en')
    
    # Toggle between English ('en') and Chinese ('zh')
    if current_language == 'en':
        guild_language_settings[guild_id] = 'ja'
        await ctx.response.send_message("Language switched to Chinese for this session.")
        logger.info(f"Language set to Chinese for guild {guild_id}.")
    else:
        guild_language_settings[guild_id] = 'en'
        await ctx.response.send_message("Language switched to English for this session.")
        logger.info(f"Language set to English for guild {guild_id}.")

# Command to tell a dark humor joke
@tree.command(name="djoke", description="Tell a dark humor joke")
async def joke(ctx: discord.Interaction):
    # Select a random dark humor joke
    joke_text = random.choice(dark_humor_jokes)
    voice_client = ctx.guild.voice_client
    if voice_client and voice_client.is_connected():
        await speak(voice_client, joke_text, "Dark Humor Bot")
    else:
        await ctx.response.send_message("I'm not connected to a voice channel to tell the joke!")


# Fetch a random dad joke from icanhazdadjoke API
async def fetch_dad_joke():
    try:
        headers = {
            "Accept": "application/json",  # Ensure the API responds with JSON
            "User-Agent": "DiscordDadJokeBot (https://github.com/yourusername)"
        }
        response = requests.get("https://icanhazdadjoke.com/", headers=headers)
        joke_data = response.json()
        return joke_data['joke']
    except Exception as e:
        logger.error(f"Failed to fetch dad joke: {e}")
        return "I'm sorry, I couldn't fetch a dad joke right now"

async def speak(voice_client, message: str, author: str):
    global is_speaking, last_speaker, last_speak_time
    logger.info(f"Speaking message from {author}: {message}")

    current_time = time.time()
    if last_speaker == author and current_time - last_speak_time < 10:  
        tts_message = message  
    else:
        tts_message = f"{author} says: {message}"  

    # Get the language setting for the guild
    guild_id = voice_client.guild.id
    current_language = guild_language_settings.get(guild_id, 'en')  # Default to English if not set

    # Generate TTS message with the current language
    tts = gTTS(text=tts_message, lang=current_language)
    audio_file = "tts_message.mp3"
    tts.save(audio_file)

    voice_client.play(discord.FFmpegPCMAudio(audio_file), after=lambda e: on_play_finish(e, audio_file))

    is_speaking = True  
    last_speaker = author  
    last_speak_time = current_time  

    while voice_client.is_playing():
        await asyncio.sleep(1)

    await asyncio.sleep(1)  # Adjust time as necessary
    is_speaking = False  


def on_play_finish(e, audio_file):
    if e is not None:
        logger.info(f"Finished playing: {e}")
    else:
        logger.info("Finished playing audio.")

    try:
        os.remove(audio_file)
        logger.info(f"Removed audio file: {audio_file}")
    except PermissionError as pe:
        logger.error(f"PermissionError while deleting file: {pe}")


async def check_for_inactivity(guild):
    voice_client = guild.voice_client
    while voice_client and voice_client.is_connected():
        await asyncio.sleep(300)
        if len(voice_client.channel.members) == 1:
            await voice_client.disconnect()
            logger.info("Bot disconnected due to inactivity.")  
            break

@bot.event
async def on_message(message):
    global current_text_channel
    global is_speaking

    if current_text_channel and message.channel == current_text_channel and not message.author.bot:
        user_id = str(message.author.id)

        # Check if the user has paused TTS for the next message
        if user_id in paused_users:
            paused_users.pop(user_id)  # Remove from paused users since this is a one-time opt-out
            logger.info(f"Skipping TTS for {message.author.display_name}'s message.")
            return  # Skip reading this message

        # Check if the message contains a link
        if re.search(r'(https?://[^\s]+)', message.content):
            logger.info(f"Skipping TTS for message with link from {message.author.display_name}.")
            return  # Skip reading messages containing links

        if user_id not in opted_out_users:
            voice_client = message.guild.voice_client
            if voice_client and voice_client.is_connected():
                member = message.guild.get_member(message.author.id)

                if member:  # Check if member is not None
                    author_name = member.display_name

                    # Handle mentions in the message content
                    content = message.content
                    if message.mentions:
                        for mentioned_member in message.mentions:
                            mention_name = mentioned_member.display_name
                            content = content.replace(f"<@{mentioned_member.id}>", f"@{mention_name}")

                    logger.info(f"Message from {author_name}: {content}")

                    # Check if the bot is currently speaking
                    if not is_speaking:
                        await speak(voice_client, content, author_name)
                    else:
                        message_queue.append((voice_client, content, author_name))

                        while is_speaking:
                            await asyncio.sleep(1)

                        if message_queue:
                            next_voice_client, next_content, next_author_name = message_queue.popleft()
                            await speak(next_voice_client, next_content, next_author_name)
                else:
                    logger.warning(f"Could not find member for user ID {message.author.id}. Skipping TTS.")
# Run the bot using the token from an environment variable
# bot.run(os.getenv("DISCORD_BOT_TOKEN"))
bot.run("MTI5MTMwNDg3NzM4NDkyOTM2Nw.Ge831E.y0LJ0pKdNxyoZHbpjph7Tamy0ZBRleadOdcfCQ")

