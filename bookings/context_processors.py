from bookings.workshop_basket import basket_item_count, get_session_basket


def basket_context(request):
    basket = get_session_basket(request)
    count = basket_item_count(basket)
    return {
        'basket_item_count': count,
        'basket_has_items': count > 0,
    }
