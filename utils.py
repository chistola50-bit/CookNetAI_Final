def generate_caption(title: str, description: str) -> str:
    """Lightweight caption generator without external APIs."""
    title = (title or '').strip()
    description = (description or '').strip()
    if not title and not description:
        return "Вкусный домашний рецепт"
    if title and not description:
        return f"{title} — простой и быстрый рецепт"
    short = (description[:120] + '…') if len(description) > 120 else description
    return f"{title}: {short}"
