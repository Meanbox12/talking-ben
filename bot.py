import os
import json
import discord
from discord.ext import commands
import secrets
import asyncio
from gtts import gTTS
import tempfile


def load_token():
    try:
        with open("token.json") as config_file:
            config = json.load(config_file)
            token = config.get("token", "").strip()
            if token == "PASTE_YOUR_BOT_TOKEN_HERE":
                return None
            return token
    except FileNotFoundError:
        return None

TOKEN = load_token() or os.getenv("token")
if not TOKEN:
    raise ValueError("No token found in token.json or environment variable.")


intents = discord.Intents.all()
intents.voice_states = True
bot = commands.Bot(command_prefix="b.", intents=intents)

SOUNDS = {
    "arrive": "Sounds/Arrive.mp3",
    "leave": "Sounds/Leave.mp3",
    "yes": "Sounds/Yes.mp3",
    "no": "Sounds/No.mp3",
    "hohoho": "Sounds/Laugh.mp3",
    "ugh": "Sounds/Ugh.mp3"
}

SETTING1 = "Text To Speech"
SETTING2 = "Restrict Joining"
SETTING3 = "Restrict Speaking"

text_to_speech = False
restrict_joining = False
restrict_speaking = False

def load_settings():
    try:
        with open("settings.json", "r") as file:
            return json.load(file)
    except (FileNotFoundError, json.JSONDecodeError):
        return {
            SETTING1: True,
            SETTING2: False,
            SETTING3: False
        }

def save_settings():
    with open("settings.json", "w") as file:
        json.dump(settings_state, file, indent=4)

def apply_settings():
    global text_to_speech, restrict_joining, restrict_speaking
    text_to_speech = settings_state[SETTING1]
    restrict_joining = settings_state[SETTING2]
    restrict_speaking = settings_state[SETTING3]

settings_state = load_settings()
apply_settings()

def get_settings_options():
    return [
        discord.SelectOption(label=f"Text To Speech - {'Enabled' if settings_state[SETTING1] else 'Disabled'}", description="Controls text-to-speech before responses."),
        discord.SelectOption(label=f"Restrict Joining - {'Enabled' if settings_state[SETTING2] else 'Disabled'}", description="Requires Manage Server permission for b.join and b.leave."),
        discord.SelectOption(label=f"Restrict Speaking - {'Enabled' if settings_state[SETTING3] else 'Disabled'}", description="Requires Manage Server permission for b.ask."),
        discord.SelectOption(label="Close", description="Removes this menu.")
    ]

class SettingsView(discord.ui.View):
    def __init__(self, author: discord.Member):
        super().__init__()
        self.author = author
        self.add_item(SettingsDropdown(author))

class SettingsDropdown(discord.ui.Select):
    def __init__(self, author: discord.Member):
        self.author = author
        super().__init__(placeholder="Select a setting...", options=get_settings_options())

    async def callback(self, interaction: discord.Interaction):
        if interaction.user != self.author:
            await interaction.response.send_message("This menu is not for you.", ephemeral=True)
            return

        setting_name = self.values[0].split(" - ")[0]
        if setting_name in settings_state:
            settings_state[setting_name] = not settings_state[setting_name]
            save_settings()
            apply_settings()
            await interaction.response.send_message(f"{setting_name} is now {'Enabled' if settings_state[setting_name] else 'Disabled'}.", ephemeral=True)
            
            self.view.clear_items()
            self.view.add_item(SettingsDropdown(self.author))
            await interaction.message.edit(view=self.view)
        elif setting_name == "Close":
            await interaction.message.delete()

@bot.command(name="settings")
@commands.has_permissions(manage_guild=True)
async def settings(ctx, setting: str = None, value: str = None):
    """Allows server admins to configure bot settings."""
    setting_map = {
        "tts": SETTING1,
        "joining": SETTING2,
        "speaking": SETTING3
    }
    
    if setting and value:
        setting_name = setting_map.get(setting.lower())
        if setting_name and value.lower() in ["true", "false"]:
            settings_state[setting_name] = value.lower() == "true"
            save_settings()
            apply_settings()
            print(f"(!) - {setting_name} is now {'Enabled' if settings_state[setting_name] else 'Disabled'}.")
            msg = await ctx.send(f"{setting_name} is now {'Enabled' if settings_state[setting_name] else 'Disabled'}.")
            await asyncio.sleep(3)
            await msg.delete()
            return
    
    embed = discord.Embed(title="Settings", description="Click a setting in the dropdown to toggle it.", color=discord.Color.blue())
    view = SettingsView(ctx.author)
    await ctx.send(embed=embed, view=view)

@settings.error
async def settings_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("You need the \"Manage Server\" permission to use this command.", ephemeral=True)



SOUNDS = {
    "arrive": "Sounds/Arrive.mp3",
    "leave": "Sounds/Leave.mp3",
    "yes": "Sounds/Yes.mp3",
    "no": "Sounds/No.mp3",
    "hohoho": "Sounds/Laugh.mp3",
    "ugh": "Sounds/Ugh.mp3"
}

RESPONSES = {
    "yes": SOUNDS["yes"],
    "no": SOUNDS["no"],
    "laugh": SOUNDS["hohoho"],
    "ugh": SOUNDS["ugh"]
}

@bot.event
async def on_ready():   
    print(f"(!) - Logged in as {bot.user}")



@bot.command(name="join")
async def join(ctx, *, channel_name: str = None):
    """Joins a voice channel."""
    if restrict_joining and not ctx.author.guild_permissions.manage_guild:
        return
    
    if ctx.guild.voice_client:
        await ctx.send("Ben is already in a voice channel.")
        return

    channel = discord.utils.get(ctx.guild.voice_channels, name=channel_name)
    if channel:
        await channel.connect()
        ctx.guild.voice_client.play(discord.FFmpegPCMAudio(SOUNDS["arrive"]))
        await ctx.send(f"Joined {channel.name}!")
        print(f"(!) - Joined channel: {channel.name}")
    else:
        await ctx.send("Please provide a valid channel name or ID.")

@bot.command(name="leave")
async def leave(ctx):
    """Leaves the voice channel."""
    if restrict_joining and not ctx.author.guild_permissions.manage_guild:
        return
    
    voice_client = ctx.guild.voice_client
    if voice_client:
        if voice_client.is_playing():
            voice_client.stop()

        voice_client.play(discord.FFmpegPCMAudio(SOUNDS["leave"]))
        while voice_client.is_playing():
            await asyncio.sleep(1)
        await voice_client.disconnect()
        await ctx.send("Left the voice channel.")
        print("(!) - Left channel")
    else:
        await ctx.send("I'm not in a voice channel.")

async def respond(response: str, ctx=None):
    """Plays a sound and sends a message for a given response."""
    if response in RESPONSES:
        response_audio_path = RESPONSES[response]
        voice_client = discord.utils.get(bot.voice_clients)
        print(f"(!) - Ben says: {response.capitalize()}")
        if voice_client:
            if voice_client.is_playing():
                voice_client.stop()
            voice_client.play(discord.FFmpegPCMAudio(response_audio_path))
        if ctx:
            await ctx.reply(f"Ben says: {response.capitalize()}")

@bot.command(name="ask")
async def ask(ctx, *, question: str):
    """Asks Ben a question."""
    if restrict_speaking and not ctx.author.guild_permissions.manage_guild:
        return
    
    user_nickname = ctx.author.display_name
    tts_text = f"{user_nickname} asked: {question}"
    response = secrets.choice(list(RESPONSES.keys()))

    voice_client = ctx.guild.voice_client
    if voice_client:
        if voice_client.is_playing():
            voice_client.stop()

        if text_to_speech:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tts_audio:
                gTTS(tts_text, lang="en").save(tts_audio.name)
                tts_filename = tts_audio.name

            async def play_response_after_tts(_):
                try:
                    os.remove(tts_filename)
                except Exception as e:
                    print(f"Error deleting TTS file: {e}")
                await respond(response, ctx)

            await voice_client.play(
                discord.FFmpegPCMAudio(tts_filename),
                after=play_response_after_tts
            )
        else:
            await respond(response, ctx)

    await ctx.reply(f"Ben says: {response.capitalize()}")
    print(f"(!) - {user_nickname} asked: {question}")

@bot.command(name="say")
async def play(ctx, *, sound_name: str):
    """Gives a specific response."""
    if restrict_speaking and not ctx.author.guild_permissions.manage_guild:
        return
    
    sound_name = sound_name.lower()
    if sound_name in RESPONSES:
        print(f"(!) - {ctx.author.display_name} requested sound: {sound_name}")
        await respond(sound_name, ctx)

@bot.command(name="commands")
async def commands_list(ctx):
    """Lists all bot commands."""
    command_descriptions = [
        "**b.commands** - Shows this list of commands.",
        "**b.join [channel name/ID]** - Joins the specified voice channel.",
        "**b.leave** - Leaves the current voice channel.",
        "**b.ask [question]** - Asks Ben a question with audio response.",
        "**b.settings** - Allows server managers to change bot settings.",
        "**b.ping** - Checks the bot's latency."
    ]
    await ctx.send("\n".join(command_descriptions))

@bot.command(name="ping")
async def ping(ctx):
    """Checks latency."""
    latency = round(bot.latency * 1000)
    await ctx.send(f"Pong! Latency is {latency}ms")

bot.run(TOKEN)