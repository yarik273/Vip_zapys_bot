import os
import telebot
import threading
import json
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer

# ================= НАЛАШТУВАННЯ =================
BOT_TOKEN = os.getenv("PRIVATE_BOT_TOKEN")     # Токен нового бота від BotFather
ALLOWED_ADMIN_ID = 5596041220                  # Ваш особистий Telegram ID
FILE_PATH = "vip_users.json"                   # Локальний файл бази даних в пам'яті бота
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
        players_list = []

    if not isinstance(players_list, list):
        players_list = []

    today = datetime.now().date()
    valid_players = []
    expired_count = 0

    for player in players_list:
        try:
            expire_str = player.get("expire_date", "")
            expire_date = datetime.strptime(expire_str, "%Y-%m-%d").date()
            
            # Якщо термін привілегії діє — залишаємо гравця
            if expire_date >= today:
                days_left = (expire_date - today).days
                player["days_left"] = days_left
                valid_players.append(player)
            else:
                expired_count += 1
        except Exception:
            player["days_left"] = "?"
            valid_players.append(player)

    # Перезаписуємо оновлений чистий файл
    with open(FILE_PATH, "w", encoding="utf-8") as f:
        json.dump(valid_players, f, indent=2, ensure_ascii=False)

    return valid_players, expired_count

# Обробник команди /start
@bot.message_handler(commands=['start'])
def start_cmd(message):
    if message.from_user.id != ALLOWED_ADMIN_ID:
        bot.send_message(message.chat.id, "👋 Вітання! Напишіть команду `/info`, щоб переглянути список активних привілегій на сервері.")
        return
    
    instructions = (
        "👋 **Привіт, Ярославе!**\n\n"
        "Я твій особистий автономний менеджер гравців (без GitHub).\n\n"
        "📝 **Щоб додати гравця, надішли мені текст через кому:**\n"
        "`Нік, SteamID, Привілегія, Кількість днів`\n\n"
        "📌 **Приклад:**\n"
        "`Yarik_Test, STEAM_0:0:11223344, VIP PREMIUM, 30`\n\n"
        "📋 **Команда для перегляду списку (працює для всіх):** `/info`"
    )
    bot.send_message(message.chat.id, instructions, parse_mode="Markdown")

# Обробник текстових повідомлень з даними (ТІЛЬКИ ВІД ВАС)
@bot.message_handler(func=lambda message: message.from_user.id == ALLOWED_ADMIN_ID and message.text and not message.text.startswith('/'))
def handle_player_data(message):
    try:
        # Розбиваємо текст по комі
        parts = [p.strip() for p in message.text.split(",")]
        
        if len(parts) != 4:
            bot.send_message(message.chat.id, "❌ **Помилка формату!**\nНадішліть рівно 4 параметри через кому:\n`Нік, SteamID, Привілегія, Дні`")
            return

        nick, steam_id, priv, days_str = parts
        days = int(days_str)

        # Рахуємо дату закінчення у форматі YYYY-MM-DD
        expire_date = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d")

        # Формуємо новий об'єкт гравця
        new_player_obj = {
            "nickname": nick,
            "steam_id": steam_id,
            "privilege": priv,
            "expire_date": expire_date
        }

        # Зчитуємо поточну базу з пам'яті
        try:
            if os.path.exists(FILE_PATH):
                with open(FILE_PATH, "r", encoding="utf-8") as f:
                    players_list = json.load(f)
            else:
                players_list = []
        except Exception:
            players_list = []

        if not isinstance(players_list, list):
            players_list = []

        # Очищаємо базу від протермінованих
        cleaned_list, expired_removed = clean_expired_players_local(players_list)

        # Додаємо нового гравця
        cleaned_list.append(new_player_obj)

        # Зберігаємо файл назад у пам'ять бота
        with open(FILE_PATH, "w", encoding="utf-8") as f:
            json.dump(cleaned_list, f, indent=2, ensure_ascii=False)

        response = (
            f"✅ **Успішно записано локально!**\n"
            f"👤 Нік: `{nick}`\n"
            f"📅 Дійсно до: *{expire_date}*\n\n"
            f"🧹 Авточистка: вилучено *{expired_removed}* гравців, у яких закінчився термін."
        )
        bot.send_message(message.chat.id, response, parse_mode="Markdown")

    except ValueError:
        bot.send_message(message.chat.id, "❌ **Помилка!** Кількість днів має бути цілим числом.")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Виникла помилка: {e}")

# Допоміжна функція для чистки списку перед додаванням
def clean_expired_players_local(players_list):
    today_str = datetime.now().strftime("%Y-%m-%d")
    valid_players = []
    expired_count = 0
    for player in players_list:
        try:
            if player.get("expire_date", "") >= today_str:
                valid_players.append(player)
            else:
                expired_count += 1
        except Exception:
            valid_players.append(player)
    return valid_players, expired_count

# Обробник команди /info (ВІДКРИТА ДЛЯ ВСІХ ГРАВЦІВ ТА ГІЛОК)
@bot.message_handler(commands=['info'])
def info_cmd(message):
    current_thread_id = message.message_thread_id
    
    # Автоматично чистимо застарілих та беремо свіжий список
    players, _ = process_and_clean_database()
    
    if not players:
        bot.send_message(message.chat.id, "📭 Наразі активних привілегій немає або список ще не заповнено.", message_thread_id=current_thread_id)
        return

    report = "📋 **Актуальний список привілегій на сервері:**\n\n"
    
    for idx, p in enumerate(players, 1):
        nick = p.get("nickname", "Unknown")
        steam = p.get("steam_id", "—")
        priv = p.get("privilege", "VIP")
        days = p.get("days_left", 0)
        
        if days == 0:
            days_text = "останній день"
        elif days < 0:
            days_text = "термін вийшал"
        else:
            days_text = f"залишилось днів: {days}"

        report += f"{idx}. 👤 *{nick}* | `{steam}`\n   👑 [{priv}] —  ⏱️ _{days_text}_\n\n"

    # Якщо звіт задовгий, ділимо повідомлення
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
    print("Бот готовий!")
    bot.remove_webhook()
    bot.polling(none_stop=True, interval=2, timeout=15)
    
