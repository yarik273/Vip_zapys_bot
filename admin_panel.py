import os
import json
from datetime import datetime
import telebot
import threading
import http.server
import socketserver

# 1. Фейковий веб-сервер для обходу перевірки портів на Render
def run_fake_server():
    port = int(os.environ.get("PORT", 8080))
    handler = http.server.SimpleHTTPRequestHandler
    handler.log_message = lambda *args: None 
    with socketserver.TCPServer(("", port), handler) as httpd:
        httpd.serve_forever()

threading.Thread(target=run_fake_server, daemon=True).start()

# 2. Ініціалізація бота та конфігурація прив'язки
# Використовуємо саме PRIVATE_BOT_TOKEN, як налаштовано у вас на Render
BOT_TOKEN = os.environ.get('PRIVATE_BOT_TOKEN')
if not BOT_TOKEN:
    raise ValueError("Токен PRIVATE_BOT_TOKEN не знайдено в змінних оточення!")

bot = telebot.TeleBot(BOT_TOKEN)

# НАЛАШТУВАННЯ ПРИВ'ЯЗКИ
ALLOWED_CHAT_USERNAME = "volynskiy_public"  # Юзернейм вашої групи
ALLOWED_THREAD_ID = 738                      # ID дозволеної гілки
MY_PERSONAL_ID = 5596041220                  # Ваш особистим Telegram ID

# 3. Обробка команди статусу VIP
@bot.message_handler(commands=['status'])

def send_vip_status(message):
    try:
        # ПЕРЕВІРКА ДОСТУПУ: Дозволяємо ЛС з вами АБО конкретну гілку у групі
        is_my_private_chat = (message.chat.type == 'private' and message.chat.id == MY_PERSONAL_ID)
        is_allowed_group_thread = (
            message.chat.username and 
            message.chat.username.lower() == ALLOWED_CHAT_USERNAME.lower() and 
            message.message_thread_id == ALLOWED_THREAD_ID
        )

        # Якщо це не ваш особистий чат і не дозволена гілка — повністю ігноруємо
        if not (is_my_private_chat or is_allowed_group_thread):
            return  

        # Далі ваш оригінальний код без змін...
        if not os.path.exists('vip_users.json'):
            bot.reply_to(message, "❌ Помилка: Файл `vip_users.json` не знайдено!")
            return

        with open('vip_users.json', 'r', encoding='utf-8') as f:
            users = json.load(f)
        
        today = datetime.now().date()
        lines = []
        
        for user in users:
            expire_date = datetime.strptime(user['expire_date'], "%Y-%m-%d").date()
            days_left = (expire_date - today).days
            formatted_date = expire_date.strftime("%d.%m.%Y")
            
            if days_left > 5:
                status = f"⏳ Дійсна до: {formatted_date} (залишилось {days_left} дн.)"
            elif 0 < days_left <= 5:
                status = f"⚠️ Дійсна до: {formatted_date} (залишилось всього {days_left} дн.!)"
            elif days_left == 0:
                status = f"🚨 ЗАКІНЧУЄТЬСЯ СЬОГОДНІ ({formatted_date})!"
            else:
                status = f"❌ ТЕРМІН ЗАКІНЧИВСЯ ({formatted_date})!"
            
            player_info = (
                f"👤 Нік: {user['nickname']}\n"
                f"🆔 Steam: {user['steam_id']}\n"
                f"👑 Привілея: {user['privilege']}\n"
                f"{status}\n"
                f"────────────────"
            )
            lines.append(player_info)
        
        if lines:
            response = (
                "📊 *СТАТУС VIP ПРИВІЛЕЙ:*\n\n" + 
                "\n".join(lines) + 
                "\n\n👉 Для купівлі або продовження привілей зв'яжіться з адміністрацією. @Marvel_Volynskiy_Public"
            )
        else:
            response = "Список привілей порожній."
            
        safe_response = response.replace("_", "\\_")
        bot.reply_to(message, safe_response, parse_mode='Markdown')
        
    except json.JSONDecodeError:
        bot.reply_to(message, "❌ Помилка: Неправильний формат тексту у файлі `vip_users.json`!")
    except Exception as e:
        bot.reply_to(message, f"❌ Системна помилка: {str(e)}")

# 4. Головний цикл запуску
if __name__ == "__main__":
    print("Бот контролю VIP запущений...")
    bot.infinity_polling()
    
