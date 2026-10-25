import math

def calculate_total(items, discount_percent=0):
    if isinstance(discount_percent, bool) or not isinstance(discount_percent, (int, float)) or not math.isfinite(discount_percent) or not 0 <= discount_percent <= 100:
        raise ValueError('invalid discount')
    subtotal = 0
    for item in items:
        if not isinstance(item, dict) or 'price' not in item or 'quantity' not in item:
            raise ValueError('invalid item')
        price, quantity = item['price'], item['quantity']
        if isinstance(price, bool) or not isinstance(price, (int, float)) or not math.isfinite(price) or price < 0:
            raise ValueError('invalid price')
        if isinstance(quantity, bool) or not isinstance(quantity, int) or quantity <= 0:
            raise ValueError('invalid quantity')
        subtotal += price * quantity
    return round(subtotal * (1 - discount_percent / 100), 2)
