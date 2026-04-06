#!/usr/bin/env python3
"""
Telegram Video Download Bot
Supports: TikTok, Instagram, X (Twitter)
Features: Quality selection, Audio-only download
"""

import sys
import os

# pylibs klasörünü path'e ekle
script_dir = os.path.dirname(os.path.abspath(__file__))
pylibs_dir = os.path.join(script_dir, 'pylibs')
if os.path.exists(pylibs_dir):
    sys.path.insert(0, pylibs_dir)

import logging
import shutil
import tempfile
from datetime import datetime

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)
import yt_dlp

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Bot Token
BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '8540719491:AAGP4T567SB2VoWN42B0rmM-F67v8LsXX3s')

# Platform detection patterns
PATTERNS = {
    'tiktok': r'https?://(?:vm|vt|www|t)\.tiktok\.com/[\w/.-]+',
    'instagram': r'https?://(?:www\.)?instagram\.com/[\w/.-]+',
    'twitter': r'https?://(?:www\.)?(?:twitter|x)\.com/[\w/.-]+',
}

# Platform names for display
PLATFORM_NAMES = {
    'tiktok': 'TikTok',
    'instagram': 'Instagram',
    'twitter': 'X (Twitter)'
}

def detect_platform(url: str) -> str:
    """Detect platform from URL"""
    import re
    for platform, pattern in PATTERNS.items():
        if re.match(pattern, url):
            return platform
    return None

def get_quality_height(quality: str) -> int:
    """Get max height for quality level"""
    heights = {'high': 1080, 'medium': 720, 'low': 480}
    return heights.get(quality, 720)

# Command Handlers
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command"""
    welcome_text = """
🎬 <b>Video İndirme Botuna Hoş Geldiniz!</b>

Bu bot ile aşağıdaki platformlardan içerik indirebilirsiniz:

✅ <b>TikTok</b> - Video ve fotoğraf indirin
✅ <b>Instagram</b> - Video, fotoğraf ve Reels indirin
✅ <b>X (Twitter)</b> - Video ve fotoğraf indirin

━━━━━━━━━━━━━━━━━━━━━━

📥 <b>Kullanım:</b>
1. Video/fotoğraf linkini gönderin
2. Kalite seçin
3. İndirin!

🔊 <b>Ek Özellik:</b>
Sadece ses (MP3) olarak da indirebilirsiniz!

━━━━━━━━━━━━━━━━━━━━━━

Bir link göndererek başlayin! 👇
"""
    await update.message.reply_text(welcome_text, parse_mode='HTML')

async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command"""
    help_text = """
📖 <b>Yardim Menusu</b>

<b>Desteklenen Platformlar:</b>
• TikTok (video ve fotoğraf)
• Instagram (video, fotoğraf ve Reels)
• X/Twitter (video ve fotoğraf)

<b>Komutlar:</b>
/start - Botu baslat
/help - Bu yardim menusunu göster

<b>Indirme Secenekleri:</b>
📹 Video (Yuksek) - 1080p kalite
📹 Video (Normal) - 720p kalite
📹 Video (Dusuk) - 480p kalite
🔊 Sadece Ses - MP3 formatinda
🖼️ Fotoğraf - Instagram ve TikTok

<b>Not:</b> TikTok ve X için video indirin.
"""
    await update.message.reply_text(help_text, parse_mode='HTML')

# Message Handler
async def handle_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle URL messages"""
    url = update.message.text.strip()

    # Validate URL
    if not url.startswith(('http://', 'https://')):
        await update.message.reply_text(
            "❌ <b>Gecersiz Link!</b>\n\n"
            "Lutfen gecerli bir video linki gonderin.\n"
            "Ornek: https://vm.tiktok.com/...",
            parse_mode='HTML'
        )
        return

    # Detect platform
    platform = detect_platform(url)
    if not platform:
        await update.message.reply_text(
            "❌ <b>Desteklenmeyen Platform!</b>\n\n"
            "Bu link desteklenmiyor.\n\n"
            "<b>Desteklenen Platformlar:</b>\n"
            "• TikTok\n• Instagram\n• X (Twitter)",
            parse_mode='HTML'
        )
        return

    # Store URL for callback
    context.user_data['url'] = url
    context.user_data['platform'] = platform

    # Show quality menu based on platform
    keyboard = [
        [
            InlineKeyboardButton("📹 Yuksek (1080p)", callback_data="quality_high"),
            InlineKeyboardButton("📹 Normal (720p)", callback_data="quality_medium"),
        ],
        [
            InlineKeyboardButton("🔊 Sadece Ses (MP3)", callback_data="audio_only"),
        ],
        [
            InlineKeyboardButton("📹 Dusuk (480p)", callback_data="quality_low"),
        ],
    ]

    # Add photo option for all platforms
    keyboard.append([
        InlineKeyboardButton("🖼️ Fotoğraf İndir", callback_data="photo_only"),
    ])

    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        f"📥 <b>{PLATFORM_NAMES.get(platform, platform)}</b> içerigi algilandi!\n\n"
        "🎯 İndirme formatini secin:",
        reply_markup=reply_markup,
        parse_mode='HTML'
    )

# Callback Handler
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle callback queries"""
    query = update.callback_query
    await query.answer()

    url = context.user_data.get('url')
    if not url:
        await query.edit_message_text(
            "❌ <b>Link bulunamadi!</b>\n\n"
            "Lutfen tekrar video linki gonderin.",
            parse_mode='HTML'
        )
        return

    quality = query.data
    chat_id = query.message.chat_id

    try:
        if quality == 'audio_only':
            await download_audio(query, context, url, chat_id)
        elif quality == 'photo_only':
            await download_photo(query, context, url, chat_id)
        elif quality.startswith('quality_'):
            q = quality.replace('quality_', '')
            await download_video(query, context, url, chat_id, q)
    except Exception as e:
        logger.error(f"Download error: {e}")
        await query.edit_message_text(
            f"❌ <b>Hata olustu!</b>\n\n{str(e)}",
            parse_mode='HTML'
        )

async def download_video(query, context, url, chat_id, quality: str):
    """Download video with selected quality"""
    temp_dir = tempfile.mkdtemp()
    platform = detect_platform(url)

    try:
        await query.edit_message_text(
            f"⏳ Video bilgileri aliniyor...\n"
            "Lutfen bekleyin...",
            parse_mode='HTML'
        )

        info_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
            'nocheckcertificate': True,
            'ignoreerrors': False,
            'no_call_home': True,
        }

        if platform == 'instagram':
            info_opts['extractor_args'] = {'instagram': {'cookies': None}}

        with yt_dlp.YoutubeDL(info_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            if not info:
                raise Exception("Video bilgileri alinamadi")

            title = info.get('title', 'video')[:50] or 'video'
            duration = info.get('duration', 0)

        if duration and duration > 600:
            await query.edit_message_text(
                "❌ <b>Video çok uzun!</b>\n\n"
                "Maksimum 10 dakika uzunlugunda video indirebilirsiniz.",
                parse_mode='HTML'
            )
            return

        await query.edit_message_text(
            f"📥 <b>{title}</b>\n\n"
            f"⏳ Indiriliyor... ({quality.upper()})",
            parse_mode='HTML'
        )

        max_height = get_quality_height(quality)
        ydl_opts = {
            'format': f'bestvideo[height<={max_height}][ext=mp4]+bestaudio[ext=m4a]/best[height<={max_height}][ext=mp4]/best',
            'outtmpl': os.path.join(temp_dir, 'video.mp4'),
            'quiet': True,
            'no_warnings': True,
            'merge_output_format': 'mp4',
            'nocheckcertificate': True,
            'no_call_home': True,
            'retries': 3,
            'fragment_retries': 3,
        }

        if platform == 'instagram':
            ydl_opts['extractor_args'] = {'instagram': {'cookies': None}}
            ydl_opts['sleep_interval'] = 1

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        video_file = os.path.join(temp_dir, 'video.mp4')
        if not os.path.exists(video_file):
            for f in os.listdir(temp_dir):
                if f.endswith('.mp4'):
                    video_file = os.path.join(temp_dir, f)
                    break

        if os.path.exists(video_file):
            file_size = os.path.getsize(video_file) / (1024 * 1024)

            if file_size > 50:
                await query.edit_message_text(
                    f"⚠️ <b>Dosya çok buyuk!</b>\n\n"
                    f"Boyut: {file_size:.1f} MB\n"
                    "Telegram limiti: 50MB\n\n"
                    "Dusuk kalite secmeyi deneyin.",
                    parse_mode='HTML'
                )
                return

            with open(video_file, 'rb') as f:
                await context.bot.send_document(
                    chat_id=chat_id,
                    document=f,
                    filename=f"{title}.mp4",
                    caption=f"🎬 <b>{title}</b>\n📊 Kalite: {quality.upper()}\n📁 Boyut: {file_size:.1f} MB",
                    parse_mode='HTML'
                )
            await query.edit_message_text("✅ Video basariyla indirildi!")

        else:
            raise Exception("Video dosyasi bulunamadi")

    except Exception as e:
        error_msg = str(e)
        if 'rate-limit' in error_msg.lower():
            await query.edit_message_text(
                "❌ <b>Rate-Limit Hatasi!</b>\n\n"
                "5-10 dakika bekleyip tekrar deneyin.",
                parse_mode='HTML'
            )
        else:
            await query.edit_message_text(
                f"❌ <b>Indirme hatasi!</b>\n\n{error_msg}",
                parse_mode='HTML'
            )

    finally:
        try:
            shutil.rmtree(temp_dir)
        except:
            pass

async def download_audio(query, context, url, chat_id):
    """Download audio only as MP3"""
    temp_dir = tempfile.mkdtemp()

    try:
        with yt_dlp.YoutubeDL({'quiet': True, 'no_warnings': True}) as ydl:
            info = ydl.extract_info(url, download=False)
            if not info:
                raise Exception("Video bilgileri alinamadi")
            title = info.get('title', 'audio')[:50] or 'audio'

        await query.edit_message_text(
            f"🔊 <b>{title}</b>\n\n"
            "⏳ Ses indiriliyor (MP3)...",
            parse_mode='HTML'
        )

        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': os.path.join(temp_dir, 'audio'),
            'quiet': True,
            'no_warnings': True,
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        audio_file = None
        for f in os.listdir(temp_dir):
            if f.endswith('.mp3'):
                audio_file = os.path.join(temp_dir, f)
                break

        if audio_file and os.path.exists(audio_file):
            file_size = os.path.getsize(audio_file) / (1024 * 1024)

            with open(audio_file, 'rb') as f:
                await context.bot.send_audio(
                    chat_id=chat_id,
                    audio=f,
                    title=title,
                    caption=f"🔊 <b>{title}</b>\n🎵 MP3 | 📁 {file_size:.1f} MB",
                    parse_mode='HTML'
                )
            await query.edit_message_text("✅ Ses basariyla indirildi!")
        else:
            raise Exception("MP3 dosyasi bulunamadi")

    except Exception as e:
        await query.edit_message_text(
            f"❌ <b>Ses indirme hatasi!</b>\n\n{str(e)}",
            parse_mode='HTML'
        )

    finally:
        try:
            shutil.rmtree(temp_dir)
        except:
            pass

async def download_photo(query, context, url, chat_id):
    """Download photo/image only"""
    temp_dir = tempfile.mkdtemp()

    try:
        await query.edit_message_text(
            "🖼️ <b>Fotoğraf(lar) indiriliyor...</b>\n\n"
            "Lutfen bekleyin...",
            parse_mode='HTML'
        )

        # TikTok photo albums come as ZIP
        ydl_opts = {
            'outtmpl': os.path.join(temp_dir, 'photo.%(ext)s'),
            'quiet': True,
            'no_warnings': True,
            'nocheckcertificate': True,
            'no_call_home': True,
            'retries': 3,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        # Check downloaded files
        downloaded_files = []
        for f in os.listdir(temp_dir):
            file_path = os.path.join(temp_dir, f)
            if os.path.isfile(file_path):
                ext = f.lower().split('.')[-1]
                if ext in ('jpg', 'jpeg', 'png', 'webp', 'zip'):
                    downloaded_files.append(file_path)

        image_files = []

        for file_path in downloaded_files:
            if file_path.endswith('.zip'):
                # Extract ZIP (TikTok albums)
                import zipfile
                extract_dir = os.path.join(temp_dir, 'extracted')
                os.makedirs(extract_dir, exist_ok=True)

                with zipfile.ZipFile(file_path, 'r') as zip_ref:
                    zip_ref.extractall(extract_dir)

                for root, dirs, files in os.walk(extract_dir):
                    for f in files:
                        if f.lower().endswith(('.jpg', '.jpeg', '.png', '.webp')):
                            image_files.append(os.path.join(root, f))

            elif file_path.lower().endswith(('.jpg', '.jpeg', '.png', '.webp')):
                image_files.append(file_path)

        if image_files:
            await query.edit_message_text(
                f"📦 <b>{len(image_files)} fotoğraf bulundu!</b>\n\n"
                "⏳ Gönderiliyor...",
                parse_mode='HTML'
            )

            for i, img_file in enumerate(image_files):
                file_size = os.path.getsize(img_file) / (1024 * 1024)
                if file_size > 20:
                    continue

                with open(img_file, 'rb') as f:
                    await context.bot.send_photo(
                        chat_id=chat_id,
                        photo=f,
                        caption=f"🖼️ Fotoğraf {i+1}/{len(image_files)}",
                        parse_mode='HTML'
                    )

            await query.edit_message_text(
                f"✅ <b>{len(image_files)} fotoğraf başarıyla indirildi!</b>",
                parse_mode='HTML'
            )
        else:
            raise Exception("İçerik fotoğraf içermiyor veya desteklenmiyor")

    except Exception as e:
        error_msg = str(e)
        logger.error(f"Photo download error: {error_msg}")

        if 'is a playlist' in error_msg.lower():
            await query.edit_message_text(
                "📦 <b>Birden fazla içerik tespit edildi!</b>\n\n"
                "Video olarak indirmeyi deneyin.",
                parse_mode='HTML'
            )
        else:
            await query.edit_message_text(
                f"❌ <b>Fotoğraf indirme hatası!</b>\n\n{error_msg}",
                parse_mode='HTML'
            )

    finally:
        try:
            shutil.rmtree(temp_dir)
        except:
            pass

def main():
    """Main entry point"""
    print("=" * 50)
    print("🎬 Video Download Bot Baslatiliyor...")
    print("=" * 50)

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_url))
    app.add_handler(CallbackQueryHandler(handle_callback))

    print("✅ Bot hazir!")
    print("📱 Telegram'da botunuzu baslatin...")
    print("=" * 50)

    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
