#!/usr/bin/python
# -*- coding: utf-8 -*-

import xlrd
import xlwt
from xlutils.filter import process, XLRDReader, XLWTWriter
import re

from functools import partial

conf = {
    "org_address": [("BC53", "BF53", "DW53"), ("A55", "D55", "DW55")],  # если записывать надо в несколько интервалов
    "org_name": "A6",  # простое поле, фигачить весь текст туда
    "worker_lastname": ("W13", "AA13", "FC13"),  # массив полей, заполнять по букве до конца,
    #Worker
    "last_name": ("Y53", "AB53", "DW53"), #фамилия
    "name": ("Y55", "AB55", "DW55"), #имя
    "patronymic": ("Y57", "AB57", "DW57"), #отчество(если есть)
    "citizenship": ("Y59", "AB59", "DW59"), #гражданство
    "place_of_birth": [("Y61", "AB61", "DW61"), ("A63", "D63", "DW63")], #место рождения (государство, населенный пункт)
    #Дата рождения:
    "birth_date_day": ("V65", "Y65", "Y65"), #число
    "birth_date_month": ("AH65", "AK65", "AK65"), #месяц
    "birth_date_year": ("AQ65", "AT65", "AZ65"), #год
    #Пол:
    "sex_m": "BL65", #муж
    "sex_w": "BU65", #жен
    #2
    #Паспорт(WorkerPassport):
    "passport": ("AK3", "AN3", "DW3"), #тип документа
    "pass_series": ("M5", "P5", "AH5"), #серия
    "pass_num": ("AT5", "AW5", "BX5"), #номер
    #Дата выдачи
    "pass_date_of_issue_day": ("CP5", "CS5", "CS5"),
    "pass_date_of_issue_month": ("DB5", "DE5", "DE5"),
    "pass_date_of_issue_year": ("DN5", "DQ5", "DW5"),
    "pass_issued_by": ("P7", "S7", "DW7"), #кем выдан
    #Миграционная карта(Worker):
    "mig_series_number": ("AN9", "AQ9", "BX9"), #серия и номер
    #Дата выдачи
    "m_day": ("CP9", "CS9", "CS9"),
    "m_month": ("DB9", "DE9", "DE9"),
    "m_year": ("DN9", "DQ9", "DW9"),
    #Регистрация(WorkerRegistration):
    "reg_address": [("AW12", "AZ12", "DW12"), ("A14", "D14", "DW14"), ("A16", "D16", "DW16")], #адрес регистрации
    #Дата постановки на учет:
    "reg_date_day": ("AW18", "AZ18", "AZ18"),
    "reg_date_month": ("BI18", "BL18", "BL18"),
    "reg_date_year": ("BU18", "BX18", "CD18"),
    #Договор(Contract):
    "cont_name": ("A44", "D44", "DW44"), #профессия либо номер договора и название (в случае гпх)
    #Тип договора
    "td": "A48", #трудовой
    "gpd": "AE48", #гпх
    #Дата заключения договора:
    "cont_day": ("CP50", "CS50", "CS50"),
    "cont_month": ("DB50", "DE50", "DE50"),
    "cont_year": ("DN50", "DQ50", "DW50"),
    #Документ:
    "doc_day": "C60", #день
    "doc_month": "H60", #месяц прописью
    "doc_year": "Z60", #2 цифры года
}