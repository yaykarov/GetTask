# -*- coding: utf-8 -*-

from django.contrib import admin
from import_export import resources
from import_export.admin import ImportExportModelAdmin
from rangefilter.filters import DateRangeFilter

from finance.models import Account

from the_redhuman_is import metro_models
from the_redhuman_is import models

from the_redhuman_is.models import (
    auth,
    chat,
    delivery,
    expenses,
    hostel,
    itella,
    legal_entity,
    partners,
    payment_schedule,
    paysheet_v2,
    turnout_operations,
    vkusvill,
)


class DeliveryRequestAdmin(admin.ModelAdmin):
    raw_id_fields = ['author', 'customer', 'location', 'delivery_service']

    def save_model(self, request, obj, form, change):
        obj.save(user=request.user)


class SaldoListFilter(admin.SimpleListFilter):
    title = 'Сальдо'
    parameter_name = 'saldo'

    def lookups(self, request, model_admin):
        return (
            ('0', 'Равно 0'),
        )

    def queryset(self, request, queryset):
        if self.value() == '0':
            turnouts = queryset.all()
            workers_id = turnouts.order_by().values_list('worker', flat=True).distinct()
            accounts = Account.objects.filter(worker_account__worker__in=workers_id)
            workers_id = list()
            for item in accounts:
                if item.turnover_saldo() == 0:
                    workers_id.append(
                        item.worker_account.worker_id
                    )
            return queryset.filter(worker__in=workers_id)
        return queryset


class WorkerTurnoutsAdmin(admin.ModelAdmin):
    list_display = ('worker', 'date', 'is_payed', 'get_saldo')
    list_filter = ('is_payed', SaldoListFilter, ('date', DateRangeFilter), )
    raw_id_fields = ('timesheet', 'contract', 'worker')
    list_per_page = 100

    def get_saldo(self, obj):
        return obj.worker.worker_account.account.turnover_saldo()

    get_saldo.short_description = 'Остаток на счете'


class WorkerResource(resources.ModelResource):
    class Meta:
        model = models.Worker
        fields = (
            'last_name',
            'name',
            'patronymic',
            'tel_number',
            'birth_date',
            'mig_series',
            'mig_number',
            'm_date_of_issue',
            'm_date_of_exp',
            # 'pass_num',
            'workerpassport__passport_type',
            'workerpassport__another_passport_number',
            'workerpassport__date_of_issue',
            'workerpassport__date_of_exp',
            'workerpassport__issued_by',
            'workerregistration__r_date_of_issue',
            'workerregistration__city',
            'workerregistration__street',
            'workerregistration__house_number',
            'workerregistration__building_number',
            'workerregistration__appt_number',
        )


class WorkerAdmin(ImportExportModelAdmin):
    resource_class = WorkerResource
    search_fields = ['last_name', 'name', 'patronymic']


class NoticeOfArrivalInline(admin.TabularInline):
    model = models.NoticeOfArrival
    max_num = 1


class NoticeOfContractInline(admin.TabularInline):
    model = models.NoticeOfContract
    max_num = 1


class NoticeOfTerminationInline(admin.TabularInline):
    model = models.NoticeOfTermination
    max_num = 1


class ContractAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        '__str__',
        'begin_date',
        'end_date',
        'is_actual',
        'cont_type'
    )
    # date_hierarchy = 'end_date'
    list_display_links = ['id', '__str__']
    search_fields = ['id', ]
    raw_id_fields = ['c_worker', ]
    inlines = [
        NoticeOfArrivalInline,
        NoticeOfContractInline,
        NoticeOfTerminationInline,
    ]


def _register(model, raw_ids, search_ids=None, readonly_ids=None):
    fields = {
        'raw_id_fields': raw_ids
    }
    if search_ids:
        fields['search_fields'] = search_ids
    if readonly_ids:
        fields['readonly_fields'] = readonly_ids
    cls = type(
        model.__name__ + 'Admin',
        (admin.ModelAdmin,),
        fields
    )
    admin.site.register(model, cls)


_register(models.Act, ['turnout', 'rko'])
_register(models.AccountablePerson, ['worker', 'account_71'])
_register(models.BankService, ['debit'])
_register(models.BankServiceParams, ['service', 'account'])
_register(models.CommissionOperation, ['operation', 'commission'])
admin.site.register(models.Contract, ContractAdmin)
admin.site.register(models.Country)
admin.site.register(models.CustComments)
admin.site.register(models.Customer)
admin.site.register(models.CustomerLegalEntity)
_register(models.CustomerAccount, ['customer', 'user'])
_register(models.LocationAccount, ['location', 'user'])
_register(models.CustomerFineDeduction, ['fine', 'deduction'])
admin.site.register(models.CustomerLocation)
_register(
    models.CustomerOperatingAccounts,
    [
        'account_10_root',
        'account_20_root',
        'account_20_other',
        'account_20_foreman',
        'account_62_root',
        'account_76_fines',
        'account_76_sales',
        'account_76_debts',
        'account_90_1_root',
        'account_90_1_disciplinary_deductions',
        'account_90_1_fine_based_deductions',
        'account_90_2_root',
        'account_90_3_root',
        'account_90_9_root'
    ]
)
_register(models.CustomerOrder, ['timesheet'])
_register(models.CustomerOrderHardNotification, ['customer_order'])
_register(models.CustomerOrderSoftNotification, ['customer_order'])
_register(models.CustomerRepr, ['customer_id'])
_register(
    models.CustomerService,
    [
        'customer',
        'service',
        'account_20_root',
        'account_20_general_work',
        'account_20_selfemployed_work',
        'account_20_general_taxes',
        'account_20_selfemployed_taxes',
        'account_76',
        'account_90_1'
    ]
)
_register(models.DevelopmentManager, ['worker', 'customer'])
_register(models.MaintenanceManager, ['worker', 'customer'])
admin.site.register(models.DocumentWithAccountablePerson)
_register(models.AccountableDocumentOperation, ['document', 'operation'])
_register(models.NoticeOfArrival, ['contract'])
_register(models.NoticeOfContract, ['contract'])
_register(models.NoticeOfTermination, ['contract'])
admin.site.register(models.Pair)
admin.site.register(models.IndustrialCostType)
_register(models.AdministrationCostType, ['account_26', 'account_90_2', 'account_90_9'])
_register(models.CustomerIndustrialAccounts, ['account_20', 'account_90_1'])
admin.site.register(models.MaterialType)
_register(models.Customer10SubAccount, ['account_10'])
_register(models.PeriodCloseDocument, ['author'])
admin.site.register(models.Photo)
admin.site.register(models.Position)
admin.site.register(models.PhotoLoadSession)
_register(models.PhotoSessionCitizenship, ['session'])
_register(models.PhotoSessionRejectedPhotos, ['session'])
_register(models.RecruitmentOrder, ['customer_order'])
_register(models.Rko, ['worker'])
_register(models.RkoOperation, ['rko', 'operation'])
admin.site.register(models.Service)
_register(models.SheetPeriodClose, ['close_document', 'close_operation'])
_register(models.TimeSheet, ['foreman'])
_register(models.TimesheetCreationTimepoint, ['timesheet'])
admin.site.register(models.TimesheetProcessingTimepoint)
admin.site.register(models.TimesheetSoftNotification)
_register(models.WorkerDeduction, ['operation'])
_register(models.SalaryPayment, ['operation'])
_register(models.TurnoutService, ['turnout'])
admin.site.register(models.Worker, WorkerAdmin)
_register(models.BannedWorker, ['worker'])
_register(models.MobileAppWorker, ['worker'])
_register(models.WorkerUser, ['worker', 'user'])
_register(models.WorkerComments, ['worker'])
_register(models.WorkerMedicalCard, ['worker'])
_register(models.WorkerOperatingAccount, ['worker', 'account'])
_register(models.WorkerPassport, ['workers_id'])
_register(models.WorkerPatent, ['workers_id'])
_register(models.WorkerRegistration, ['workers_id'])
admin.site.register(models.WorkerTurnout, WorkerTurnoutsAdmin)
_register(models.WorkerMigrationCard, ['worker'])
_register(models.WorkerSelfEmploymentData, ['worker'])
_register(models.WorkersForOrder, ['order', 'worker'])
admin.site.register(models.WorkerRating)

admin.site.register(models.PaysheetParams)
admin.site.register(models.RegistryNum)
_register(models.PaysheetRegistry, ['paysheet', 'registry_num'])
_register(models.TestRegistry, ['registry_num'])
_register(models.WorkerReceipt, ['author', 'worker'])
_register(models.WorkerReceiptRegistryNum, ['worker_receipt', 'registry_num'])
_register(models.WorkerReceiptPaysheetEntry, ['worker_receipt', 'paysheet_entry'])

admin.site.register(models.Prepayment)
_register(models.WorkerPrepayment, ['prepayment', 'worker', 'operation'])
_register(models.TalkBankClient, ['worker'])

admin.site.register(models.TalkBankWebhookRequest)
_register(models.PaysheetEntryTalkBankIncomeRegistration, ['author', 'paysheet', 'worker'])
_register(models.PaysheetEntryTalkBankPayment, ['paysheet_entry'])
_register(models.PaysheetEntryTalkBankPaymentAttempt, ['paysheet', 'worker'])
_register(models.PaysheetTalkBankPaymentStatus, ['paysheet'])

admin.site.register(metro_models.City)
admin.site.register(metro_models.MetroBranch)
admin.site.register(metro_models.MetroStation)

admin.site.register(models.deposit.CustomerDepositAmount)
_register(models.deposit.WorkerDeposit, ['worker', 'account'])


admin.site.register(models.HomePage)

admin.site.register(models.Contractor)
_register(models.ContractorProxy, ['worker'])
admin.site.register(models.PreferredContractor)

admin.site.register(paysheet_v2.Paysheet_v2)
_register(paysheet_v2.Paysheet_v2Entry, ['paysheet', 'worker', 'operation'])
_register(paysheet_v2.Paysheet_v2EntryOperation, ['entry', 'operation'])

admin.site.register(models.fine_utils.OperationsPack)
_register(models.fine_utils.OperationsPackItem, ['pack', 'operation'])

admin.site.register(vkusvill.PerformanceFile)
admin.site.register(vkusvill.ErrorsFile)

# reconciliation.py
admin.site.register(models.Reconciliation)
_register(models.ReconciliationConfirmation, ['author', 'reconciliation'])
_register(models.ReconciliationPaymentOperation, ['reconciliation', 'operation'])

# turnout_calculators.py
admin.site.register(models.AmountCalculator)
_register(models.ServiceCalculator, ['customer_service', 'calculator'])
admin.site.register(models.PositionCalculator)
admin.site.register(models.BoxPrice)
admin.site.register(models.BoxType)
admin.site.register(models.CalculatorBoxes)
admin.site.register(models.CalculatorForeman)
admin.site.register(models.CalculatorForemanOutputSum)
admin.site.register(models.CalculatorHourly)
admin.site.register(models.CalculatorInterval)
admin.site.register(models.CalculatorOutput)
admin.site.register(models.CalculatorTurnouts)
admin.site.register(models.SingleTurnoutCalculator)
_register(models.TurnoutOutput, ['turnout'])

# turnout_operations.py
_register(turnout_operations.CustomerFine, ['operation', 'turnout'])
_register(turnout_operations.TurnoutAdjustingOperation, ['turnout', 'operation'])
_register(turnout_operations.TurnoutBonus, ['turnout', 'operation'])
_register(turnout_operations.TurnoutCustomerOperation, ['turnout', 'operation'])
_register(turnout_operations.TurnoutDeduction, ['turnout', 'operation'])
_register(turnout_operations.TurnoutOperationIsPayed, ['turnout', 'operation'])
_register(turnout_operations.TurnoutOperationToPay, ['turnout', 'operation'])
_register(turnout_operations.TurnoutTaxOperation, ['turnout', 'operation'])

# hostel.py
_register(hostel.HostelBonus, ['worker'])
_register(hostel.HostelBonusOperation, ['turnout', 'operation'])

# itella.py
_register(itella.K2KAlias, ['worker'])
admin.site.register(itella.K2KSheet)

# legal_entity.py
admin.site.register(legal_entity.LegalEntity)
_register(
    legal_entity.LegalEntityCommonAccounts,
    [
        'account_26_68_01',
        'account_26_69_1_1',
        'account_26_69_1_2',
        'account_26_69_2',
        'account_26_69_3',
        'account_51_root',
        'account_68_01',
        'account_69_1_1',
        'account_69_1_2',
        'account_69_2',
        'account_69_3',
    ]
)
_register(
    legal_entity.LegalEntityGeneralTaxSystemAccounts,
    [
        'account_19',
        'account_26_68_04_2',
        'account_68_02',
        'account_68_04_2',
    ]
)
_register(
    legal_entity.LegalEntitySimpleTaxSystemAccounts,
    [
        'account_26_68_12',
        'account_26_68_14',
        'account_26_69_06_3',
        'account_26_69_06_5_1',
        'account_26_69_06_5_2',
        'account_68_12',
        'account_68_14',
        'account_69_06_3',
        'account_69_06_5_1',
        'account_69_06_5_2',
    ]
)

# expenses.py
_register(expenses.Expense, ['expense_debit'])
_register(expenses.ExpenseConfirmation, ['expense'])
_register(expenses.ExpenseOperation, ['expense', 'operation'])
_register(expenses.ExpensePaymentOperation, ['expense', 'operation'])
_register(expenses.ExpenseRejection, ['expense'])
_register(expenses.Provider, ['account_60', 'account_60_fines'])
_register(expenses.ProviderFine, ['operation'])

# partners.py
admin.site.register(partners.MobileAppPartner)

# payment_schedule.py
_register(payment_schedule.PlannedOperation, ['debet', 'credit'])

# delivery.py
admin.site.register(delivery.RequestsFile)
admin.site.register(delivery.DeliveryRequest, DeliveryRequestAdmin)
_register(
    delivery.DeliveryRequestConfirmation,
    ['author', 'request'],
    readonly_ids=['timestamp']
)
_register(delivery.DeliveryRequestStatusChange, ['author', 'request'])
_register(delivery.DeliveryRequestTimepointChange, ['author', 'request'])
_register(delivery.DeliveryRequestOperator, ['operator', 'request'])
_register(delivery.DeliveryItem, ['request'])
_register(delivery.NormalizedAddress, ['location'])
_register(delivery.GoogleMapsAddress, ['location'])
_register(delivery.AssignedWorker, ['request', 'worker'])
_register(delivery.AssignedWorkerAuthor, ['author', 'assigned_worker'])
_register(delivery.ArrivalLocation, ['worker', 'location'])
_register(delivery.TurnoutPhoto, ['location', 'photo'])
_register(delivery.PhotoRejectionComment, ['photo'])
_register(
    delivery.AssignedWorkerTurnout,
    ['assigned_worker', 'turnout'],
    readonly_ids=['timestamp']
)
_register(delivery.RequestWorker, ['author', 'request', 'worker'])
_register(delivery.WorkerConfirmation, ['author', 'requestworker'])
_register(delivery.WorkerRejection, ['author', 'requestworker'])
_register(delivery.RequestWorkerTurnout, ['requestworker', 'workerturnout'])
_register(delivery.ItemWorker, ['author', 'item', 'requestworker'])
_register(delivery.ItemWorkerRejection, ['author', 'itemworker'])
_register(delivery.ItemWorkerStart, ['author', 'itemworker', 'location'])
_register(delivery.ItemWorkerStartConfirmation, ['author', 'itemworkerstart'])
_register(delivery.ItemWorkerFinish, ['author', 'itemworker', 'location'])
_register(delivery.ItemWorkerFinishConfirmation, ['author', 'itemworkerfinish'])
_register(delivery.DeliveryService, ['service'])
_register(delivery.DriverSms, ['request'])
_register(delivery.SmsPhone, ['sms'])
admin.site.register(delivery.ZoneGroup)
_register(delivery.WeekendRest, ['zone'])
_register(delivery.DeliveryZone, ['group'])
_register(delivery.LocationZoneGroup, ['location', 'zone_group'])
_register(delivery.OperatorZoneGroup, ['operator', 'zone_group'])
_register(delivery.WorkerZone, ['worker', 'zone'])
_register(delivery.TurnoutDiscrepancyCheck, ['turnout'])
_register(delivery.RequestsAutoMergeEnabled, ['location'])
_register(delivery.DailyReconciliation, ['location'])
_register(delivery.DailyReconciliationNotification, ['author', 'reconciliation', 'recipient'])
_register(delivery.DailyReconciliationConfirmation, ['author', 'reconciliation'])

_register(delivery.DeliveryCustomerLegalEntity, ['customer'])

admin.site.register(delivery.Location)
_register(delivery.DeliveryWorkerFCMToken, ['user'], readonly_ids=['timestamp'])
_register(delivery.MobileAppStatus, ['user', 'location'], readonly_ids=['timestamp'])
_register(delivery.OnlineStatusMark, ['user'], readonly_ids=['timestamp'])

_register(delivery.DeliveryInvoice, ['author', 'customer'], readonly_ids=['timestamp'])

_register(delivery.ImportVisitTimestamp, ['customer'], readonly_ids=['timestamp'])
_register(delivery.ImportProcessedTimestamp, ['customer'], readonly_ids=['timestamp'])


# auth.py
_register(auth.OneOffCode, ['user'])
_register(auth.UserPhone, ['user'])
_register(auth.ResetPasswordRequest, ['user'])
admin.site.register(auth.UserRegistrationInfo)


# chat.py
_register(chat.WorkerTelegramUserId, ['worker'])
_register(chat.WorkerRocketchatVisitor, ['worker'])
