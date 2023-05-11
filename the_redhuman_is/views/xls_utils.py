# -*- coding: utf-8 -*-

import xlwt

def fill_days(
        worksheet,
        font_style,
        first_row,
        first_column,
        days,
        width=1500):

    date_style = xlwt.XFStyle()
    date_style.font.bold = True
    date_style.num_format_str = 'dd.mm'

    row = first_row
    col = first_column

    weekdays = ['пн', 'вт', 'ср', 'чт', 'пт', 'сб', 'вс']
    for day in days:
        worksheet.col(col).width = width
        worksheet.write(row, col, day, date_style)
        worksheet.write(
            row + 1,
            col,
            weekdays[day.weekday()],
            font_style
        )
        col += 1

    return row, col
