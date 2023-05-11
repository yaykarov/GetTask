#!/usr/bin/python
# -*- coding: utf-8 -*-

import xlrd
import xlwt
from xlutils.filter import process, XLRDReader, XLWTWriter
import re

from functools import partial


def copy(rdbook):
    w = XLWTWriter()
    process(XLRDReader(rdbook, "unknown.xls"), w)
    return w.output[0][1], w.style_list

CELL_RX = re.compile("^([a-z]+)(\d+)$")
def cell_name_to_position(cellname):
    cellname = cellname.lower()
    m = CELL_RX.match(cellname)
    if m:
        row = int(m.group(2))
        column_text = m.group(1)
        column = 0
        for i in range(len(column_text), 0, -1):
            n = ord(column_text[i - 1]) - ord('a') + 1
            rank = pow(ord('z') - ord('a') + 1, len(column_text) - i)
            column = column + n * rank

        return row - 1, column - 1
    else:
        raise Exception("Wrong cell name \"{0}\".".format(cellname))


class PlainCell(object):
    def __init__(self, write_to_cell, cellname):
        self._write_to_cell = write_to_cell
        self._row, self._column = cell_name_to_position(cellname)

    def write(self, value):
        self._write_to_cell(self._row, self._column, value)
        return None


class Interval(object):
    def __init__(self, write_to_cell, params, double=False):
        self._write_to_cell = write_to_cell
        cell_0, cell_1, last_cell = params
        self._cell_0 = cell_name_to_position(cell_0)
        self._cell_1 = cell_name_to_position(cell_1)
        self._last_cell = cell_name_to_position(last_cell)
        self.double = double
        self._row, self._column_0 = self._cell_0
        tmp, self._column_1 = self._cell_1
        tmp, self._last_column = self._last_cell
        self._step = self._column_1 - self._column_0
        self.cells_count = (self._last_column - self._column_0) / self._step
        self.multi_interval = False

    def write(self, value):
        column = self._column_0
        symbol_count = 1
        if self.double:
            value_length = len(value)
            if value_length > self.cells_count or self.multi_interval:
                symbol_count = 2
                if value_length / 2 - value_length // 2:
                    value += ' '
        for i in range(0, len(value), symbol_count):
            if column <= self._last_column:
                self._write_to_cell(self._row, column, str(value[i: (i + symbol_count)]))
                column = column + self._step
            else:
                return value[i + symbol_count - 1:]
        return None


class MultiInterval(object):
    def __init__(self, write_to_cell, params, double=False):
        self._intervals = []
        self._double = double
        for p in params:
            self._intervals.append(Interval(write_to_cell, p, double))

    def write(self, value):
        if self._double:
            value_length = len(value)
            cells_count = 0
            for item in self._intervals:
                cells_count += item.cells_count
            if value_length > cells_count:
                if value_length / 2 - value_length // 2:
                    value += ' '
            else:
                self._double = False
        for i in self._intervals:
            i.double = self._double
            i.multi_interval = True
            value = i.write(value)
            if value is None:
                return None
        return value


def create_writer(write_to_cell, params):
    double = False
    if isinstance(params, dict):
        double = params['type'] == "double"
        params = params['cells']
    if isinstance(params, str):
        return PlainCell(write_to_cell, params)
    elif isinstance(params, list):
        return MultiInterval(write_to_cell, params, double)
    else:
        # assuming params is tuple
        return Interval(write_to_cell, params, double)


def create_excel_document(filename, config, values):
    src = xlrd.open_workbook(filename, formatting_info="True")
    dst, style_list = copy(src)
    for sheet_index, sheet_config in config:
        rdsheet = src.sheet_by_index(sheet_index)
        wtsheet = dst.get_sheet(sheet_index)
        def write_to_cell(row, column, value):
            style_index = rdsheet.cell_xf_index(row, column)
            wtsheet.write(row, column, value, style_list[style_index])
        for key, params in sheet_config.items():
            if key in values:
                writer = create_writer(write_to_cell, params)
                writer.write(values[key])
    for sheet_index in range(len(src.sheets())):
        sheet = dst.get_sheet(sheet_index)
        sheet.fit_num_pages = 1
        sheet.header_str = b""
        sheet.footer_str = b""
    return dst



RKO_FILENAME = "rko.xls"
RKO_CONFIG = [
    (
        0,
        {
            "org_name" :                        "A6",   # Организация
            "okpo_code" :                       "CT6",  # Форма по ОКПО (?)
            "structural_unit" :                 "A8",   # Структурное подразделение
            "document_id" :                     "CC11", # Номер документа
            "document_date" :                   "CT11", # Дата составления
            "debet_structure_code" :            "H15",  # Дебет -> код структурного подразделения
            "debet_subaccount" :                "AA15", # Дебет -> корреспондирующий счет, субсчет
            "debet_analysis_code" :             "AV15", # Дебет -> код аналитического учета
            "credit" :                          "BT15", # Кредит
            "amount_digits" :                   "CC15", # Сумма, руб. коп.
            "target_code" :                     "CQ15", # Код целевого назначения
            "to_whom" :                         "H17",  # Выдать, (фамилия, имя, отчество)
            "rationale" :                       "K19",  # Основание
            "amount_roubles_text" :             "G20",  # Сумма, прописью, рублей
            "amount_kopeck_text" :              "CL22", # Сумма, прописью, копеек
            "application" :                     "L23",  # Приложение
            "org_head_position" :               "Z25",  # Руководитель организации, должность
            "org_head_initials" :               "BR25", # Расшифровка подписи, руководитель
            "accountant_initials" :             "AK27", # Расшифровка подписи, главбух
            "received_ammount_roubles_text" :   "I29",  # Получил (сумма прописью) рублей
            "received_ammount_roubles_kopeck" : "CL31", # Получил (сумма прописью) копеек
            "doc_day":                          "C32",  # день
            "doc_month":                        "J32",  # месяц прописью
            "doc_year":                         "AC32", # Год
            "receiver_identity" :               "D33",  # По (наименование, номер, дата и место выдачи документа, удостоверяющего личность получателя)
        }
    )
]
def create_rko(values):
    return create_excel_document(RKO_FILENAME, RKO_CONFIG, values)

AKT_FILENAME = "Akt.xls"
AKT_CONFIG = [
    (
        0,
        {
            "cap_text" :                        "A6",  # Шапка
            "unit_name" :                       "A9",  # Наименование
            "quantity" :                        "B9",  # Количество
            "unit_measure" :                    "C9",  # Единица измерения
            "unit_price" :                      "D9",  # Цена
            "cost" :                            "E9",  # Стоимость
            "average_cost" :                    "E11", # Стоимость итого
            "text_average_cost" :               "A14", # Стоимость, итого, в т.ч. прописью
            "full_name" :                       "A19", # ФИО
        }
    )
]

def create_act(values):
    return create_excel_document(AKT_FILENAME, AKT_CONFIG, values)


def test(config, creator):
    values = {}
    for tmp, sheet_config in config:
        for k, v in sheet_config.items():
            values[k] = k + " and some more text"
    filled_document = creator(values)
    filled_document.save("dst.xls")


def test_0():
    test(RKO_CONFIG, create_rko)


if __name__ == "__main__":
    test_0()
