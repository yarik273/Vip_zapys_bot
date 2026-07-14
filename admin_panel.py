import os
import telebot
import threading
import json
from datetime import datetime, timedelta
from github import Github
from http.server import BaseHTTPRequestHandler, HTTPServer

# ================= НАЛАШТУВАННЯ ЗІ СКРИНШОТА =================
BOT_TOKEN = os.getenv("PRIVATE_BOT_TOKEN")     # Токен нового бота від BotFather
GITHUB_TOKEN = os.getenv("MY_GITHUB_TOKEN")    # Ваш токен GitHub (з правами repo)
REPO_NAME = "yarik273/cs-vip-control"          # Ваш репозиторій зі скриншота
FILE_PATH = "vip_users.json"                   # Ваш JSON-файл зі скриншота
ALLOWED_ADMIN_ID = 123456789                    # СУВОРО ВКАЖІТЬ ВАШ TELEGRAM ID
# =============================================================

bot = telebot.TeleBot(BOT_TOKEN)
g = Github(GITHUB_TOKEN)

# Функція для чистки застарілих гравців за форматом YYYY-MM-DD
def clean_expired_players(players_list):
    today_str = datetime.now().strftime("%Y-%m-%d")
    valid_players = []
    expired_count = 0

    for player in players_list:
        try:
            # Якщо дата закінчення більша або дорівнює сьогоднішній — гравець залишається
            if player.get("expire_date", "") >= today_str:
                valid_players.append(player)
            else:
                expired_count += 1
        except Exception:
            # На випадок некоректних даних залишаємо гравця, щоб нічого не зламати
            valid_players.append(player)

    return valid_players, expired_count

# Функція для зчитування, чистки та додавання нового гравця на GitHub
def update_json_on_github(new_player_obj):
    try:
        repo = g.get_repo(REPO_NAME)
        
        # Читаємо існуючий файл vip_users.json
        try:
            contents = repo.get_contents(FILE_PATH, ref="main")
            players_list = json.loads(contents.decoded_content.decode("utf-8"))
            if not isinstance(players_list, list):
                players_list = []
        except Exception:
            players_list = []

        # КРОК 1: Очищаємо список від тих, у кого закінчився термін
        cleaned_list, expired_count = clean_expired_players(players_list)

        # КРОК 2: Додаємо нового гравця в масив
        cleaned_list.append(new_player_obj)

        # КРОК 3: Перетворюємо у красивий JSON-текст із відступами
        updated_json_text = json.dumps(cleaned_list, indent=2, ensure_ascii=False)

        # КРОК 4: Записуємо оновлену базу поверх старого файлу vip_users.json
        commit_msg = f"Додано {new_player_obj['nickname']}. Видалено застарілих: {expired_count}"
        if 'contents' in locals() and contents:
            repo.update_file(contents.path, commit_msg, updated_json_text, contents.sha, branch="main")
        else:
            repo.create_file(FILE_PATH, "Створення бази JSON", updated_json_text, branch="main")
            
        return True, expired_count
    except Exception as e:
        print(f"Помилка GitHub API: {e}")
        return False, 0

# Обробник команди /start
@bot.message_handler(commands=['start'])
def start_cmd(message):
    if message.from_user.id != ALLOWED_ADMIN_ID:
        return
        
    instructions = (
        "👋 **Привіт, Ярославе!**\n\n"
        "Я твій особистий адмін-бот для редагування файлу `vip_users.json`.\n\n"
        "📝 **Надсилай мені дані нового гравця через кому у такому форматі:**\n"
        "`Нік, SteamID, Привілегія, Кількість днів`\n\n"
        "📌 **Приклад повідомлення:**\n"
        "`SilverevliS, STEAM_2:1:413704831, SPONSOR, 30`\n\n"
        "Я сам вирахую дату, додам його у твій поточний файл, а також автоматично **видалю звідти всіх, у кого закінчився термін привілегії!**"
    )
    bot.send_message(message.chat.id, instructions, parse_mode="Markdown")

# Обробник повідомлень з даними (тільки від вас)
@bot.message_handler(func=lambda message: message.from_user.id == ALLOWED_ADMIN_ID and message.text)
def handle_player_data(message):
    try:
        # Розділяємо отриманий текст по комі
        parts = [p.strip() for p in message.text.split(",")]
        
        if len(parts) != 4:
            bot.send_message(message.chat.id, "❌ **Помилка формату!**\nНадішліть рівно 4 параметри через кому:\n`Нік, SteamID, Привілегія, Дні`")
            return

        nick, steam_id, priv, days_str = parts
        days = int(days_str)

        # Розраховуємо дату закінчення (сьогодні + N днів) у форматі YYYY-MM-DD
        expire_date = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d")

        # Формуємо об'єкт точно під структуру вашого файлу vip_users.json
        new_player_obj = {
            "nickname": nick,
            "steam_id": steam_id,
            "privilege": priv,
            "expire_date": expire_date
        }

        waiting_msg = bot.send_message(message.chat.id, "⏳ Оновлюю файл vip_users.json на GitHub...")

        # Запускаємо процес оновлення
        success, expired_removed = update_json_on_github(new_player_obj)

        if success:
            response = (
                f"✅ **Успішно додано в vip_users.json!**\n"
                f"👤 Нік: `{nick}`\n"
                f"📅 Дійсно до: *{expire_date}*\n\n"
                f"🧹 Авточистка: вилучено *{expired_removed}* гравців, у яких закінчився термін."
            )
            bot.edit_message_text(response, message.chat.id, waiting_msg.message_id, parse_mode="Markdown")
        else:
            bot.edit_message_text("❌ Не вдалося зберегти зміни. Перевірте токени або налаштування.", message.chat.id, waiting_msg.message_id)

    except ValueError:
        bot.send_message(message.chat.id, "❌ **Помилка!** Кількість днів має бути цілим числом.")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Виникла помилка: {e}")

# === ВЕБ-СЕРВЕР ДЛЯ RENDER (ЗАХИСТ ВІД ПОМИЛКИ 501 ТА ФОНОВА АВТОЧИСТКА) ===
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")
        # Планова чистка бази при кожному автоматичному запиті від Render
        threading.Thread(target=clean_json_file_silent).start()

    def do_HEAD(self): self.send_response(200); self.end_headers()
    def do_POST(self): self.send_response(200); self.end_headers(); self.wfile.write(b"OK")
    def log_message(self, format, *args): return

def clean_json_file_silent():
    try:
        repo = g.get_repo(REPO_NAME)
        contents = repo.get_contents(FILE_PATH, ref="main")
        players_list = json.loads(contents.decoded_content.decode("utf-8"))
        cleaned_list, expired_count = clean_expired_players(players_list)
        if expired_count > 0:
            updated_json_text = json.dumps(cleaned_list, indent=2, ensure_ascii=False)
            repo.update_file(contents.path, f"Автоматична планова чистка JSON: видалено {expired_count}", updated_json_text, contents.sha, branch="main")
    except Exception: pass

def run_health_server():
    server = HTTPServer(("0.0.0.0", int(os.getenv("PORT", 10000))), HealthCheckHandler)
    server.serve_forever()

if __name__ == "__main__":
    threading.Thread(target=run_health_server, daemon=True).start()
    print("Розумний JSON адмін-бот успішно запущено!")
    bot.remove_webhook()
    bot.polling(none_stop=True, interval=2, timeout=15)
                             
