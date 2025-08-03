# Сделать бота ТГ
# Получение промпта от пользователя фото гардероба:
# - загрузить фото 1 или более
# - посмотреть фото вещей из гардероба
# - ваш стиль итд

import os
import traceback

import telebot
from dotenv import load_dotenv
from telebot import types

from ai_agent.ollama_agent import generate_outfit_with_ollama, analyze_clothing_item
from ai_agent.semantic_search import build_vector_store, search_similar_items, inspect_chroma_db
from database.sqlite_init import add_clothing_item, add_user, get_user_clothes, print_users_and_clothes

load_dotenv()

API_KEY = os.getenv('API_KEY')

bot = telebot.TeleBot(API_KEY, parse_mode=None)  # You can set parse_mode by default. HTML or MARKDOWN

SAVE_DIR = 'received_photos'
os.makedirs(SAVE_DIR, exist_ok=True)

user_states = {}
user_metadata = {}
STATE_SCENARIO_1_PHOTOS = 'scenario_1_photos'
STATE_SCENARIO_2_PROMPT = 'scenario_2_prompt'


def escape_markdown(text):
    escape_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    for char in escape_chars:
        text = text.replace(char, f'\\{char}')
    return text


@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    item1 = types.KeyboardButton("📸 Добавить фото")
    item2 = types.KeyboardButton("👗 Получить образ")

    markup.add(item1, item2)

    bot.send_message(
        message.chat.id,
        "✨ Добро пожаловать в вашего персонального стилиста! ✨\n\n"
        "Я помогу вам создать идеальный образ из вашего гардероба! 👗\n"
        "Выберите, что хотите сделать:\n"
        "📸 *Добавить в гардероб* — загрузите фото одежды, чтобы пополнить вашу коллекцию.\n"
        "👗 *Получить образ от ИИ* — укажите повод, и я подберу стильный образ из ваших вещей!",
        reply_markup=markup
    )


@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    chat_id = message.chat.id
    username = message.from_user.username or "unknown"
    language = message.from_user.language_code or "unknown"

    # Проверка, что пользователь в нужном сценарии
    if user_states.get(chat_id) != STATE_SCENARIO_1_PHOTOS:
        bot.send_message(chat_id, "📌 Пожалуйста, сначала выберите сценарий 1 для загрузки фото.")
        return

    # Получение фото
    file_info = bot.get_file(message.photo[-1].file_id)
    downloaded_file = bot.download_file(file_info.file_path)

    # Создание пользовательской папки
    user_folder = os.path.join(SAVE_DIR, str(chat_id))
    os.makedirs(user_folder, exist_ok=True)

    # Имя и путь к файлу
    filename = file_info.file_path.split('/')[-1]
    file_path = os.path.join(user_folder, filename)

    # Сохраняем файл
    with open(file_path, 'wb') as new_file:
        new_file.write(downloaded_file)

    # Анализ одежды
    try:
        item_metadata = analyze_clothing_item(file_path)
    except Exception as e:
        bot.send_message(chat_id, f"⚠️ Не удалось проанализировать фото: {e}")
        return

    # Сохраняем пользователя и одежду в базу данных
    try:
        add_user(chat_id, username=username, language=language)
        add_clothing_item(
            user_id=chat_id,
            filename=filename,
            description=item_metadata.get("description", ""),
            season=", ".join(item_metadata.get("season", [])),
            sex=item_metadata.get("sex", ""),
            image_path=file_path
        )
        build_vector_store(chat_id)

        bot.send_message(chat_id, f"✅ Фото '{filename}' добавлено, проанализировано и сохранено.")
    except Exception as db_err:
        bot.send_message(chat_id, f"❌ Ошибка при сохранении в БД: {db_err}")

    inspect_chroma_db()
    print_users_and_clothes()


@bot.message_handler(func=lambda message: True)
def handle_user_input(message):
    chat_id = message.chat.id
    state = user_states.get(chat_id)

    # === Обработка меню выбора ===
    if message.text == "📸 Добавить фото":
        user_states[chat_id] = STATE_SCENARIO_1_PHOTOS
        bot.send_message(chat_id, "📥 Пожалуйста, отправьте одно или несколько фото вашей одежды.")
        return
    elif message.text == "👗 Получить образ":
        user_states[chat_id] = STATE_SCENARIO_2_PROMPT
        bot.send_message(chat_id, "📝 На какое мероприятие вы собираетесь? Опишите кратко.")
        return

    elif (state is None and not message.text.startswith('/') and message.content_type == 'text'):
        bot.send_message(chat_id, "❗️ Пожалуйста, выберите один из предложенных сценариев.")

    # === Сценарий 1: Фото одежды ===
    if state == STATE_SCENARIO_1_PHOTOS:
        if message.content_type != 'photo':
            bot.send_message(chat_id, "📸 Пожалуйста, отправьте фото одежды.")
        return

    # === Сценарий 2: Генерация образа ===
    elif state == STATE_SCENARIO_2_PROMPT:
        print(user_metadata)
        prompt = message.text.strip()
        user_folder = os.path.join(SAVE_DIR, str(chat_id))

        if not os.path.exists(user_folder):
            bot.send_message(chat_id, "❌ У вас пока нет добавленных вещей. Сначала воспользуйтесь Сценарием 1.")
            return

        files = [f for f in os.listdir(user_folder) if f.endswith(('.png', '.jpg', '.jpeg'))]
        if len(files) < 2:
            bot.send_message(chat_id, f"❌ Недостаточно вещей в гардеробе (найдено: {len(files)}). Нужно минимум 2.")
            return

        bot.send_message(chat_id, "🧠 Генерирую персональный образ...")

        try:

            # 📌 Сначала — семантический поиск подходящих вещей
            try:
                similar_items = search_similar_items(chat_id, prompt, top_k=5)
                selected_filenames = [item["filename"] for item in similar_items]
            except Exception as e:
                bot.send_message(chat_id, f"❌ Ошибка в поиске похожих вещей: {e}")
                return

            if not selected_filenames:
                bot.send_message(chat_id, "😕 Не удалось найти подходящие вещи по запросу.")
                return

            # Получаем всю одежду из БД
            all_clothes = get_user_clothes(chat_id)

            # Формируем словарь метаданных
            clothing_dict = {
                row[0]: {  # row[0] — filename
                    "description": row[1],
                    "season": row[2].split(", ") if row[2] else [],
                    "sex": row[3],
                    "image_path": row[4]
                }
                for row in all_clothes
            }

            filtered_metadata = {
                fname: clothing_dict[fname]
                for fname in selected_filenames if fname in clothing_dict
            }

            # Генерация через Ollama уже по отобранным вещам
            result = generate_outfit_with_ollama(prompt, selected_filenames, filtered_metadata)

            if not result:
                bot.send_message(chat_id, "❌ Ошибка при генерации образа.")
                return

            # Парсинг ответа
            split_sections = result.split('---')
            outfit_block = split_sections[1].strip()
            advice_block = split_sections[2].strip()

            # Обработка блока с вещами
            if "❌" in outfit_block:
                bot.send_message(chat_id, "😕 К сожалению, ни одна из вещей не подходит под выбранное мероприятие.")
            else:
                selected_files = []
                for line in outfit_block.splitlines():
                    line = line.strip()
                    if line.startswith("- ") and line[2:]:
                        selected_files.append(line[2:])

                # Отправка фото подходящих вещей
                for filename in selected_files:
                    file_path = os.path.join(user_folder, filename)
                    if os.path.exists(file_path):
                        with open(file_path, "rb") as photo:
                            bot.send_photo(chat_id, photo)

            # Отправка советов
            bot.send_message(chat_id, f"🎯 *Рекомендации от стилиста:*\n\n{advice_block}", parse_mode=None)

        except Exception as e:
            print(f"[Ollama error] {e}")
            traceback.print_exc()
            bot.send_message(chat_id, "❌ Произошла ошибка при генерации образа.")

        # Очистка состояния
        user_states.pop(chat_id, None)
        return


bot.infinity_polling()
