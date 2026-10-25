def calculate_total(items, discount_percent=0):
    return sum(item['price'] * item['quantity'] for item in items)
