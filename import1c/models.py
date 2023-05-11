import hashlib
import json

from django.db import models
from django.core.exceptions import ObjectDoesNotExist

import finance

from utils.date_time import string_from_date

from . import parser


class Import(models.Model):
    created = models.DateTimeField(auto_now_add=True)
    file_content = models.TextField()
    file_name = models.CharField(max_length=255)
    comment = models.TextField(default='')

    def __str__(self):
        return 'Импорт №{}, {}, {}'.format(
            self.pk,
            string_from_date(self.created),
            self.file_name
        )


class ImportedNode(models.Model):
    HEADER_DOC_TYPE = 'hd'
    ACCOUNT_INFO_DOC_TYPE = 'ai'
    DOCUMENT_DOC_TYPE = 'dt'

    DOC_TYPE_CHOICES = [
        (HEADER_DOC_TYPE, 'Header'),
        (ACCOUNT_INFO_DOC_TYPE, 'AccountInfo'),
        (DOCUMENT_DOC_TYPE, 'Document')
    ]

    theimport = models.ForeignKey(
        Import,
        on_delete=models.PROTECT,
    )
    doc_type = models.CharField(
        choices=DOC_TYPE_CHOICES,
        max_length=2
    )
    key = models.CharField(
        max_length=256,
        unique=True,
        null=True
    )
    position_in_file = models.SmallIntegerField()

    items = models.TextField()
    operation = models.ForeignKey(
        finance.models.Operation,
        on_delete=models.PROTECT,
        null=True,
        blank=True
    )

    def document_header(self):
        assert self.doc_type == ImportedNode.DOCUMENT_DOC_TYPE
        return ImportedNode.objects.filter(
            doc_type=ImportedNode.HEADER_DOC_TYPE,
            theimport=self.theimport,
            position_in_file__lt=self.position_in_file
        ).order_by(
            'position_in_file'
        ).first()

    def document_accounts_info(self):
        assert self.doc_type == ImportedNode.DOCUMENT_DOC_TYPE
        return ImportedNode.objects.filter(
            doc_type=ImportedNode.ACCOUNT_INFO_DOC_TYPE,
            theimport=self.theimport,
        ).order_by(
            'position_in_file'
        )

    @classmethod
    def from_node(cls, theimport, pos, node):
        items = json.dumps(node.__getstate__(), ensure_ascii=False)
        if isinstance(node, parser.Header):
            assert pos == 0
            db_node = cls(
                theimport=theimport,
                doc_type=ImportedNode.HEADER_DOC_TYPE,
                key=None,
                position_in_file=pos,
                items=items
            )
        elif isinstance(node, parser.AccountInfo):
            assert pos > 0
            db_node = cls(
                theimport=theimport,
                doc_type=ImportedNode.ACCOUNT_INFO_DOC_TYPE,
                key=None,
                position_in_file=pos,
                items=items
            )
        elif isinstance(node, parser.Document):
            assert pos > 1
            db_node = cls(
                theimport=theimport,
                doc_type=ImportedNode.DOCUMENT_DOC_TYPE,
                key=cls._doc_key(node),
                position_in_file=pos,
                items=items
            )
        return db_node

    # To parser node
    def to_node(self):
        items = json.loads(self.items)
        if self.doc_type == ImportedNode.HEADER_DOC_TYPE:
            node = parser.Header()
        elif self.doc_type == ImportedNode.ACCOUNT_INFO_DOC_TYPE:
            node = parser.AccountInfo()
        elif self.doc_type == ImportedNode.DOCUMENT_DOC_TYPE:
            node = parser.Document(items['СекцияДокумент'])
        node.__setstate__(items)
        return node

    @staticmethod
    def _doc_key(node):
        str_key = ('|'.join(node.get_uniq_key())).encode('utf-8')
        return hashlib.sha256(str_key).hexdigest()

    @classmethod
    def is_saved(cls, node):
        if not isinstance(node, parser.Document):
            return False
        node_key = cls._doc_key(node)
        try:
            cls.objects.get(key=node_key)
        except cls.DoesNotExist:
            return False
        # TODO: compare node == db_node.to_node() ??????
        return True

    def __str__(self):
        return f'{self.key} {str(self.operation)}'


def unimported_operations_count():
    return ImportedNode.objects.filter(
        operation__isnull=True,
        doc_type=ImportedNode.DOCUMENT_DOC_TYPE
    ).count()


def _best_match(debit, credit):
    if isinstance(debit, list):
        if isinstance(credit, list):
            raise ValueError('Либо debit либо credit должен быть в единственном экземпляре')

        best_debit = None
        max_count = 0
        for account in debit:
            count = finance.models.Operation.objects.filter(
                debet=account,
                credit=credit
            ).count()
            if count > max_count:
                best_debit = account
                max_count = count

        return (best_debit, credit)

    else:
        if not isinstance(credit, list):
            return (debit, credit)

        best_credit = None
        max_count = 0
        for account in credit:
            count = finance.models.Operation.objects.filter(
                debet=debit,
                credit=account
            ).count()
            if count > max_count:
                best_credit = account
                max_count = count

        return (debit, best_credit)


def is_treasury_account(bank_account):
    return bank_account[:5] == '03100'


class AccountMapping(models.Model):
    bank_account = models.CharField(
        max_length=20,
    )
    tax_code = models.CharField(
        max_length=15,
    )
    budget_code = models.CharField(
        max_length=20,
        blank=True,
        null=True
    )
    account = models.ForeignKey(
        finance.models.Account,
        on_delete=models.PROTECT,
    )

    @staticmethod
    def find_autocomplete(document):
        def _find(bank_account, tax_code, budget_code=None):
            mappings = AccountMapping.objects.filter(
                bank_account=bank_account,
                tax_code=tax_code,
                budget_code=budget_code
            )
            if is_treasury_account(bank_account):
                return [m.account for m in mappings]
            else:
                try:
                    return mappings.get().account
                except ObjectDoesNotExist:
                    return None

        kbk = document.get('ПоказательКБК')
        if not kbk:
            kbk = None
        return _best_match(
            _find(
                document['ПолучательСчет'],
                document['ПолучательИНН'],
                kbk
            ),
            _find(document['ПлательщикСчет'], document['ПлательщикИНН'])
        )

    @staticmethod
    def save_autocomplete(document, operation):
        def _save(operating_account, bank_account, tax_code, budget_code=None):
            mapping = None

            try:
                if is_treasury_account(bank_account):
                    mapping = AccountMapping.objects.get(
                        bank_account=bank_account,
                        tax_code=tax_code,
                        budget_code=budget_code,
                        account=operating_account,
                    )
                else:
                    mapping = AccountMapping.objects.get(
                        bank_account=bank_account,
                        tax_code=tax_code,
                        budget_code=budget_code
                    )
                    if mapping.account != operating_account:
                        mapping.account = operating_account
                        mapping.save()

            except ObjectDoesNotExist:
                pass

            if not mapping:
                mapping = AccountMapping.objects.create(
                    bank_account=bank_account,
                    tax_code=tax_code,
                    budget_code=budget_code,
                    account=operating_account,
                )

        kbk = document.get('ПоказательКБК')
        if not kbk:
            kbk = None
        _save(
            operation.debet,
            document['ПолучательСчет'],
            document['ПолучательИНН'],
            kbk
        )
        _save(operation.credit, document['ПлательщикСчет'], document['ПлательщикИНН'])

    def __str__(self):
        return '{}+{} -> {}'.format(
            self.tax_code,
            self.bank_account,
            self.account.full_name
        )
