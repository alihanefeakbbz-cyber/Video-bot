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
    'tiktok': r'https?://(?:vm|vt|www)\.tiktok\.com/[\w/-]+',
    'instagram': r'https?://(?:www\.)?instagram\.com/(?:p|reel|tv)/[\w-]+',
    'twitter': r'https?://(?:www\.)?(?:twitter|x)\.com/[\w/]+',
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

Bu bot ile aşağıdaki platformlardan video indirebilirsiniz:

✅ <b>TikTok</b> - Videoları yüksek kalitede indirin
✅ <b>Instagram</b> - Reels ve videoları indirin
✅ <b>X (Twitter)</b> - Videoları indirin

━━━━━━━━━━━━━━━━━━━━━━

📥 <b>Kullanım:</b>
1. Video linkini gönderin
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
• TikTok (vm.tiktok.com, vt.tiktok.com)
• Instagram (instagram.com/p/, reel/)
• X/Twitter (twitter.com, x.com)

<b>Komutlar:</b>
/start - Botu baslat
/help - Bu yardim menusunu göster

<b>Kalite Secenekleri:</b>
📹 Video (Yuksek) - 1080p kalite
📹 Video (Normal) - 720p kalite
📹 Video (Dusuk) - 480p kalite
🔊 Sadece Ses - MP3 formatinda

<b>Not:</b> Ses sadece indirmek için MP3 seceneğini kullanin.
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

    # Show quality menu
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
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        f"📥 <b>{PLATFORM_NAMES.get(platform, platform)}</b> videosu algilandi!\n\n"
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

    try:
        # Get video info
        info_opts = {'quiet': True, 'no_warnings': True, 'extract_flat': False}
        with yt_dlp.YoutubeDL(info_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            if not info:
                raise Exception("Video bilgileri alinamadi")

            title = info.get('title', 'video')[:50] or 'video'
            duration = info.get('duration', 0)

        # Check duration
        if duration and duration > 600:  # 10 minutes
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

        # Configure yt-dlp
        max_height = get_quality_height(quality)
        ydl_opts = {
            'format': f'bestvideo[height<={max_height}][ext=mp4]+bestaudio[ext=m4a]/best[height<={max_height}][ext=mp4]/best',
            'outtmpl': os.path.join(temp_dir, 'video.mp4'),
            'quiet': True,
            'no_warnings': True,
            'merge_output_format': 'mp4',
        }

        # Download
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        # Find file
        video_file = os.path.join(temp_dir, 'video.mp4')
        if not os.path.exists(video_file):
            # Try to find any mp4 file
            for f in os.listdir(temp_dir):
                if f.endswith('.mp4'):
                    video_file = os.path.join(temp_dir, f)
                    break

        if os.path.exists(video_file):
            file_size = os.path.getsize(video_file) / (1024 * 1024)  # MB

            # Check Telegram limit (50MB for documents)
            if file_size > 50:
                await query.edit_message_text(
                    f"⚠️ <b>Dosya çok buyuk!</b>\n\n"
                    f"Boyut: {file_size:.1f} MB\n"
                    "Telegram limiti: 50MB\n\n"
                    "Dusuk kalite secmeyi deneyin.",
                    parse_mode='HTML'
                )
                return

            # Send file
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
        await query.edit_message_text(
            f"❌ <b>Indirme hatasi!</b>\n\n{str(e)}",
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
        # Get info
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

        # Configure audio download
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

        # Download
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        # Find MP3
        audio_file = None
        for f in os.listdir(temp_dir):
            if f.endswith('.mp3'):
                audio_file = os.path.join(temp_dir, f)
                break

        if audio_file and os.path.exists(audio_file):
            file_size = os.path.getsize(audio_file) / (1024 * 1024)

            # Send audio
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

def main():
    """Main entry point"""
    print("=" * 50)
    print("🎬 Video Download Bot Baslatiliyor...")
    print("=" * 50)

    # Create application
    app = Application.builder().token(BOT_TOKEN).build()

    # Add handlers
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_url))
    app.add_handler(CallbackQueryHandler(handle_callback))

    print("✅ Bot hazir!")
    print("📱 Telegram'da botunuzu baslatin...")
    print("=" * 50)

    # Start polling
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()