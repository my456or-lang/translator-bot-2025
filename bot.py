import os
import sys
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import whisper
from googletrans import Translator
import pysrt
import subprocess
from datetime import timedelta

# קריאת TOKEN מ-environment variable
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TEMP_DIR = "temp_files"

# בדיקה שיש TOKEN
if not TELEGRAM_TOKEN:
    print("❌ ERROR: TELEGRAM_TOKEN environment variable not set!")
    print("Please set it in Railway dashboard: Variables → New Variable")
    sys.exit(1)

# יצירת תיקייה זמנית
os.makedirs(TEMP_DIR, exist_ok=True)

# טעינת מודל Whisper
print("=" * 60)
print("🤖 Telegram Video Translator Bot - Starting...")
print("=" * 60)
print("🔄 Loading Whisper AI model (this takes a minute)...")
whisper_model = whisper.load_model("base")
print("✅ Whisper model loaded successfully!")

translator = Translator()

def format_timestamp(seconds):
    """המרת שניות לפורמט SRT"""
    td = timedelta(seconds=seconds)
    hours = td.seconds // 3600
    minutes = (td.seconds % 3600) // 60
    secs = td.seconds % 60
    millis = td.microseconds // 1000
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

def transcribe_audio(audio_path):
    """תמלול אודיו"""
    print("🎤 Transcribing audio...")
    result = whisper_model.transcribe(audio_path, language="en", verbose=False)
    print(f"✅ Transcription complete: {len(result['segments'])} segments")
    return result

def translate_to_hebrew(text):
    """תרגום לעברית"""
    try:
        translation = translator.translate(text, src='en', dest='he')
        return translation.text
    except Exception as e:
        print(f"⚠️ Translation warning: {e}")
        return text

def create_srt(segments, output_path):
    """יצירת קובץ כתוביות SRT"""
    print("📝 Creating Hebrew subtitles...")
    subs = pysrt.SubRipFile()
    
    for i, segment in enumerate(segments, start=1):
        start_time = format_timestamp(segment['start'])
        end_time = format_timestamp(segment['end'])
        text = segment['text'].strip()
        
        # תרגום לעברית
        hebrew_text = translate_to_hebrew(text)
        
        sub = pysrt.SubRipItem(
            index=i,
            start=start_time,
            end=end_time,
            text=hebrew_text
        )
        subs.append(sub)
    
    subs.save(output_path, encoding='utf-8')
    print(f"✅ Subtitles saved: {output_path}")

def extract_audio(video_path, audio_path):
    """חילוץ אודיו מסרטון"""
    print("🔊 Extracting audio from video...")
    cmd = [
        'ffmpeg', '-i', video_path,
        '-vn', '-acodec', 'pcm_s16le',
        '-ar', '16000', '-ac', '1',
        audio_path, '-y',
        '-loglevel', 'error'
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise Exception(f"FFmpeg error: {result.stderr}")
    print("✅ Audio extracted successfully")

def burn_subtitles(video_path, srt_path, output_path):
    """הטמעת כתוביות בסרטון"""
    print("🎬 Burning subtitles into video...")
    
    # נתיב מותאם ל-Linux
    srt_path_escaped = srt_path.replace('\\', '/').replace(':', '\\:')
    
    cmd = [
        'ffmpeg', '-i', video_path,
        '-vf', f"subtitles={srt_path_escaped}:force_style='FontName=Arial,FontSize=24,PrimaryColour=&HFFFFFF,OutlineColour=&H000000,Outline=2,Bold=1'",
        '-c:a', 'copy',
        '-preset', 'fast',
        output_path, '-y',
        '-loglevel', 'error'
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise Exception(f"FFmpeg error: {result.stderr}")
    print("✅ Subtitles burned successfully")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """פקודת התחלה"""
    welcome = """
🎬 **ברוכים הבאים לבוט תרגום הסרטונים!**

אני מתרגם סרטונים מאנגלית לעברית ומוסיף כתוביות.

**📖 איך להשתמש:**
1️⃣ שלח לי סרטון (עד 50MB)
2️⃣ המתן בסבלנות - העיבוד לוקח זמן
3️⃣ קבל את הסרטון עם כתוביות בעברית!

**⚠️ חשוב לדעת:**
• הסרטון חייב להכיל דיבור באנגלית ברורה
• זמן עיבוד: כ-5-10 דקות לסרטון של 5 דקות
• סרטונים קצרים (1-5 דקות) עובדים הכי טוב

**🚀 מוכן? שלח לי סרטון!**

לעזרה נוספת: /help
    """
    await update.message.reply_text(welcome, parse_mode='Markdown')

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """פקודת עזרה"""
    help_text = """
🆘 **מדריך שימוש**

**⏱️ זמני עיבוד משוערים:**
• 1 דקת וידאו = ~2-3 דקות עיבוד
• 3 דקות וידאו = ~5-8 דקות עיבוד
• 5 דקות וידאו = ~10-15 דקות עיבוד

**📹 פורמטים נתמכים:**
MP4, AVI, MOV, MKV - כל פורמט שטלגרם תומך בו

**📏 הגבלות:**
• גודל מקסימלי: 50MB
• אורך מומלץ: עד 10 דקות
• שפת מקור: אנגלית בלבד

**❓ בעיות נפוצות:**
• "לא זוהה דיבור" → בדוק שיש דיבור ברור בסרטון
• "הסרטון גדול מדי" → נסה לדחוס את הסרטון
• "זמן ארוך מדי" → סבלנות, זה לוקח זמן 😊

**💡 טיפים:**
• סרטונים עם דיבור ברור מתורגמים טוב יותר
• רעשי רקע עלולים להשפיע על האיכות
• כתוביות אוטומטיות - ייתכנו טעויות קלות

🎯 שלח סרטון כדי להתחיל!
    """
    await update.message.reply_text(help_text, parse_mode='Markdown')

async def handle_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """טיפול בסרטון שנשלח"""
    user_id = update.message.from_user.id
    username = update.message.from_user.username or "unknown"
    message_id = update.message.message_id
    
    print(f"\n{'='*60}")
    print(f"📹 New video from user @{username} (ID: {user_id})")
    print(f"{'='*60}")
    
    # בדיקת גודל הסרטון
    video_size = update.message.video.file_size
    max_size = 50 * 1024 * 1024  # 50MB
    
    if video_size > max_size:
        await update.message.reply_text(
            f"❌ **הסרטון גדול מדי!**\n\n"
            f"גודל מקסימלי: 50MB\n"
            f"גודל הסרטון שלך: {video_size / (1024*1024):.1f}MB\n\n"
            f"💡 נסה לדחוס את הסרטון או לשלוח סרטון קצר יותר.",
            parse_mode='Markdown'
        )
        return
    
    print(f"✅ Video size OK: {video_size / (1024*1024):.1f}MB")
    
    # הגדרת נתיבי קבצים
    video_path = os.path.join(TEMP_DIR, f"video_{user_id}_{message_id}.mp4")
    audio_path = os.path.join(TEMP_DIR, f"audio_{user_id}_{message_id}.wav")
    srt_path = os.path.join(TEMP_DIR, f"subs_{user_id}_{message_id}.srt")
    output_path = os.path.join(TEMP_DIR, f"output_{user_id}_{message_id}.mp4")
    
    status_msg = None
    
    try:
        # הורדת הסרטון
        status_msg = await update.message.reply_text("📥 **מוריד את הסרטון...**", parse_mode='Markdown')
        
        video = await update.message.video.get_file()
        await video.download_to_drive(video_path)
        print(f"✅ Video downloaded: {video_path}")
        
        await status_msg.edit_text("✅ הסרטון הורד\n🔊 **מחלץ אודיו...**", parse_mode='Markdown')
        
        # חילוץ אודיו
        extract_audio(video_path, audio_path)
        
        await status_msg.edit_text(
            "✅ הסרטון הורד\n✅ אודיו חולץ\n🎤 **מתמלל את הדיבור...**\n\n⏳ _זה לוקח כמה דקות..._",
            parse_mode='Markdown'
        )
        
        # תמלול
        result = transcribe_audio(audio_path)
        
        if not result['segments'] or len(result['segments']) == 0:
            await status_msg.edit_text(
                "❌ **לא זוהה דיבור בסרטון**\n\n"
                "💡 ודא שהסרטון מכיל דיבור באנגלית ברורה.",
                parse_mode='Markdown'
            )
            print("❌ No speech detected in video")
            return
        
        await status_msg.edit_text(
            f"✅ הסרטון הורד\n✅ אודיו חולץ\n✅ תמלול הושלם ({len(result['segments'])} משפטים)\n"
            f"🔄 **מתרגם לעברית...**\n\n⏳ _כמעט גמרנו..._",
            parse_mode='Markdown'
        )
        
        # יצירת כתוביות
        create_srt(result['segments'], srt_path)
        
        await status_msg.edit_text(
            "✅ הסרטון הורד\n✅ אודיו חולץ\n✅ תמלול הושלם\n✅ תרגום הושלם\n"
            "🎬 **מטמיע כתוביות בסרטון...**\n\n⏳ _זה החלק הכי ארוך - המתן בסבלנות..._",
            parse_mode='Markdown'
        )
        
        # הטמעת כתוביות
        burn_subtitles(video_path, srt_path, output_path)
        
        await status_msg.edit_text("✅ **כמעט סיימנו! שולח את הסרטון...**", parse_mode='Markdown')
        
        # שליחת הסרטון המתורגם
        with open(output_path, 'rb') as video_file:
            await update.message.reply_video(
                video=video_file,
                caption="🎉 **הנה הסרטון שלך עם כתוביות בעברית!**\n\n"
                        "😊 נהנת? שלח עוד סרטון!\n"
                        "💬 בעיות? שלח /help",
                parse_mode='Markdown',
                supports_streaming=True
            )
        
        await status_msg.delete()
        print(f"✅ Video processed successfully for user @{username}")
        
    except Exception as e:
        error_message = str(e)
        print(f"❌ Error processing video: {error_message}")
        
        error_text = (
            f"❌ **אירעה שגיאה בעיבוד הסרטון**\n\n"
            f"💡 **מה אפשר לנסות:**\n"
            f"• ודא שהסרטון מכיל דיבור באנגלית\n"
            f"• נסה סרטון קצר יותר\n"
            f"• בדוק שאיכות האודיו טובה\n"
            f"• נסה שוב בעוד כמה דקות\n\n"
            f"🆘 עדיין לא עובד? שלח /help"
        )
        
        if status_msg:
            await status_msg.edit_text(error_text, parse_mode='Markdown')
        else:
            await update.message.reply_text(error_text, parse_mode='Markdown')
    
    finally:
        # ניקוי קבצים זמניים
        print("🧹 Cleaning up temporary files...")
        for file_path in [video_path, audio_path, srt_path, output_path]:
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
                    print(f"  🗑️ Deleted: {file_path}")
            except Exception as e:
                print(f"  ⚠️ Could not delete {file_path}: {e}")

def main():
    """הפעלת הבוט"""
    print("\n" + "=" * 60)
    print("🚀 Starting bot polling...")
    print("=" * 60)
    print(f"✅ Bot is LIVE and waiting for videos!")
    print(f"📱 Users can now send videos to the bot")
    print(f"🛑 Press Ctrl+C to stop")
    print("=" * 60 + "\n")
    
    # יצירת האפליקציה
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # הוספת handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(MessageHandler(filters.VIDEO, handle_video))
    
    # הפעלת הבוט
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n" + "=" * 60)
        print("👋 Bot stopped by user")
        print("=" * 60)
    except Exception as e:
        print(f"\n❌ FATAL ERROR: {e}")
        sys.exit(1)
