import os
import telebot
import threading
import json
import shutil
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer

# ================= НАЛАШТУВАННЯ ЗІ СКРИНШОТА =================
BOT_TOKEN = os.getenv("PRIVATE_BOT_TOKEN")     # Токен нового бота від BotFather
REPO_NAME = "yarik273/cs-vip-control"          # Ваш репозиторій зі скриншота
FILE_PATH = "vip_users.json"                   # Ваш JSON-файл зі скриншота
ALLOWED_ADMIN_ID = 5596041220                  # Ваш особистий Telegram ID
# =============================================================

# Наш надійний зашитий SSH-ключ, який більше не зламається на Render
SSH_PRIVATE_KEY = """-----BEGIN OPENSSH PRIVATE KEY-----
b3BlbnNzaC1rZXktdjEAAAAABG5vbmUAAAAEbm9uZQAAAAAAAAABAAAAMwAAAAtzc2gtZW
QyNTUxOQAAACDpuoPwNoeuNbwuz9qtOTLJBsyG8lPjO+6iHgv9s+usTQAAsKDXF5Cw1xeQ
sAAAAAtzc2gtZWQyNTUxOQAAACDpuoPwNoeuNbwuz9qtOTLJBsyG8lPjO+6iHgv9s+usTQ
AAAECbB0WkHwS258b3/V1zBfsh8uH/G4uMIn232YofI/VbX+m6g/A2h641vC7P2q0pMskG
zIbyU+M77qIeC/2z66xNAAAAC3ZpcC1ib3Qta2V5AQIDBAU=
-----END OPENSSH PRIVATE KEY-----"""

bot = telebot.TeleBot(BOT_TOKEN)

# Функція для чистки застарілих гравців за форматом YYYY-MM-DD
def clean_expired_players(players_list):
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

# Функція для зчитування, чистки та додавання нового гравця через SSH Ключ
def update_json_on_github(new_player_obj):
    home_dir = os.path.expanduser("~")
    ssh_dir = os.path.join(home_dir, ".ssh")
    os.makedirs(ssh_dir, exist_ok=True)
    
    ssh_key_path = os.path.join(ssh_dir, "id_ed25519")
    repo_dir = os.path.join(home_dir, "cs-vip-control-repo")
    
    try:
        # Записуємо ключ безпосередньо зі змінної в коді
        with open(ssh_key_path, "w", encoding="utf-8") as f:
            f.write(SSH_PRIVATE_KEY.strip() + "\n")
        os.chmod(ssh_key_path, 0o600)
        
        # Налаштовуємо систему безпеки Git
        os.environ["GIT_SSH_COMMAND"] = f"ssh -i {ssh_key_path} -o IdentitiesOnly=yes -o StrictHostKeyChecking=no"
        
        if os.path.exists(repo_dir):
            shutil.rmtree(repo_dir)
            
        import subprocess
        clone_res = subprocess.run(
            f"git clone git@github.com:{REPO_NAME}.git {repo_dir}", 
            shell=True, capture_output=True, text=True
        )
        if clone_res.returncode != 0:
            return False, f"Помилка клонування репозиторію:\n{clone_res.stderr}"
        
        full_file_path = os.path.join(repo_dir, FILE_PATH)
        
        try:
            with open(full_file_path, "r", encoding="utf-8") as f:
                players_list = json.load(f)
        except Exception:
            players_list = []
            
        if not isinstance(players_list, list):
            players_list = []

        # КРОК 1: Очищаємо список від тих, у кого закінчився термін
        cleaned_list, expired_count = clean_expired_players(players_list)

        # КРОК 2: Додаємо нового гравця в масив
        cleaned_list.append(new_player_obj)

        # КРОК 3: Перетворюємо у красивий JSON-текст із відступами
        with open(full_file_path, "w", encoding="utf-8") as f:
            json.dump(cleaned_list, f, indent=2, ensure_ascii=False)

        # КРОК 4: Записуємо оновлену базу на GitHub
        commit_cmd = (
            f"cd {repo_dir} && "
            f"git config user.name 'Admin Bot' && "
            f"git config user.email 'bot@render.com' && "
            f"git add {FILE_PATH} && "
            f"git commit -m 'Додано {new_player_obj['nickname']}' && "
            f"git push origin main"
        )
        push_res = subprocess.run(commit_cmd, shell=True, capture_output=True, text=True)
        
        if push_res.returncode != 0:
            return False, f"Помилка відправки змін (git push):\n{push_res.stderr}"
        
        if os.path.exists(ssh_key_path):
            os.remove(ssh_key_path)
        if os.path.exists(repo_dir):
            shutil.rmtree(repo_dir)
            
        return True, expired_count
    except Exception as e:
        return False, f"Системна помилка в коді бота:\n{str(e)}"

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
        parts = [p.strip() for p in message.text.split(",")]
        
        if len(parts) != 4:
            bot.send_message(message.chat.id, "❌ **Помилка формата!**\nНадішліть рівно 4 параметри через кому:\n`Нік, SteamID, Привілегія, Дні`")
            return

        nick, steam_id, priv, days_str = parts
        days = int(days_str)

        expire_date = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d")

        new_player_obj = {
            "nickname": nick,
            "steam_id": steam_id,
            "privilege": priv,
            "expire_date": expire_date
        }

        waiting_msg = bot.send_message(message.chat.id, "⏳ Оновлюю файл vip_users.json на GitHub...")

        success, details = update_json_on_github(new_player_obj)

        if success:
            response = (
                f"✅ **Успішно додано в vip_users.json!**\n"
                f"👤 Нік: `{nick}`\n"
                f"📅 Дійсно до: *{expire_date}*\n\n"
                f"🧹 Авточистка: вилучено *{details}* гравців, у яких закінчився термін."
            )
            bot.edit_message_text(response, message.chat.id, waiting_msg.message_id, parse_mode="Markdown")
        else:
            error_response = (
                f"❌ **Не вдалося зберегти зміни.**\n\n"
                f"⚙️ **Технічні деталі помилки:**\n```text\n{details}\n```"
            )
            bot.edit_message_text(error_response, message.chat.id, waiting_msg.message_id, parse_mode="Markdown")

    except ValueError:
        bot.send_message(message.chat.id, "❌ **Помилка!** Кількість днів має бути цілим числом.")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Виникла помилка: {e}")

# === ВЕБ-СЕРВЕР ДЛЯ RENDER ===
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")
    def do_HEAD(self): self.send_response(200); self.end_headers()
    def do_POST(self): self.send_response(200); self.end_headers(); self.wfile.write(b"OK")
    def log_message(self, format, *args): return

def run_health_server():
    server = HTTPServer(("0.0.0.0", int(os.getenv("PORT", 10000))), HealthCheckHandler)
    server.serve_forever()

if __name__ == "__main__":
    threading.Thread(target=run_health_server, daemon=True).start()
    print("Розумний JSON адмін-бот успішно запущено!")
    bot.remove_webhook()
    bot.polling(none_stop=True, interval=2, timeout=15)
    
