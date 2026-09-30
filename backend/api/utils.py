def format_shopping_list(ingredients):
    lines = ['Список покупок', '']
    lines.extend(
        f'{item["ingredient__name"]} '
        f'({item["ingredient__measurement_unit"]}) — {item["total"]}'
        for item in ingredients
    )
    return '\n'.join(lines) + '\n'
