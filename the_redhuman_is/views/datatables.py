# -*- coding: utf-8 -*-


def selected_columns(params):
    mask = 'columns[{}][data]'
    i = 0
    columns = []
    key = mask.format(i)
    while key in params:
        columns.append(params[key])
        i += 1
        key = mask.format(i)

    return columns


def order(params):
    order_column = params.get('order[0][column]')
    if order_column:
        order_column = int(order_column)
    else:
        order_column = 0

    order_dir = '-' if params.get('order[0][dir]') == 'asc' else ''

    return order_column, order_dir


def filter_range(query, params):
    total = query.count()

    start = int(params['start'])
    length = int(params['length'])

    if total > 0:
        finish = total
        if length > 0:
            finish = min(total, start+length)
        query = query[start:finish]

    return total, query
