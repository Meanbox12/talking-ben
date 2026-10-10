import os
import json
import asyncio
import secrets
import tempfile

import discord
from discord.ext import commands
from gtts import gTTS

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def load_token():
    try:
        with open(os.path.join(BASE_DIR, "token.json")) as config_file:
            config = json.load(config_file)
            token = config.get("token", "").strip()
            if token == "PASTE_YOUR_BOT_TOKEN_HERE":
                return None
            return token
    except (FileNotFoundError, json.JSONDecodeError):
        return None


TOKEN = load_token() or os.getenv("token") or os.getenv("TOKEN")
if not TOKEN:
    raise ValueError("No token found in token.json or environment variable.")

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="b.", intents=intents)


def sound_path(name: str) -> str:
    return os.path.join(BASE_DIR, "Sounds", name)


SOUNDS = {
    "arrive": sound_path("Arrive.mp3"),
    "leave": sound_path("Leave.mp3"),
    "yes": sound_path("Yes.mp3"),
    "no": sound_path("No.mp3"),
    "hohoho": sound_path("Laugh.mp3"),
    "ugh": sound_path("Ugh.mp3"),
}

RESPONSES = {k: SOUNDS[k] for k in ("yes", "no", "hohoho", "ugh")}

emojis_enabled = False

EMOJIS = {
    "arrive": "1558295514758512670",
    "leave": "1558295597868646521",
    "yes": "1558295539714363422",
    "no": "1558295551760404560",
    "hohoho": "1558295569292726282",
    "ugh": "1558295585554178148",
}

SETTING1 = "Text To Speech"
SETTING2 = "Restrict Joining"
SETTING3 = "Restrict Speaking"

DEFAULT_SETTINGS = {SETTING1: True, SETTING2: False, SETTING3: False}
SETTINGS_FILE = os.path.join(BASE_DIR, "settings.json")

text_to_speech = False
restrict_joining = False
restrict_speaking = False

active = {}

def is_busy(guild: discord.Guild) -> bool:
    """True if Ben is mid-interaction or any audio is playing in this guild."""
    vc = guild.voice_client
    return guild.id in active or bool(vc and vc.is_playing())


def release(guild_id: int, token) -> None:
    """Frees the guild, but only if this token is still the active one."""
    if active.get(guild_id) is token:
        del active[guild_id]

def load_settings():
    settings = dict(DEFAULT_SETTINGS)
    try:
        with open(SETTINGS_FILE, "r") as file:
            data = json.load(file)
            if isinstance(data, dict):
                for key in DEFAULT_SETTINGS:
                    if isinstance(data.get(key), bool):
                        settings[key] = data[key]
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    return settings


def save_settings():
    with open(SETTINGS_FILE, "w") as file:
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
        discord.SelectOption(label=f"Restrict Speaking - {'Enabled' if settings_state[SETTING3] else 'Disabled'}", description="Requires Manage Server permission for b.ask and b.say."),
        discord.SelectOption(label="Close", description="Removes this menu."),
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

            view = SettingsView(self.author)
            await interaction.response.edit_message(view=view)
            await interaction.followup.send(
                f"{setting_name} is now {'Enabled' if settings_state[setting_name] else 'Disabled'}.",
                ephemeral=True,
            )
        elif setting_name == "Close":
            await interaction.response.defer()
            await interaction.message.delete()


@bot.command(name="settings")
@commands.guild_only()
@commands.has_permissions(manage_guild=True)
async def settings(ctx, setting: str = None, value: str = None):
    """Allows server admins to configure bot settings."""
    setting_map = {"tts": SETTING1, "joining": SETTING2, "speaking": SETTING3}

    if setting and value:
        setting_name = setting_map.get(setting.lower())
        if setting_name and value.lower() in ["true", "false"]:
            settings_state[setting_name] = value.lower() == "true"
            save_settings()
            apply_settings()
            state = "Enabled" if settings_state[setting_name] else "Disabled"
            print(f"(!) - {setting_name} is now {state}.")
            await ctx.send(f"{setting_name} is now {state}.", delete_after=3)
            return

    embed = discord.Embed(title="Settings", description="Click a setting in the dropdown to toggle it.", color=discord.Color.blue())
    await ctx.send(embed=embed, view=SettingsView(ctx.author))


@settings.error
async def settings_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("You need the \"Manage Server\" permission to use this command.", delete_after=5)
    elif isinstance(error, commands.NoPrivateMessage):
        await ctx.send("This command only works in a server.")
    else:
        raise error


@bot.event
async def on_ready():
    print(f"(!) - Logged in as {bot.user}")


@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        return
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"Missing argument: `{error.param.name}`. Try `b.commands`.")
        return
    if isinstance(error, commands.NoPrivateMessage):
        await ctx.send("This command only works in a server.")
        return
    if ctx.command and ctx.command.has_error_handler():
        return
    raise error


@bot.command(name="join")
@commands.guild_only()
async def join(ctx, *, channel_name: str = None):
    """Joins a voice channel (by name or ID), or your current channel if none is given."""
    if restrict_joining and not ctx.author.guild_permissions.manage_guild:
        return

    if ctx.guild.voice_client:
        await ctx.send("Ben is already in a voice channel.")
        return

    channel = None
    if channel_name is None:
        if ctx.author.voice and ctx.author.voice.channel:
            channel = ctx.author.voice.channel
    elif channel_name.isdigit():
        found = ctx.guild.get_channel(int(channel_name))
        if isinstance(found, (discord.VoiceChannel, discord.StageChannel)):
            channel = found
    else:
        channel = discord.utils.get(ctx.guild.voice_channels, name=channel_name)

    if not channel:
        await ctx.send("Please provide a valid channel name or ID (or join a voice channel first).")
        return

    voice_client = await channel.connect()
    voice_client.play(discord.FFmpegPCMAudio(SOUNDS["arrive"]))
    await ctx.send(f"{emojis_enabled and f'<a:arrive:{EMOJIS['arrive']} ' or ''}Joined {channel.name}!")
    print(f"(!) - Joined channel: {channel.name}")


@bot.command(name="leave")
@commands.guild_only()
async def leave(ctx):
    """Leaves the voice channel."""
    if restrict_joining and not ctx.author.guild_permissions.manage_guild:
        return

    voice_client = ctx.guild.voice_client
    if voice_client:
        active.pop(ctx.guild.id, None)
        if voice_client.is_playing():
            voice_client.stop()

        voice_client.play(discord.FFmpegPCMAudio(SOUNDS["leave"]))
        while voice_client.is_playing():
            await asyncio.sleep(0.2)
        await voice_client.disconnect()
        await ctx.send(f"<a:leave:{EMOJIS['leave']}> Left the voice channel.")
        print("(!) - Left channel")
    else:
        await ctx.send("I'm not in a voice channel.")


async def respond(response: str, ctx, token):
    """Plays a response clip and keeps the guild busy until it finishes."""
    if response not in RESPONSES:
        release(ctx.guild.id, token)
        return

    try:
        print(f"(!) - Ben says: {response.capitalize()}")
        voice_client = ctx.guild.voice_client

        if voice_client and voice_client.is_connected():
            def after_response(error):
                if error:
                    print(f"Playback error: {error}")
                release(ctx.guild.id, token)

            voice_client.play(
                discord.FFmpegPCMAudio(RESPONSES[response]),
                after=after_response,
            )
        else:
            release(ctx.guild.id, token)

        await ctx.reply(f"{emojis_enabled and f'<a:{response}:{EMOJIS[response]}> ' or ''}Ben says: {response.capitalize()}")
    except Exception:
        release(ctx.guild.id, token)
        raise


def make_tts_file(text: str) -> str:
    """Generates a TTS mp3 and returns its path (blocking; run in a thread)."""
    fd, path = tempfile.mkstemp(suffix=".mp3")
    os.close(fd)
    try:
        gTTS(text, lang="en").save(path)
    except Exception:
        os.remove(path)
        raise
    return path


@bot.command(name="ask")
@commands.guild_only()
async def ask(ctx, *, question: str):
    """Asks Ben a question."""
    if restrict_speaking and not ctx.author.guild_permissions.manage_guild:
        return

    if is_busy(ctx.guild):
        await ctx.message.add_reaction("<a:ugh:1558295585554178148>")
        return

    voice_client = ctx.guild.voice_client
    if not voice_client:
        await ctx.send("I'm not in a voice channel. Use `b.join` first.")
        return

    token = object()
    active[ctx.guild.id] = token

    user_nickname = ctx.author.display_name
    tts_text = f"{user_nickname} asked: {question}"
    response = secrets.choice(list(RESPONSES.keys()))
    print(f"(!) - {user_nickname} asked: {question}")

    try:
        if not text_to_speech:
            await respond(response, ctx, token)
            return

        try:
            tts_filename = await asyncio.to_thread(make_tts_file, tts_text)
        except Exception as e:
            print(f"Error generating TTS: {e}")
            await respond(response, ctx, token)
            return

        voice_client = ctx.guild.voice_client
        if not voice_client or active.get(ctx.guild.id) is not token:
            os.remove(tts_filename)
            release(ctx.guild.id, token)
            return

        def after_tts(error):
            try:
                os.remove(tts_filename)
            except OSError as e:
                print(f"Error deleting TTS file: {e}")
            if error:
                print(f"Playback error: {error}")
                release(ctx.guild.id, token)
                return
            if active.get(ctx.guild.id) is token:
                asyncio.run_coroutine_threadsafe(respond(response, ctx, token), bot.loop)

        voice_client.play(discord.FFmpegPCMAudio(tts_filename), after=after_tts)
    except Exception:
        release(ctx.guild.id, token)
        raise


@bot.command(name="say")
@commands.guild_only()
async def say(ctx, *, sound_name: str):
    """Gives a specific response."""
    if restrict_speaking and not ctx.author.guild_permissions.manage_guild:
        return

    if is_busy(ctx.guild):
        await ctx.message.add_reaction("<a:ugh:1558295585554178148>")
        return

    sound_name = sound_name.lower()
    if sound_name not in RESPONSES:
        await ctx.send(f"Unknown response. Choose one of: {', '.join(RESPONSES)}.")
        return

    token = object()
    active[ctx.guild.id] = token
    print(f"(!) - {ctx.author.display_name} requested sound: {sound_name}")
    await respond(sound_name, ctx, token)


@bot.command(name="commands")
async def commands_list(ctx):
    """Lists all bot commands."""
    command_descriptions = [
        "**b.commands** - Shows this list of commands.",
        "**b.join [channel name/ID]** - Joins the specified voice channel (or yours).",
        "**b.leave** - Leaves the current voice channel.",
        "**b.ask [question]** - Asks Ben a question with audio response.",
        "**b.say [yes/no/hohoho/ugh]** - Makes Ben give a specific response.",
        "**b.settings** - Allows server managers to change bot settings.",
        "**b.ping** - Checks the bot's latency.",
    ]
    await ctx.send("\n".join(command_descriptions))


@bot.command(name="ping")
async def ping(ctx):
    """Checks latency."""
    await ctx.send(f"Pong! Latency is {round(bot.latency * 1000)}ms")


if __name__ == "__main__":
    bot.run(TOKEN)