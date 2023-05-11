# -*- coding: utf-8 -*-
import datetime
from datetime import datetime

from dal import autocomplete

from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.contenttypes.models import ContentType

from django.db.models import (
    Exists,
    OuterRef,
    Q,
)
from django.http import JsonResponse

from . import models

from .models import (
    AccountablePerson,
    BankService,
    BankServiceParams,
    Country,
    Customer,
    DevelopmentManager,
    DevelopmentManagerPosition,
    MaintenanceManager,
    MaintenanceManagerPosition,
    Metro,
    Position,
    Prepayment,
    Worker,
    WorkerTurnout,
)
from finance.models import Account as FinanceAccount

DATE_FORMAT = '%d.%m.%Y'


class AccountablePersonAutocomplete(LoginRequiredMixin, autocomplete.Select2QuerySetView):
    def get_queryset(self):
        workers = Worker.objects.filter(
            accountableperson__isnull=False
        )
        if self.q:
            workers = workers.filter_by_text(self.q)
        return AccountablePerson.objects.filter(
            worker__in=workers
        ).order_by('worker__last_name', 'worker__name', 'worker__patronymic')


class WorkerAutocomplete(LoginRequiredMixin, autocomplete.Select2QuerySetView):
    def get_queryset(self):
        workers = Worker.objects.filter_rf_or_mk()
        if self.q:
            workers = workers.filter_by_text(self.q)
        return workers


class AllWorkersAutocomplete(LoginRequiredMixin, autocomplete.Select2QuerySetView):
    def get_queryset(self):
        workers = Worker.objects.all()
        if self.q:
            workers = workers.filter_by_text(self.q)
        return workers


class WorkerWithContractAutocomplete(LoginRequiredMixin, autocomplete.Select2QuerySetView):
    def get_queryset(self):
        workers = Worker.objects.filter_with_contract().order_by('-pk')
        if self.q:
            workers = workers.filter_by_text(self.q)
        return workers


def workers_for_customer(view):
    workers = models.Worker.objects.all()
    
    if view.q:
        workers = workers.filter_by_text(view.q)

    customer_pk = view.forwarded.get('customer')
    if customer_pk:
        workers = workers.filter_by_turnout_customer(customer_pk)

    return workers


class WorkerWithCustomerAutocomplete(LoginRequiredMixin, autocomplete.Select2QuerySetView):
    def get_queryset(self):
        return workers_for_customer(self)


class WorkerWithoutContractAutocomplete(LoginRequiredMixin, autocomplete.Select2QuerySetView):

    def get_queryset(self):
        tomorrow = datetime.date.today() + datetime.timedelta(days=1)
        worker_qs = Worker.objects.filter(
            contract__isnull=True
        ).with_has_photo(
        ).exclude(
            Q(workerregistration__r_date_of_issue__isnull=True) |
            Q(has_photo=False)
        ).filter_rf_or_mk(tomorrow)
        if self.q:
            worker_qs = worker_qs.filter_by_text(self.q)
        return worker_qs


class WorkerByPrepaymentAutocomplete(LoginRequiredMixin, autocomplete.Select2QuerySetView):
    def get_queryset(self):
        # Если выбран клиент
        prepayment = Prepayment.objects.get(pk=self.kwargs['pk'])

        turnouts = WorkerTurnout.objects.filter(
            timesheet__sheet_date__lte=prepayment.created_at,
            timesheet__customer=prepayment.customer,
            turnoutoperationtopay__operation__paysheet_entries__isnull=True,
        )
        include_workers = set(turnouts.order_by().values_list('worker', flat=True).distinct('worker_id'))
        workers = Worker.objects.filter(pk__in=include_workers)
        if self.q:
            workers = workers.filter_by_text(self.q)
        return workers


class ForemanAutocomplete(LoginRequiredMixin, autocomplete.Select2QuerySetView):
    def get_queryset(self):
        workers = Worker.objects.filter_rf_or_mk(
        ).filter(
            Q(position__name='Бригадир') |
            Q(position__name='Стажер')
        )
        if self.q:
            workers = workers.filter_by_text(self.q)
        return workers


class CustomerAutocomplete(LoginRequiredMixin, autocomplete.Select2QuerySetView):
    def get_queryset(self):
        customers = Customer.objects.exclude(is_actual=False).order_by('cust_name')
        if self.q:
            customers = customers.filter(
                cust_name__icontains=self.q
            )
        return customers


class CustomerReprAutocomplete(LoginRequiredMixin, autocomplete.Select2QuerySetView):
    def get_queryset(self):
        customer_pk = self.forwarded.get('customer')
        if customer_pk:
            representers = models.CustomerRepr.objects.filter(
                customer_id__pk=customer_pk
            )
            if self.q:
                representers = representers.filter(
                    Q(repr_last_name__icontains=self.q) |
                    Q(repr_name__icontains=self.q) |
                    Q(repr_patronymic__icontains=self.q)
                )
            return representers
        return models.CustomerRepr.objects.none()


class CustomerLocationAutocomplete(LoginRequiredMixin, autocomplete.Select2QuerySetView):
    def get_queryset(self):
        customer_pk = self.forwarded.get('customer', None)
        if customer_pk:
            locations = models.CustomerLocation.objects.filter(
                customer_id__pk=customer_pk
            )
            if self.q:
                locations = locations.filter(location_name__icontains=self.q)
            return locations.order_by('location_name')
        return models.CustomerLocation.objects.none()

    def get_result_label(self, result):
        return '{}/{}'.format(
            result.customer_id.cust_name,
            result.location_name
        )


class ActualCustomerLocationAutocomplete(CustomerLocationAutocomplete):
    def get_queryset(self):
        return super(ActualCustomerLocationAutocomplete, self).get_queryset().filter(
            is_actual=True
        )


class ServiceAutocomplete(LoginRequiredMixin, autocomplete.Select2QuerySetView):
    def get_queryset(self):
        services = models.Service.objects.all()
        if self.q:
            services = services.filter(name__icontains=self.q)
        return services


class CustomerServiceAutocomplete(LoginRequiredMixin, autocomplete.Select2QuerySetView):
    def get_queryset(self):
        customer_pk = self.forwarded.get('customer', None)
        if customer_pk:
            services = models.CustomerService.objects.filter(
                active=True,
                customer__pk=customer_pk
            )
            if self.q:
                services = services.filter(
                    Q(customer__cust_name__icontains=self.q) |
                    Q(service__name__icontains=self.q)
                )
            return services


class CountryAutocomplete(LoginRequiredMixin, autocomplete.Select2QuerySetView):
    def get_queryset(self):
        country_qs = Country.objects.all()
        if self.q:
            country_qs = country_qs.filter(
                name__icontains=self.q
            )
        return country_qs.order_by('name')


class PositionAutocomplete(LoginRequiredMixin, autocomplete.Select2QuerySetView):
    def get_queryset(self):
        position_qs = Position.objects.all()
        if self.q:
            position_qs = position_qs.filter(
                name__icontains=self.q
            )
        return position_qs.order_by('name')


class PositionDMinusAutocomplete(PositionAutocomplete):
    def get_queryset(self):
        return super(PositionDMinusAutocomplete, self).get_queryset().filter(
            developmentmanagerposition__isnull=True
        )


class PositionMMinusAutocomplete(PositionAutocomplete):
    def get_queryset(self):
        return super(PositionMMinusAutocomplete, self).get_queryset().filter(
            maintenancemanagerposition__isnull=True
        )


class MetroAutocomplete(LoginRequiredMixin, autocomplete.Select2QuerySetView):
    def get_queryset(self):
        metro_qs = Metro.objects.all()
        if self.q:
            metro_qs = metro_qs.filter(name__icontains=self.q)
        return metro_qs.order_by('name')


class MManagerPositionAutocomplete(LoginRequiredMixin, autocomplete.Select2QuerySetView):
    manager_position_model = MaintenanceManagerPosition

    def get_queryset(self):
        worker_qs = Worker.objects.annotate(
            is_manager_position=Exists(
                self.manager_position_model.objects.filter(
                    position=OuterRef('position')
                )
            )
        ).filter(
            is_manager_position=True
        )
        if self.q:
            worker_qs = worker_qs.filter_by_text(self.q)
        return worker_qs


class DManagerPositionAutocomplete(MManagerPositionAutocomplete):
    manager_position_model = DevelopmentManagerPosition


class MaintenanceManagerAutocomplete(LoginRequiredMixin, autocomplete.Select2QuerySetView):
    manager_model = MaintenanceManager

    def get_queryset(self):
        if self.request.user.groups.filter(name='Менеджеры').exists():
            workers = Worker.objects.filter(
                workeruser__user=self.request.user
            )
        else:
            managers = self.manager_model.objects.filter(worker=OuterRef('pk'))
            # Если выбран клиент
            customer_id = self.request.GET.get('customer_id')
            if customer_id:
                managers = managers.filter(customer_id=customer_id)
            workers = Worker.objects.annotate(
                is_manager=Exists(
                    managers
                )
            ).filter(is_manager=True)
        if self.q:
            workers = workers.filter_by_text(self.q)
        return workers


class DevelopmentManagerAutocomplete(MaintenanceManagerAutocomplete):
    manager_model = DevelopmentManager


class FinanceAccountAutocomplete(LoginRequiredMixin, autocomplete.Select2QuerySetView):
    def get_queryset(self):
        accounts_set = FinanceAccount.objects.order_by('full_name')
        if self.q:
            accounts_set = accounts_set.filter(full_name__icontains=self.q)
        return accounts_set

    def get_result_label(self, result):
        return result.full_name


def FinanceAccountForPaysheetAutocomplete(request):
    accounts = []
    if request.user.is_authenticated:
        account_names = ['50. ', '51. ', '71. ']
        for name in account_names:
            account = FinanceAccount.objects.filter(
                name__startswith=name
            ).first()
            for descendant in account.descendants():
                if not descendant.children.all():
                    accounts.append({'id': descendant.pk,
                                     'text': str(descendant)})

    return JsonResponse({'results': accounts}, safe=False)


class BankServiceAutocomplete(LoginRequiredMixin, autocomplete.Select2QuerySetView):
    def get_queryset(self):
        bank_services = BankService.objects.order_by('type')
        if self.q:
            bank_services = bank_services.filter(
                type__icontains=self.q
            )
        bank_id = self.request.GET.get('bank_id')
        # Если выбран банк
        if bank_id:
            bs_params = BankServiceParams.objects.filter(bank_id=bank_id, service=OuterRef('pk'))
            bank_services = bank_services.annotate(
                has_params=Exists(bs_params)
            ).filter(has_params=False)
        return bank_services


class VacantCustomerLocationAutocomplete(LoginRequiredMixin, autocomplete.Select2QuerySetView):
    def get_queryset(self):
        if not self.request.user.is_authenticated:
            return models.CustomerLocation.objects.none()
        queryset = models.CustomerLocation.objects.all()

        if self.q:
            queryset = queryset.filter(
                (
                    Q(location_name__icontains=self.q) |
                    Q(customer_id__cust_name__icontains=self.q)
                )
            )
        queryset = queryset.select_related('customer_id')
        queryset = queryset.order_by('customer_id__cust_name', 'location_name')
        return queryset

    def get_result_label(self, item):
        return '{} - {}'.format(item.customer_id.cust_name, item.location_name)


class LegalEntityAutocomplete(LoginRequiredMixin, autocomplete.Select2QuerySetView):
    def get_queryset(self):
        queryset = models.LegalEntity.objects.all()

        if self.q:
            queryset = queryset.filter(short_name__icontains=self.q)

        return queryset


# Todo: to manager
def administration_cost_types(view):
    cost_types = models.AdministrationCostType.objects.all().order_by('name')

    if view.q:
        cost_types = cost_types.filter(name__icontains=view.q)

    return cost_types


class AdministrationCostTypeAutocomplete(LoginRequiredMixin, autocomplete.Select2QuerySetView):
    def get_queryset(self):
        return administration_cost_types(self)


# Todo: to manager
def industrial_cost_types(view):
    cost_types = models.IndustrialCostType.objects.all().order_by('name')

    if view.q:
        cost_types = cost_types.filter(name__icontains=view.q)

    return cost_types


class IndustrialCostTypeAutocomplete(LoginRequiredMixin, autocomplete.Select2QuerySetView):
    def get_queryset(self):
        return industrial_cost_types(self)


# Todo: to manager
def providers(view):
    queryset = models.Provider.objects.all().order_by('name')

    if view.q:
        queryset = queryset.filter(name__icontains=view.q)

    return queryset


class ProviderAutocomplete(LoginRequiredMixin, autocomplete.Select2QuerySetView):
    def get_queryset(self):
        return providers(self)


class ExpenseAutocomplete(LoginRequiredMixin, autocomplete.Select2QuerySetView):
    def get_queryset(self):
        queryset = models.Expense.objects.filter(
            expenseconfirmation__isnull=False,
            expensepaymentoperation__isnull=True
        ).order_by(
            'pk'
        ).select_related(
            'provider',
        )

        expense_filter = self.forwarded.get('expense_filter')
        if expense_filter == 'unassigned':
            queryset = queryset.annotate(
                assigned=Exists(
                    models.DocumentWithAccountablePerson.objects.filter(
                        content_type=ContentType.objects.get_for_model(models.Expense),
                        object_id=OuterRef('pk')
                    )
                )
            ).filter(
                assigned=False
            )

        if self.q:
            queryset = queryset.filter(
                Q(provider__name__icontains=self.q)
            )

        return queryset

    def get_result_label(self, item):
        return 'Расход №{}. {}, {}р. с {} по {}.'.format(
            item.pk,
            item.provider.name,
            item.amount,
            item.first_day,
            item.last_day
        )


# Warning: это для вычетов, так что фильтрует специфично
def expenses_by_customer(view):
    # нас интересуют только расходы по материалам
    queryset = models.Expense.objects.filter(
        expense_debit__account_10_subaccounts__isnull=False
    ).order_by(
        'pk'
    ).select_related(
        'provider'
    )

    customer = view.forwarded.get('customer')
    if customer:
        queryset = queryset.filter(
            expense_debit__account_10_subaccounts__customer__pk=customer
        )

    return queryset


class ExpenseByCustomerAutocomplete(LoginRequiredMixin, autocomplete.Select2QuerySetView):
    def get_queryset(self):
        return expenses_by_customer(self)

    def get_result_label(self, item):
        return 'Расход №{}, {}, {}р. {}'.format(
            item.pk,
            item.provider.name,
            item.amount,
            item.comment
        )


# Todo: to manager
def materials(view):
    queryset = models.MaterialType.objects.all().order_by('pk')
    if view.q:
        queryset = queryset.filter(name__icontains=view.q)

    return queryset


class MaterialAutocomplete(LoginRequiredMixin, autocomplete.Select2QuerySetView):
    def get_queryset(self):
        return materials(self)

    def get_result_label(self, item):
        return item.name
