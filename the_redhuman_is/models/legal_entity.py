# -*- coding: utf-8 -*-

import decimal

from django.db import (
    models,
    transaction,
)

import finance

from finance.model_utils import (
    ensure_account,
    ensure_accounts_chain,
    ensure_root_account,
)

from utils.numbers import ZERO_OO


def vat_20(amount):
    return decimal.Decimal(
        (amount / decimal.Decimal('1.2')) * decimal.Decimal('0.2')
    ).quantize(ZERO_OO)


class LegalEntity(models.Model):
    short_name = models.CharField(
        verbose_name='Краткое название',
        max_length=160
    )

    def uses_simple_tax_system(self):
        return LegalEntitySimpleTaxSystemAccounts.objects.filter(
            legal_entity=self
        ).exists()

    @transaction.atomic
    def try_to_delete(self):
        self.legal_entity_common_accounts.try_to_delete()
        if hasattr(self, 'legal_entity_general_tax_system_accounts'):
            self.legal_entity_general_tax_system_accounts.try_to_delete()
        if hasattr(self, 'legal_entity_simple_tax_system_accounts'):
            self.legal_entity_simple_tax_system_accounts.try_to_delete()
        self.delete()

    def expense_accounts(self):
        accounts = self.legal_entity_common_accounts.expense_accounts()
        if hasattr(self, 'legal_entity_general_tax_system_accounts'):
            accounts.extend(
                self.legal_entity_general_tax_system_accounts.expense_accounts()
            )
        if hasattr(self, 'legal_entity_simple_tax_system_accounts'):
            accounts.extend(
                self.legal_entity_simple_tax_system_accounts.expense_accounts()
            )

        return accounts

    def __str__(self):
        return self.short_name


def _26_root():
    return ensure_root_account('26.', '26. Общехозяйственные расходы')


def _68_root():
    return ensure_root_account('68.', '68. Расчеты по налогам и сборам')


def _69_root():
    return ensure_root_account('69.', '69. Расчеты по социальному страхованию и обеспечению')


def _90_root():
    return ensure_root_account('90.', '90. Продажи')


# Для справки использовался план счетов с
# https://ppt.ru/info/plan-schetov/68
# https://ppt.ru/art/buh-uchet/nachisleni-strah-vznosi
class LegalEntityCommonAccounts(models.Model):
    legal_entity = models.OneToOneField(
        LegalEntity,
        on_delete=models.CASCADE,
        verbose_name='Юрлицо',
        related_name='legal_entity_common_accounts'
    )

    # НДФЛ
    account_26_68_01 = models.ForeignKey(
        finance.models.Account,
        on_delete=models.PROTECT,
        verbose_name='26/68.01/Юрлицо (НДФЛ)',
        related_name='account_26_68_01_legal_entity_common_accounts'
    )
    # ФСС
    account_26_69_1_1 = models.ForeignKey(
        finance.models.Account,
        on_delete=models.PROTECT,
        verbose_name='26/69 ФСС, ВН и М/Юрлицо (ФСС)',
        related_name='account_26_69_1_1_legal_entity_common_accounts'
    )
    account_26_69_1_2 = models.ForeignKey(
        finance.models.Account,
        on_delete=models.PROTECT,
        verbose_name='26/69 ФСС, НС и ПЗ/Юрлицо (ФСС)',
        related_name='account_26_69_1_2_legal_entity_common_accounts'
    )
    # ОПС
    account_26_69_2 = models.ForeignKey(
        finance.models.Account,
        on_delete=models.PROTECT,
        verbose_name='26/69/2/Юрлицо (ОПС)',
        related_name='account_26_69_2_legal_entity_common_accounts'
    )
    # ОМС
    account_26_69_3 = models.ForeignKey(
        finance.models.Account,
        on_delete=models.PROTECT,
        verbose_name='26/69/3/Юрлицо (ОМС)',
        related_name='account_26_69_3_legal_entity_common_accounts'
    )
    # Комиссия, Банки
    account_26_bank_comission = models.ForeignKey(
        finance.models.Account,
        on_delete=models.PROTECT,
        verbose_name='Комиссия, Банки',
        related_name='account_26_bank_comission_legal_entity_common_accounts',
    )
    # Комиссия, Партнеры
    account_26_partner_comission = models.ForeignKey(
        finance.models.Account,
        on_delete=models.PROTECT,
        verbose_name='Комиссия, Партнеры',
        related_name='account_26_partner_comission_legal_entity_common_accounts',
    )
    account_51_root = models.ForeignKey(
        finance.models.Account,
        on_delete=models.PROTECT,
        verbose_name='51/Юрлицо',
        related_name='account_51_legal_entity_common_accounts'
    )
    # НДФЛ
    account_68_01 = models.ForeignKey(
        finance.models.Account,
        on_delete=models.PROTECT,
        verbose_name='68/01/Юрлицо (НДФЛ)',
        related_name='account_68_01_legal_entity_common_accounts'
    )
    # ФСС
    account_69_1_1 = models.ForeignKey(
        finance.models.Account,
        on_delete=models.PROTECT,
        verbose_name='69/ФСС, ВН и М/Юрлицо (ФСС)',
        related_name='account_69_1_1_legal_entity_common_accounts'
    )
    account_69_1_2 = models.ForeignKey(
        finance.models.Account,
        on_delete=models.PROTECT,
        verbose_name='69/ФСС, НС и ПЗ/Юрлицо (ФСС)',
        related_name='account_69_1_2_legal_entity_common_accounts'
    )
    # ОПС
    account_69_2 = models.ForeignKey(
        finance.models.Account,
        on_delete=models.PROTECT,
        verbose_name='69/2/Юрлицо (ОПС)',
        related_name='account_69_2_legal_entity_common_accounts'
    )
    # ОМС
    account_69_3 = models.ForeignKey(
        finance.models.Account,
        on_delete=models.PROTECT,
        verbose_name='69/3/Юрлицо (ОМС)',
        related_name='account_69_3_legal_entity_common_accounts'
    )

    # Себестоимость (для закрытия периода)
    account_90_2 = models.ForeignKey(
        finance.models.Account,
        on_delete=models.PROTECT,
        verbose_name='90/2/Общехоз. расходы/Юрлицо',
        related_name='account_90_2_legal_entity_common_accounts',
    )
    # Прибыль/убыток
    account_90_9 = models.ForeignKey(
        finance.models.Account,
        on_delete=models.PROTECT,
        verbose_name='90/9/Общехоз. расходы/Юрлицо',
        related_name='account_90_9_legal_entity_common_accounts',
    )

    @transaction.atomic
    def try_to_delete(self):
        accounts = self.expense_accounts() + [
            self.account_51_root,
            self.account_68_01,
            self.account_69_1_1,
            self.account_69_1_2,
            self.account_69_2,
            self.account_69_3,
            self.account_90_2,
        ]
        self.delete()
        for account in accounts:
            account.delete()

    def expense_accounts(self):
        return [
            self.account_26_68_01,
            self.account_26_69_1_1,
            self.account_26_69_1_2,
            self.account_26_69_2,
            self.account_26_69_3,
            self.account_26_bank_comission,
            self.account_26_partner_comission,
        ]

    def __str__(self):
        return self.legal_entity.short_name


@transaction.atomic
def _create_legal_entity_common_accounts(legal_entity):
    root_26 = _26_root()
    root_51 = ensure_root_account('51.', '51. Расчетные счета')
    root_68 = _68_root()
    root_69 = _69_root()
    root_90 = _90_root()

    account_26_68_01 = ensure_accounts_chain(root_26, ['68.01 НДФЛ', legal_entity.short_name])

    account_26_69_1_1 = ensure_accounts_chain(root_26, ['69 ФСС, ВН и М', legal_entity.short_name])
    account_26_69_1_2 = ensure_accounts_chain(root_26, ['69 ФСС, НС и ПЗ', legal_entity.short_name])

    account_26_69_2 = ensure_accounts_chain(root_26, ['69.2 ОПС', legal_entity.short_name])

    account_26_69_3 = ensure_accounts_chain(root_26, ['69.3 ОМС', legal_entity.short_name])

    account_26_bank_comission = ensure_accounts_chain(
        root_26,
        ['Комиссия, банки', legal_entity.short_name]
    )
    account_26_partner_comission = ensure_accounts_chain(
        root_26,
        ['Комиссия, партнеры', legal_entity.short_name]
    )

    account_51_root = ensure_account(root_51, legal_entity.short_name)

    account_68_01 = ensure_accounts_chain(root_68, ['01. НДФЛ', legal_entity.short_name])

    account_69_1_1 = ensure_accounts_chain(root_69, ['ФСС, ВН и М', legal_entity.short_name])
    account_69_1_2 = ensure_accounts_chain(root_69, ['ФСС, НС и ПЗ', legal_entity.short_name])

    account_69_2 = ensure_accounts_chain(root_69, ['2. ОПС', legal_entity.short_name])

    account_69_3 = ensure_accounts_chain(root_69, ['3. ОМС', legal_entity.short_name])

    account_90_2 = ensure_accounts_chain(
        root_90,
        ['2. Себестоимость продаж', 'Общехозяйственные расходы', legal_entity.short_name]
    )
    account_90_9 = ensure_accounts_chain(
        root_90,
        ['9. Прибыль/убыток от продаж', 'Общехозяйственные расходы', legal_entity.short_name]
    )

    return LegalEntityCommonAccounts.objects.create(
        legal_entity=legal_entity,
        account_26_68_01=account_26_68_01,
        account_26_69_1_1=account_26_69_1_1,
        account_26_69_1_2=account_26_69_1_2,
        account_26_69_2=account_26_69_2,
        account_26_69_3=account_26_69_3,
        account_26_bank_comission=account_26_bank_comission,
        account_26_partner_comission=account_26_partner_comission,
        account_51_root=account_51_root,
        account_68_01=account_68_01,
        account_69_1_1=account_69_1_1,
        account_69_1_2=account_69_1_2,
        account_69_2=account_69_2,
        account_69_3=account_69_3,
        account_90_2=account_90_2,
        account_90_9=account_90_9,
    )


class LegalEntityGeneralTaxSystemAccounts(models.Model):
    legal_entity = models.OneToOneField(
        LegalEntity,
        on_delete=models.CASCADE,
        verbose_name='Юрлицо',
        related_name='legal_entity_general_tax_system_accounts'
    )

    # НДС к вычету
    account_19 = models.ForeignKey(
        finance.models.Account,
        on_delete=models.PROTECT,
        verbose_name='19/Юрлицо (НДС к вычету)',
        related_name='account_19_legal_entity_general_tax_system_accounts'
    )
    # Налог на прибыль
    account_26_68_04_2 = models.ForeignKey(
        finance.models.Account,
        on_delete=models.PROTECT,
        verbose_name='26/04.02/Юрлицо (Налог на прибыль)',
        related_name='account_26_68_04_2_legal_entity_general_tax_system_accounts'
    )
    # НДС
    account_68_02 = models.ForeignKey(
        finance.models.Account,
        on_delete=models.PROTECT,
        verbose_name='68/02/Юрлицо (НДС)',
        related_name='account_68_02_legal_entity_general_tax_system_accounts'
    )
    # Налог на прибыль
    account_68_04_2 = models.ForeignKey(
        finance.models.Account,
        on_delete=models.PROTECT,
        verbose_name='68/04.2/Юрлицо (Налог на прибыль)',
        related_name='account_68_04_2_legal_entity_general_tax_system_accounts'
    )

    @transaction.atomic
    def try_to_delete(self):
        accounts = self.expense_accounts() + [
            self.account_19,
            self.account_68_02,
            self.account_68_04_2,
        ]
        self.delete()
        for account in accounts:
            account.delete()

    def expense_accounts(self):
        return [self.account_26_68_04_2]

    def __str__(self):
        return self.legal_entity.short_name


@transaction.atomic
def _create_legal_entity_general_tax_system_accounts(legal_entity):
    root_19 = ensure_root_account(
        '19.',
        '19. Налог на добавленную стоимость по приобретенным ценностям'
    )
    root_26 = _26_root()
    root_68 = _68_root()

    account_19 = ensure_account(root_19, legal_entity.short_name)
    account_26_68_04_2 = ensure_accounts_chain(
        root_26,
        ['68.04.2. Расчет налога на прибыль', legal_entity.short_name]
    )
    account_68_02 = ensure_accounts_chain(root_68, ['02. НДС', legal_entity.short_name])
    account_68_04_2 = ensure_accounts_chain(
        root_68,
        ['04.2. Расчет налога на прибыль', legal_entity.short_name]
    )

    return LegalEntityGeneralTaxSystemAccounts.objects.create(
        legal_entity=legal_entity,
        account_19=account_19,
        account_26_68_04_2=account_26_68_04_2,
        account_68_02=account_68_02,
        account_68_04_2=account_68_04_2,
    )


class LegalEntitySimpleTaxSystemAccounts(models.Model):
    legal_entity = models.OneToOneField(
        LegalEntity,
        on_delete=models.CASCADE,
        verbose_name='Юрлицо',
        related_name='legal_entity_simple_tax_system_accounts'
    )

    # УСН
    account_26_68_12 = models.ForeignKey(
        finance.models.Account,
        on_delete=models.PROTECT,
        verbose_name='26/68.12/Юрлицо (УСН)',
        related_name='account_26_68_12_legal_entity_simple_tax_system_accounts'
    )
    # ПСН
    account_26_68_14 = models.ForeignKey(
        finance.models.Account,
        on_delete=models.PROTECT,
        verbose_name='26/68.14/Юрлицо (ПСН)',
        related_name='account_26_68_14_legal_entity_simple_tax_system_accounts',
    )
    # ФФОМС
    account_26_69_06_3 = models.ForeignKey(
        finance.models.Account,
        on_delete=models.PROTECT,
        verbose_name='26/69.06.3/Юрлицо (ФФОМС)',
        related_name='account_26_69_06_3_legal_entity_simple_tax_system_accounts'
    )
    # ОПС
    account_26_69_06_5_1 = models.ForeignKey(
        finance.models.Account,
        on_delete=models.PROTECT,
        verbose_name='26/69.06.5/1/Юрлицо (ОПС фиксированные взносы)',
        related_name='account_26_69_06_5_1_legal_entity_simple_tax_system_accounts'
    )
    account_26_69_06_5_2 = models.ForeignKey(
        finance.models.Account,
        on_delete=models.PROTECT,
        verbose_name='26/69.06.5/2/Юрлицо (ОПС 1%)',
        related_name='account_26_69_06_5_2_legal_entity_simple_tax_system_accounts'
    )
    # УСН
    account_68_12 = models.ForeignKey(
        finance.models.Account,
        on_delete=models.PROTECT,
        verbose_name='68/12/Юрлицо (УСН)',
        related_name='account_68_12_legal_entity_simple_tax_system_accounts'
    )
    # ПСН
    account_68_14 = models.ForeignKey(
        finance.models.Account,
        on_delete=models.PROTECT,
        verbose_name='68/14/Юрлицо (ПСН)',
        related_name='account_68_14_legal_entity_simple_tax_system_accounts',
    )
    # ФФОМС
    account_69_06_3 = models.ForeignKey(
        finance.models.Account,
        on_delete=models.PROTECT,
        verbose_name='69/06/3/Юрлицо (ФФОМС)',
        related_name='account_69_06_3_legal_entity_simple_tax_system_accounts'
    )
    # ОПС
    account_69_06_5_1 = models.ForeignKey(
        finance.models.Account,
        on_delete=models.PROTECT,
        verbose_name='69/06/5/1/Юрлицо (ОПС фиксированные взносы)',
        related_name='account_69_06_5_1_legal_entity_simple_tax_system_accounts'
    )
    account_69_06_5_2 = models.ForeignKey(
        finance.models.Account,
        on_delete=models.PROTECT,
        verbose_name='69/06/5/2/Юрлицо (ОПС 1%)',
        related_name='account_69_06_5_2_legal_entity_simple_tax_system_accounts'
    )

    @transaction.atomic
    def try_to_delete(self):
        accounts = self.expense_accounts() + [
            self.account_68_12,
            self.account_68_14,
            self.account_69_06_5_1,
            self.account_69_06_5_2,
            self.account_69_06_3,
        ]
        self.delete()
        for account in accounts:
            account.delete()

    def expense_accounts(self):
        return [
            self.account_26_68_12,
            self.account_26_68_14,
            self.account_26_69_06_3,
            self.account_26_69_06_5_1,
            self.account_26_69_06_5_2,
        ]

    def __str__(self):
        return self.legal_entity.short_name


@transaction.atomic
def _create_legal_entity_simple_tax_system_accounts(legal_entity):
    root_26 = _26_root()
    root_68 = _68_root()
    root_69 = _69_root()

    account_26_68_12 = ensure_accounts_chain(root_26, ['68.12 УСН', legal_entity.short_name])
    account_26_68_14 = ensure_accounts_chain(root_26, ['68.14 ПСН', legal_entity.short_name])
    account_26_69_06_3 = ensure_accounts_chain(
        root_26,
        ['69.06.3 ФОМС ИП', legal_entity.short_name]
    )

    root_26_69_06_5 = ensure_account(root_26, '69.06.5 ОПС ИП')
    account_26_69_06_5_1 = ensure_accounts_chain(
        root_26_69_06_5,
        ['1. Фиксированные взносы', legal_entity.short_name]
    )
    account_26_69_06_5_2 = ensure_accounts_chain(
        root_26_69_06_5,
        ['2. Взносы 1%', legal_entity.short_name]
    )
    account_68_12 = ensure_accounts_chain(root_68, ['12. УСН', legal_entity.short_name])
    account_68_14 = ensure_accounts_chain(root_68, ['14. ПСН', legal_entity.short_name])

    root_69_06_5 = ensure_account(
        root_69,
        '06.5 ОПС ИП'
    )
    account_69_06_5_1 = ensure_accounts_chain(
        root_69_06_5,
        ['1. Фиксированные взносы', legal_entity.short_name]
    )
    account_69_06_5_2 = ensure_accounts_chain(
        root_69_06_5,
        ['2. Взносы 1%', legal_entity.short_name]
    )

    account_69_06_3 = ensure_accounts_chain(root_69, ['06.3 ФОМС ИП', legal_entity.short_name])

    return LegalEntitySimpleTaxSystemAccounts.objects.create(
        legal_entity=legal_entity,
        account_26_68_12=account_26_68_12,
        account_26_68_14=account_26_68_14,
        account_26_69_06_3=account_26_69_06_3,
        account_26_69_06_5_1=account_26_69_06_5_1,
        account_26_69_06_5_2=account_26_69_06_5_2,
        account_68_12=account_68_12,
        account_68_14=account_68_14,
        account_69_06_5_1=account_69_06_5_1,
        account_69_06_5_2=account_69_06_5_2,
        account_69_06_3=account_69_06_3,
    )


@transaction.atomic
def create_legal_entity(short_name, simple_taxes):
    legal_entity = LegalEntity.objects.create(short_name=short_name)
    _create_legal_entity_common_accounts(legal_entity)
    if simple_taxes:
        _create_legal_entity_simple_tax_system_accounts(legal_entity)
    else:
        _create_legal_entity_general_tax_system_accounts(legal_entity)

    return legal_entity
