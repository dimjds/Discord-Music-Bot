import discord
from discord.ext import commands
import yt_dlp as youtube_dl
import os
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from collections import deque
from dotenv import load_dotenv

# Загрузка переменных окружения из .env файла
load_dotenv()

# Получение токенов из переменных окружения
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
SPOTIFY_CLIENT_ID = os.getenv('SPOTIFY_CLIENT_ID')
SPOTIFY_CLIENT_SECRET = os.getenv('SPOTIFY_CLIENT_SECRET')

permissions_int = 8
permissions = discord.Permissions(permissions_int)
intents = discord.Intents.default()
intents.members = True
intents.message_content = True

# Инициализация префикса
bot = commands.Bot(command_prefix='!', intents=intents)

# Оповещение, что бот работает
@bot.event
async def on_ready():
    print('Bot online')

# Настройки Spotify API
sp = spotipy.Spotify(auth_manager=SpotifyClientCredentials(
    client_id=SPOTIFY_CLIENT_ID,
    client_secret=SPOTIFY_CLIENT_SECRET
))

# Очередь песен
song_queue = deque()

# Функция для воспроизведения следующей песни
async def play_next(ctx):
    if len(song_queue) > 0:
        next_song = song_queue.popleft()
        await play_song(ctx, next_song['url'], next_song['title'])
    else:
        voice_client = ctx.voice_client
        if voice_client and voice_client.is_connected():
            await voice_client.disconnect()
            await ctx.send("```Бот отключился от голосового канала.🚶```")

# Вспомогательная функция для воспроизведения песни
async def play_song(ctx, url, title):
    voice_client = ctx.voice_client
    ydl_opts = {
        'format': 'bestaudio',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'quiet': True,
        'no_warnings': True,
        'default_search': 'ytsearch',
    }

    try:
        with youtube_dl.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            if 'entries' in info:
                info = info['entries'][0]
            audio_url = info['url']
        print(f"Playing URL: {audio_url}")  # Лог URL
        voice_client.play(discord.FFmpegPCMAudio(
            executable="ffmpeg",
            source=audio_url,
            before_options="-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
            options="-vn"
        ), after=lambda e: bot.loop.create_task(play_next(ctx)))
        await ctx.send(f'```Играет: {title}```')
    except youtube_dl.utils.DownloadError as e:
        await ctx.send(f"```Ошибка при загрузке аудио: {e}```")
    except KeyError as e:
        await ctx.send(f"```Ключ {e} отсутствует в информации об аудио.```")
        print(f"Исключение: {e}")  # Лог исключения
    except Exception as e:
        await ctx.send(f"```Произошла ошибка: {e}```")
        print(f"Исключение: {e}")  # Лог исключения

# Команда остановки песни
@bot.command(name='stop', help='Остановить воспроизведение и отключиться от голосового канала')
async def stop(ctx):
    voice_client = ctx.message.guild.voice_client
    song_queue.clear()
    if voice_client and voice_client.is_connected():
        await voice_client.disconnect()
        await ctx.send("```Бот отключился от голосового канала.🚶```")
    else:
        await ctx.send("```Бот не был подключен к голосовому каналу.```")

# Команда для добавления песни в очередь и воспроизведения музыки
@bot.command(name='play', help='Воспроизвести песню или добавить в очередь')
async def play(ctx, url: str):
    if not ctx.message.author.voice:
        await ctx.send("```Вы не подключены к голосовому каналу!```")
        return
    channel = ctx.message.author.voice.channel
    if ctx.voice_client is None:
        await channel.connect()
    voice_client = ctx.voice_client

    ydl_opts = {
        'format': 'bestaudio',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'quiet': True,
        'no_warnings': True,
        'default_search': 'ytsearch',
    }

    try:
        if 'spotify.com/playlist' in url:
            results = sp.playlist(url)
            for item in results['tracks']['items']:
                track = item['track']
                track_name = track['name']
                artist_name = track['artists'][0]['name']
                search_query = f"{artist_name} {track_name}"
                song_info = {'url': f"ytsearch:{search_query}", 'title': f"{artist_name} - {track_name}"}
                song_queue.append(song_info)
            await ctx.send("```Плейлист добавлен в очередь.📜```")
        elif 'spotify.com/track' in url:
            results = sp.track(url)
            track_name = results['name']
            artist_name = results['artists'][0]['name']
            search_query = f"{artist_name} {track_name}"
            url = f"ytsearch:{search_query}"

            with youtube_dl.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                if 'entries' in info:
                    info = info['entries'][0]
                title = info['title']

            song_info = {'url': url, 'title': title}
            if not voice_client.is_playing():
                await play_song(ctx, song_info['url'], song_info['title'])
            else:
                song_queue.append(song_info)
                await ctx.send(f"```Добавлено в очередь: {title}```")
        else:
            with youtube_dl.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                if 'entries' in info:
                    info = info['entries'][0]
                title = info['title']

            song_info = {'url': url, 'title': title}
            if not voice_client.is_playing():
                await play_song(ctx, song_info['url'], song_info['title'])
            else:
                song_queue.append(song_info)
                await ctx.send(f"```Добавлено в очередь: {title}```")
    except youtube_dl.utils.DownloadError as e:
        await ctx.send(f"```Ошибка при загрузке аудио: {e}```")
    except KeyError as e:
        await ctx.send(f"```Ключ {e} отсутствует в информации об аудио.```")
        print(f"Исключение: {e}")  # Лог исключения
    except Exception as e:
        await ctx.send(f"```Произошла ошибка: {e}```")
        print(f"Исключение: {e}")  # Лог исключения

# Команда для отображения очереди
@bot.command(name='queue', help='Показать текущую очередь песен')
async def queue(ctx):
    if len(song_queue) == 0:
        await ctx.send("```Очередь пуста!```")
    else:
        queue_list = '\n'.join([song['title'] for song in song_queue])
        await ctx.send(f"```Текущая очередь:\n{queue_list}```")

# Команда для пропуска текущей песни
@bot.command(name='skip', help='Пропустить текущую песню ⏭️')
async def skip(ctx):
    voice_client = ctx.message.guild.voice_client
    if voice_client.is_playing():
        voice_client.stop()
        await ctx.send("```Песня была пропущена.💨```")
    else:
        await ctx.send("```Никакая песня сейчас не играет.🤷```")

bot.run(DISCORD_TOKEN)
