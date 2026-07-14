import os
import telebot
import threading
import json
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer

# ================= НАЛАШТУВАННЯ =================
BOT_TOKEN = os.getenv("PRIVATE_BOT_TOKEN")     # Токен нового бота від BotFather
ALLOWED_ADMIN_ID = 5596041220                  # Ваш особистий Telegram ID
FILE_PATH = "vip_users.json"                   # Локальний файл бази даних
# ================================================

bot = telebot.TeleBot(BOT_TOKEN)

# Функція для чистки застарілих гравців та підрахунку залишку днів
def process_and_clean_database():
    if not os.path.exists(FILE_PATH):
        return [], 0
        
    try:
        with open(FILE_PATH, "r", encoding="utf-8") as f:
            players_list = json.load(f)
    except Exception:
        return [], 0

    if not isinstance(players_list, list):
        players_list = []

    today = datetime.now().date()
    valid_players = []
    expired_count = 0

    for player in players_list:
        try:
            expire_str = player.get("expire_date", "")
            expire_date = datetime.strptime(expire_str, "%Y-%m-%d").date()
            
            # Якщо термін не закінчився — залишаємо гравця
            if expire_date >= today:
                # Рахуємо скільки днів залишилося
                days_left = (expire_date - today).days
                player["days_left"] = days_left
                valid_players.append(player)
            else:
                expired_count += 1
        except Exception:
            # На випадок помилки дати залишаємо гравця, щоб не втратити дані
            player["days_left"] = "?"
            valid_players.append(player)

    # Перезаписуємо чистий файл назад у пам'ять бота
    with open(FILE_PATH, "w", encoding="utf-8") as f:
        json.dump(valid_players, f, indent=2, ensure_ascii=False)

    return valid_players, expired_count

# Обробник команди /start (Тільки для вас)
@bot.message_handler(commands=['start'])
def start_cmd(message):
    if message.from_user.id != ALLOWED_ADMIN_ID:
        # Для звичайних користувачів показуємо просту інструкцію
        bot.send_message(message.chat.id, "👋 Вітання! Напишіть команду `/info`, щоб переглянути список активних привілегій на сервері.", parse_mode="Markdown")
        return
    
    welcome_text = (
        "👋 **Привіт, Ярославе!**\n\n"
        "Я твій особистий автономний бот-помічник.\n\n"
        "📂 **Як оновити базу:** Просто надішли мені файл `vip_users.json` як документ у цей чат.\n"
        "📋 **Як подивитися звіт:** Напиши команду `/info` (вона також працює для всіх гравців)."
    )
    bot.send_message(message.chat.id, welcome_text, parse_mode="Markdown")

# Обробник отримання файлу JSON (ТІЛЬКИ ВІД ВАС)
@bot.message_handler(content_types=['document'], func=lambda message: message.from_user.id == ALLOWED_ADMIN_ID)
def handle_document(message):
    if not message.document.file_name.endswith('.json'):
        bot.send_message(message.chat.id, "❌ Помилка! Надішліть саме файл у форматі `.json`")
        return

    waiting = bot.send_message(message.chat.id, "📥 Завантажую та обробляю файл...")
    
    try:
        # Скачуємо файл із серверів Telegram
        file_info = bot.get_file(message.document.file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        
        # Зберігаємо файл локально в пам'ять бота
        with open(FILE_PATH, 'wb') as new_file:
            new_file.write(downloaded_file)
            
        # Запускаємо чистку протермінованих гравців
        valid_list, removed = process_and_clean_database()
        
        response = (
            f"✅ **Файл успішно збережено та активовано!**\n\n"
            f"📊 Загалом активних гравців: `{len(valid_list)}`\n"
            f"🧹 Авточистка: видалено `{removed}` застарілих привілегій, у яких вийшов термін."
        )
        bot.edit_message_text(response, message.chat.id, waiting.message_id, parse_mode="Markdown")
        
    except Exception as e:
        bot.edit_message_text(f"❌ Помилка під час обробки файлу:\n`{str(e)}`", message.chat.id, waiting.message_id, parse_mode="Markdown")

# Обробник команди /info (ВІДКРИТА ДЛЯ ВСІХ ГРАВЦІВ)
@bot.message_handler(commands=['info'])
def info_cmd(message):
    current_thread_id = message.message_thread_id  # Підтримка гілок у супергрупах
    
    # Перед виведенням робимо швидку перевірку дат
    players, _ = process_and_clean_database()
    
    if not players:
        bot.send_message(message.chat.id, "📭 База даних порожня або файл ще не завантажено адміном.", message_thread_id=current_thread_id)
        return

    report = "📋 **Актуальний список привілегій на сервері:**\n\n"
    
    for idx, p in enumerate(players, 1):
        nick = p.get("nickname", "Unknown")
        steam = p.get("steam_id", "—")
        priv = p.get("privilege", "VIP")
        days = p.get("days_left", 0)
        
        # Красиве відображення залишку днів
        if days == 0:
            days_text = "останній день"
        elif days < 0:
            days_text = "термін вийшов"
        else:
            days_text = f"залишилось днів: {days}"

        report += f"{idx}. 👤 *{nick}* | `{steam}`\n   👑 [{priv}] —  ⏱️ _{days_text}_\n\n"

    # Якщо текст задовгий для одного повідомлення Telegram (більше 4000 символів), розіб'ємо його на частини
    if len(report) > 4000:
        for x in range(0, len(report), 4000):
            bot.send_message(message.chat.id, report[x:x+4000], parse_mode="Markdown", message_thread_id=current_thread_id)
    else:
        bot.send_message(message.chat.id, report, parse_mode="Markdown", message_thread_id=current_thread_id)

# === ВЕБ-СЕРВЕР ДЛЯ RENDER ===
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self): self.send_response(200); self.end_headers(); self.wfile.write(b"OK")
    def do_HEAD(self): self.send_response(200); self.end_headers()
    def do_POST(self): self.send_response(200); self.end_headers(); self.wfile.write(b"OK")
    def log_message(self, format, *args): return

if __name__ == "__main__":
    threading.Thread(target=lambda: HTTPServer(("0.0.0.0", int(os.getenv("PORT", 10000))), HealthCheckHandler).serve_forever(), daemon=True).start()
    print("Автономний адмін-блокнот успішно запущено!")
    bot.remove_webhook()
    bot.polling(none_stop=True, interval=2, timeout=15)
    
