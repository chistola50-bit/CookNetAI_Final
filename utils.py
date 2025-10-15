import os

def generate_caption(title: str, desc: str) -> str:
    """
    Возвращает короткую подпись к рецепту.
    Если есть OPENAI_API_KEY — можно подключить OpenAI (см. комментарий ниже).
    Пока — лёгкий шаблон без внешних запросов.
    """
    title = (title or "").strip()
    desc = (desc or "").strip()
    if not title and not desc:
        return "Домашнее блюдо, приготовленное с любовью 😋"
    # Простая "умная" подпись
    base = "Нежное, ароматное и вкусное блюдо"
    if "суп" in title.lower() or "суп" in desc.lower():
        base = "Согревающий суп с богатым вкусом"
    elif "паста" in title.lower() or "макар" in desc.lower():
        base = "Итальянская классика — паста al dente"
    elif "тост" in title.lower() or "авокадо" in desc.lower():
        base = "Лёгкий и полезный тост для энергии"
    return f"{base}. Идеально для друзей и семьи!"
    
    # --- Вариант с OpenAI ---
    # import openai
    # api_key = os.getenv("OPENAI_API_KEY")
    # if not api_key:
    #     return base
    # openai.api_key = api_key
    # prompt = f"Сделай короткую, аппетитную подпись (до 12 слов) для рецепта '{title}'. Описание: {desc}"
    # try:
    #     resp = openai.Completion.create(
    #         model="gpt-3.5-turbo-instruct",
    #         prompt=prompt,
    #         max_tokens=40
    #     )
    #     return resp.choices[0].text.strip()
    # except Exception:
    #     return base
