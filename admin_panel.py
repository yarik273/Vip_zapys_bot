import os
import json
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

# 2. Ініціалізація бота
BOT_TOKEN = os.environ.get('TOP_BOT_TOKEN')
if not BOT_TOKEN:
    raise ValueError("Токен TOP_BOT_TOKEN не знайдено в змінних оточення!")

bot = telebot.TeleBot(BOT_TOKEN)

# НАЛАШТУВАННЯ ДОРУЧЕНЬ ТА ПРИВ'ЯЗКИ (Точно як у попередньому боті)
ALLOWED_CHAT_USERNAME = "volynskiy_public"  # Юзернейм вашої групи
ALLOWED_THREAD_ID = 764                     # ID дозволеної гілки
MY_PERSONAL_ID = 5596041220                  # Ваш особистим Telegram ID

# 3. Обробка команди /top або /top10
@bot.message_handler(commands=['top', 'top10'])
def send_top_players(message):
    try:
        # СУВОРА ПЕРЕВІРКА ДОСТУПУ: Дозволяємо ЛС з вами АБО конкретну гілку у групі
        is_my_private_chat = (message.chat.type == 'private' and message.chat.id == MY_PERSONAL_ID)
        is_allowed_group_thread = (
            message.chat.username and 
            message.chat.username.lower() == ALLOWED_CHAT_USERNAME.lower() and 
            message.message_thread_id == ALLOWED_THREAD_ID
        )

        # Якщо це не ваше ЛС і не дозволена гілка — бот повністю ігнорує команду і мовчить
        if not (is_my_private_chat or is_allowed_group_thread):
            return  

        # Перевірка наявності файлу з топом
        if not os.path.exists('top_players.json'):
            bot.reply_to(message, "❌ Помилка: Файл `top_players.json` не знайдено!")
            return

        # Зчитуємо актуальні дані з файлу
        with open('top_players.json', 'r', encoding='utf-8') as f:
            players = json.load(f)
        
        # Автоматично сортуємо гравців за вбивствами (kills) від більшого до меншого
    # players.sort(key=lambda x: x.get('kills', 0), reverse=True)

        lines = []
        # Формуємо список топ-10
        for index, player in enumerate(players[:10], start=1):
            if index == 1:
                medal = "🥇"
            elif index == 2:
                medal = "🥈"
            elif index == 3:
                medal = "🥉"
            else:
                medal = f"*{index}.*"

            nickname = player.get('nickname', 'Unknown Player')
            kills = player.get('kills', 0)
            deaths = player.get('deaths', 0)
            hs = player.get('headshots', 0)

            # Гарний рядок для кожного гравця
            player_line = f"{medal} {nickname} — `{kills}` уб. _(💀 {deaths} / 🪖 {hs} в голову)_"
            lines.append(player_line)
        
        if lines:
            response = (
                "🏆 *ТОП-10 НАЙКРАЩИХ ГРАВЦІВ СЕРВЕРА:*\n\n" + 
                "\n".join(lines) + 
                "\n\n📊 Оновлення статистики відбувається раз на 14 днів."
            )
        else:
            response = "Список найкращих гравців порожній."
            
        # Надійний захист від зламу Markdown через символи <, > або _ у нікнеймах гравців
        safe_response = response.replace("_", "\\_").replace("<", "\\<").replace(">", "\\>")
        bot.reply_to(message, safe_response, parse_mode='Markdown')
        
    except json.JSONDecodeError:
        bot.reply_to(message, "❌ Помилка: Неправильний формат тексту у файлі `top_players.json`!")
    except Exception as e:
        bot.reply_to(message, f"❌ Системна помилка: {str(e)}")

if __name__ == "__main__":
    print("Бот ТОП-10 успішно запущений...")
    bot.infinity_polling()
    
