import base64
import json
import requests

OLLAMA_URL = 'http://localhost:11434/api/generate'


def generate_outfit_with_ollama(prompt_text: str, items: list, wardrobe_list: dict):

    prompt = (
        "Ты — опытный fashion-стилист. Вот гардероб пользователя:\n"
        f"{wardrobe_list.items()}\n\n"
        f"Пользователь собирается на мероприятие:\n\"{prompt_text}\"\n\n"
        "1. Выбери только те вещи из списка, которые реально подходят к событию. "
        "Если нет ни одной подходящей вещи, честно скажи об этом. "
        "Если подходит только 1, не добавляй ничего лишнего. "
        "запрещено включать одежду, которая не подходит по сезону (лето, зима, весна и т.д.)"
        "перечислять только вещи, подходящие по погоде и мероприятию"
        "ПОМНИ ЧТО ТВОИ РЕКОМЕНДАЦИИ ПОВЛИЯЮТ НА ПОЛЬЗОВАТЕЛЯ"
        "Верни список названий файлов подходящих вещей (в точности как в списке выше).\n\n"
        "2. Затем дай рекомендации:\n"
        "- Как можно дополнить образ\n"
        "- Как эти вещи лучше носить\n"
        "- Какие цвета и акценты подойдут\n\n"
        "Формат ответа:\n"
        "---\n"
        "📸 Подходящие вещи:\n"
        "- filename1.jpg\n"
        "- filename2.jpg\n"
        "(или: ❌ Подходящих вещей нет)\n\n"
        "🎯 Рекомендации:\n"
        "Текст советов...\n"
        "---\n"
        "Не добавляй других заголовков, emoji, комментариев — только указанный шаблон."
    )

    data = {
        "model": "llama3.2:latest",
        "prompt": prompt,
        "stream": True
    }

    try:
        response = requests.post(OLLAMA_URL, json=data, stream=True)
        response.raise_for_status()

        full_response = ""
        for line in response.iter_lines():
            if line:
                chunk = json.loads(line.decode("utf-8"))
                full_response += chunk.get("response", "")

        return full_response.strip()
    except Exception as e:
        print(f"[Ollama error] {e}")
        return None


def analyze_clothing_item(file_path: str) -> dict:
    """
    Анализирует изображение одежды с помощью модели gemma3.
    Возвращает словарь с описанием вещи, тегами, сезоном и полом.
    """
    # Читаем файл и конвертируем в base64
    with open(file_path, "rb") as image_file:
        image_bytes = image_file.read()
    image_base64 = base64.b64encode(image_bytes).decode("utf-8")

    # Промт для модели — описание вещи с требованием возвращать JSON
    prompt = (
        "Ты fashion-аналитик. Проанализируй изображение одежды. "
        "Верни результат строго в виде JSON объекта с полями:\n"
        "description: строка с описанием одежды,\n"
        "tags: список ключевых слов,\n"
        "season: список сезонов (зима, лето, весна, осень),\n"
        "sex: мужской, женский или унисекс.\n"
        "Не добавляй других слов, кроме JSON!"
    )

    data = {
        "model": "gemma3",
        "prompt": prompt,
        "images": [image_base64]
    }

    response = requests.post("http://localhost:11434/api/generate", json=data)
    response.raise_for_status()

    full_response = ""
    for line in response.iter_lines():
        if line:
            chunk = json.loads(line.decode("utf-8"))
            full_response += chunk.get("response", "")

    # Вырезаем JSON из ответа модели
    try:
        json_start = full_response.find("{")
        json_end = full_response.rfind("}") + 1
        item_metadata = json.loads(full_response[json_start:json_end])
    except Exception as e:
        raise ValueError(f"Ошибка при парсинге ответа модели: {e}")

    # Проверка корректности полей и значений
    required_keys = {"description", "tags", "season", "sex"}
    if not required_keys.issubset(item_metadata.keys()):
        raise ValueError(f"Ответ модели не содержит необходимые поля: {required_keys}")

    return item_metadata
