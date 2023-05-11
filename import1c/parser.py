# -*- coding: utf-8 -*-
#
# https://v8.1c.ru/tekhnologii/obmen-dannymi-i-integratsiya/standarty-i-formaty/standart-obmena-s-sistemami-klient-banka/formaty-obmena/ 
#

import decimal
import datetime
from collections.abc import Mapping


class ParserException(Exception):
    pass


class SyntaxError(ParserException):
    pass


class _Node(Mapping):
    def __init__(self):
        self.dict = {}

    def add(self, key, value):
        if key in self.dict:
            if not isinstance(self.dict[key], list):
                self.dict[key] = [self.dict[key], value]
            else:
                self.dict[key].append(value)
        else:
            self.dict[key] = value

    def __getstate__(self):
        return self.dict

    def __setstate__(self, state_dict):
        self.dict = state_dict

    def items(self):
        return self.dict.items()

    def __getitem__(self, key):
        return self.dict[key]

    def __iter__(self):
        return iter(self.dict)

    def __len__(self):
        return len(self.dict)

    def getint(self, key):
        return int(self[key])

    def getdate(self, key, format="%d.%m.%Y"):
        return datetime.datetime.strptime(self[key], format).date()

    def getmoney(self, key):
        return decimal.Decimal(self[key]).quantize(decimal.Decimal("0.01"))

    def get(self, key, default=None):
        return self.dict.get(key, default)

    def __str__(self):
        return ', '.join('{}={}'.format(k, v) for k, v in self.dict.items())

    def __repr__(self):
        return '{}<{}>'.format(self.__class__.__name__, str(self).encode('utf-8'))


class Header(_Node):
    pass


class AccountInfo(_Node):
    pass


class Document(_Node):
    def __init__(self, doc_type):
        super(Document, self).__init__()
        self.add('СекцияДокумент', doc_type)
        self.doc_type = doc_type

    def __setstate__(self, state_dict):
        super(Document, self).__setstate__(state_dict)
        self.doc_type = self['СекцияДокумент']

    def is_incoming(self, header):
        accounts = header['РасчСчет']
        if not isinstance(accounts, list):
            accounts = [accounts]
        for acc in accounts:
            if (acc == self['ПолучательСчет']) and ('ДатаПоступило' in self):
                return True
            elif (acc == self['ПлательщикСчет']) and ('ДатаСписано' in self):
                return False

        raise ParserException(
            (
                "Can't detect if operation '{}' is incoming or outgoing "
                "ПолучательСчет: '{}', ДатаПоступило: '{}'; "
                "ПлательщикСчет: '{}', ДатаСписано: '{}'; "
                "РасчСчет: '{}'"
            ).format(
                self,
                self.get('ПолучательСчет'),
                self.get('ДатаПоступило'),
                self.get('ПлательщикСчет'),
                self.get('ДатаСписано'),
                acc
            )
        )

    def _payment_purpose(self):
        if 'НазначениеПлатежа' in self:
            return self['НазначениеПлатежа']
        else:
            comment_lines = []
            for i in range(1, 6):
                k = 'НазначениеПлатежа{0}'.format(i)
                if k not in self:
                    break
                comment_lines.append(self[k])
            return '\n'.join(comment_lines)

    def comment(self, is_incoming):
        def _get(key1, key2):
            value = self.get(key1)
            if value:
                return value
            return self[key2]

        if is_incoming:
            prefix = 'От кого: '
            partner = _get('Плательщик1', 'Плательщик')
        else:
            prefix = 'Кому: '
            partner = _get('Получатель1', 'Получатель')

        return '{}{};\nНазначение: {}'.format(
            prefix,
            partner,
            self._payment_purpose()
        )

    def get_uniq_key(self):
        # XXX: ensure 1'st 2 elements are correct. Maybe it should be
        # the preceeding 'AccountInfo' node?
        return (
            self['ПлательщикСчет'],
            self['ПолучательСчет'],
            self.doc_type,
            self['Дата'],
            self['Номер'],
            self._payment_purpose(),
        )


def parse(content):
    # conctent should be in unicode
    S_NONE = 0
    S_HEADER = 1
    S_ACCOUNT_INFO = 2
    S_DOCUMENT = 3
    lines = content.splitlines()
    state = S_NONE
    account = document = header = None
    for lno, line in enumerate(lines):
        line = line.strip()
        if not line:
            # skip empty lines
            continue
        token = line.split('=', 1)
        key = token[0]
        if len(token) > 1:
            value = token[1]
        else:
            value = None

        def _add_kv(target):
            if key == 'РасчСчет':
                if key not in target:
                    target.add(key, [])
                target[key].append(value)
                print(target)
            else:
                target.add(key, value)

        if state == S_NONE:
            if line == "1CClientBankExchange":
                header = Header()
                state = S_HEADER
            elif line == 'СекцияРасчСчет':
                account = AccountInfo()
                state = S_ACCOUNT_INFO
            elif key == 'СекцияДокумент':
                document = Document(value)
                state = S_DOCUMENT
            elif key == 'КонецФайла':
                return
            else:
                raise SyntaxError(line, lno, state)
        elif state == S_HEADER:
            if line == 'СекцияРасчСчет':
                yield header
                state = S_ACCOUNT_INFO
                account = AccountInfo()
            elif key == 'КонецФайла':
                return
            elif value is not None:
                _add_kv(header)
            else:
                raise SyntaxError(line, lno, state)
        elif state == S_ACCOUNT_INFO:
            if line == 'КонецРасчСчет':
                yield account
                state = S_NONE
            elif value is not None:
                _add_kv(account)
            else:
                raise SyntaxError(line, lno, state)
        elif state == S_DOCUMENT:
            if line == 'КонецДокумента':
                yield document
                state = S_NONE
            elif value is not None:
                _add_kv(document)
            else:
                raise SyntaxError(line, lno, state)
