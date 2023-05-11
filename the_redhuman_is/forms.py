import collections
import datetime
from pathlib import Path

from bootstrap_daterangepicker.fields import DateField
from crispy_forms.helper import FormHelper
from crispy_forms.layout import (
    Field,
    Layout,
    Row,
)
from dal import autocomplete
from django import forms
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.db.models import Q
from django.forms import widgets
from django.utils import timezone
from django.utils.safestring import mark_safe

import finance
from the_redhuman_is import models
from the_redhuman_is.models import (
    AdministrationCostType,
    Bank,
    BankService,
    BankServiceParams,
    Contract,
    Country,
    Creditor,
    CustComments,
    Customer,
    CustomerLocation,
    CustomerOrder,
    CustomerRepr,
    DevelopmentManager,
    DevelopmentManagerPosition,
    IndustrialCostType,
    MaintenanceManager,
    MaintenanceManagerPosition,
    Metro,
    NoticeOfContract,
    NoticeOfTermination,
    Photo,
    Position,
    TimeSheet,
    Worker,
    WorkerComments,
    WorkerPassport,
    WorkerPatent,
    WorkerRegistration,
    WorkerTurnout,
    ZoneGroup,
    add_photo,
)
from the_redhuman_is.models.reconciliation import ReconciliationInvoice
from the_redhuman_is.views.customer_summary import (
    CITIZENSHIP_TYPES,
    CUSTOMER_FETCH_TYPES,
    LAYOUT_TYPES,
)
from utils import DATE_FORMAT
from utils.locale import DATEPICKER_LOCALE
from utils.forms import (
    SubmitNoValue,
    DatePickerWidget,
)


def _rename_field(fields, old_name, new_name):
    fields[new_name] = fields[old_name]
    del fields[old_name]


# Todo: replace with datepicker field?
def _dateinput_field(label, placeholder='дд.мм.гггг', initial=None):
    attrs = {
        'size': '10',
        'placeholder': placeholder,
    }
    return forms.DateField(
        label=label,
        initial=initial,
        input_formats=[DATE_FORMAT],
        required=False,
        widget=forms.DateInput(
            attrs=attrs,
            format=DATE_FORMAT
        )
    )


def _datepicker_field(label, placeholder='дд.мм.гггг', initial=None):
    return _dateinput_field(label, placeholder, initial)

    # DatePickerInput is broken somehow :(

#    return DateField(
#        label=label,
#        initial=initial,
#        widget=DatePickerInput(
#            format=DATE_FORMAT,
#            attrs={
#                'placeholder': placeholder,
#                'class': 'form-control form-control-sm',
#                'style': 'max-width: 100px;',
#            },
#            options={
#                'locale': 'ru-RU'
#            }
#        ),
#        required=False,
#    )


class WorkerForm(forms.ModelForm):
    birth_date = _datepicker_field('Дата рождения')
    m_date_of_issue = _datepicker_field('МК, дата выдачи')
    m_date_of_exp = _datepicker_field('МК, дата окончания')

    place_of_birth = forms.ModelChoiceField(
        label='Место рождения',
        queryset=Country.objects.all(),
        widget=autocomplete.ModelSelect2(
            url='the_redhuman_is:country-autocomplete'
        )
    )
    citizenship = forms.ModelChoiceField(
        label='Гражданство',
        queryset=Country.objects.all(),
        widget=autocomplete.ModelSelect2(
            url='the_redhuman_is:country-autocomplete'
        )
    )
    position = forms.ModelChoiceField(
        label='Должность',
        queryset=Position.objects.all(),
        widget=autocomplete.ModelSelect2(
            url='the_redhuman_is:position-autocomplete'
        )
    )
    photos = forms.ImageField(
        label='Загрузить фото',
        widget=widgets.ClearableFileInput(attrs={'multiple': True}),
        required=False,
    )

    class Meta:
        model = Worker
        fields = (
            'last_name',
            'name',
            'patronymic',
            'sex',
            'tel_number',
            'birth_date',
            'place_of_birth',
            'mig_series',
            'mig_number',
            'm_date_of_issue',
            'm_date_of_exp',
            'citizenship',
            'contract_type',
            'position',
        )

    def save(self, commit=True):
        worker = super(WorkerForm, self).save(commit=False)
        worker.input_date = timezone.now()
        if commit:
            worker = super(WorkerForm, self).save()
            if self.files:
                for file in self.files.getlist('photos', []):
                    add_photo(worker, file)
        return worker


class ImageChoiceField(forms.ModelMultipleChoiceField):
    def label_from_instance(self, obj):
        return mark_safe(f'<a href="{obj.image.url}">{Path(obj.image.url).name}</a>')

    def clean(self, value):
        value = [item for item in value if item]
        return super(ImageChoiceField, self).clean(value)


def _worker_photo_form_queryset():
    try:
        return Photo.objects.filter(
            content_type=ContentType.objects.get_for_model(Worker),
        )
    except:
        return Photo.objects.none()


class WorkerPhotoForm(forms.Form):
    photos = ImageChoiceField(
        label='Удалить загруженные фото:',
        queryset=_worker_photo_form_queryset(),
        widget=forms.CheckboxSelectMultiple,
        required=False,
        initial=False,
    )

    def __init__(self, *args, **kwargs):
        worker_pk = kwargs.pop('worker_pk', None)
        super(WorkerPhotoForm, self).__init__(*args, **kwargs)
        qs = self.fields['photos'].queryset
        if worker_pk is None:
            qs = qs.none()
        else:
            qs = qs.filter(object_id=worker_pk)
        self.fields['photos'].queryset = qs


class WorkerFormWOutImages(WorkerForm):
    class Meta(WorkerForm.Meta):
        fields = (
            'last_name',
            'name',
            'patronymic',
            'sex',
            'tel_number',
            'birth_date',
            'place_of_birth',
            'mig_series',
            'mig_number',
            'm_date_of_issue',
            'm_date_of_exp',
            'citizenship',
            'contract_type',
            'position',
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['citizenship'].required = False
        self.fields['place_of_birth'].required = False
        self.fields['position'].required = False
        self.helper = FormHelper()
        self.helper.form_class = 'form-horizontal'
        self.helper.form_tag = False
        self.helper.label_class = 'col-lg-4'
        self.helper.field_class = 'col-lg-8'

    def clean(self):
        required = [
            'last_name',
            'name',
            'sex',
            'birth_date',
            'place_of_birth',
            'citizenship',
            'contract_type',
            'position',
        ]
        cleaned_data = super().clean()
        citizenship = cleaned_data.get("citizenship")
        if citizenship:
            if citizenship.name not in ['РФ', 'Белоруссия']:
                required.extend(['mig_series', 'mig_number', 'm_date_of_issue',
                                'm_date_of_exp'])

        for item in required:
            if not cleaned_data.get(item):
                self.add_error(item, 'Поле обязательно для заполнения')


class ForHRWorkerForm(forms.ModelForm):
    class Meta:
        model = Worker
        fields = (
            'metro',
            'status',
            'speaks_russian'
        )
        widgets = {'metro': autocomplete.Select2(url='the_redhuman_is:metro-autocomplete-from-list')}


class WorkerCommentsForm(forms.ModelForm):

    class Meta:
        model = WorkerComments
        fields = (
            'author',
            'text',
        )


class WorkerContractForm(forms.ModelForm):
    c_worker_id = forms.IntegerField(required=False, widget=forms.HiddenInput())

    class Meta:
        model = Contract
        fields = (
            'c_worker_id',
            'cont_type',
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_class = 'form-horizontal'
        self.helper.form_tag = False
        self.helper.label_class = 'col-lg-4'
        self.helper.field_class = 'col-lg-8'


class WorkerSearchForm(forms.Form):
    worker = forms.ModelChoiceField(
        queryset=Worker.objects.all(),
        label='',
        widget=autocomplete.ListSelect2(
            url='the_redhuman_is:worker-autocomplete',
            attrs={'class': 'form-control'}
        ),
        required=False
    )

    def __init__(self, field_name='worker', *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_tag = False
        if field_name != 'worker':
            self.field_name = field_name
            _rename_field(self.fields, 'worker', field_name)

    def set_autocomplete_url(self, url):
        self.fields['worker'].widget.url = url

    def worker_field(self):
        return self[self.field_name]


def all_worker_search_form():
    form = WorkerSearchForm()
    form.set_autocomplete_url('the_redhuman_is:all-worker-autocomplete')
    return form


WorkerSearchFormSet = forms.formset_factory(WorkerSearchForm)


class WorkerWithContractSearchForm(forms.Form):
    worker = forms.ModelChoiceField(
        queryset=Worker.objects.all(),
        label='',
        widget=autocomplete.ListSelect2(
            url='the_redhuman_is:worker_with_contract_autocomplete',
            attrs={'class': 'form-control'}
        ),
        required=False
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_tag = False


WorkerWithContractSearchFormSet = forms.formset_factory(WorkerWithContractSearchForm)


def _to_add_contract_form_queryset():
    try:
        return Worker.objects.filter_to_deal_with()
    except:
        return Worker.objects.none()


class ToAddContractForm(forms.Form):
    workers = forms.ModelMultipleChoiceField(
        queryset=_to_add_contract_form_queryset(),
        label='Выбрать рабочих',
        widget=autocomplete.Select2Multiple(
            url='the_redhuman_is:worker_without_contract_autocomplete'
        )
    )


class WorkerPassportForm(forms.ModelForm):
    worker_id = forms.IntegerField(required=False, widget=forms.HiddenInput())
    date_of_issue = forms.DateField(
        label='Дата выдачи',
        input_formats=[DATE_FORMAT],
        required=False,
        widget=forms.DateInput(
            attrs={'placeholder': 'дд.мм.гггг'},
            format=DATE_FORMAT
        )
    )
    date_of_exp = forms.DateField(
        label='Дата окончания',
        input_formats=[DATE_FORMAT],
        required=False,
        widget=forms.DateInput(
            attrs={'placeholder': 'дд.мм.гггг'},
            format=DATE_FORMAT
        )
    )

    class Meta:
        model = WorkerPassport
        fields = (
            'worker_id',
            'passport_type',
            'passport_series',
            'another_passport_number',
            'date_of_issue',
            'date_of_exp',
            'issued_by',
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_class = 'form-horizontal'
        self.helper.form_tag = False
        self.helper.label_class = 'col-lg-4'
        self.helper.field_class = 'col-lg-8'

    def clean(self):
        cleaned_data = super().clean()
        required = [
            'passport_type',
            'another_passport_number',
            'date_of_issue',
            'issued_by',
        ]
        for item in required:
            if not cleaned_data.get(item):
                self.add_error(item, 'Поле обязательно для заполнения')


class WorkerRegistrationForm(forms.ModelForm):
    worker_id = forms.IntegerField(required=False, widget=forms.HiddenInput())
    r_date_of_issue = forms.DateField(
        label='Дата выдачи',
        input_formats=[DATE_FORMAT],
        required=False,
        widget=forms.DateInput(
            attrs={'placeholder': 'дд.мм.гггг'},
            format=DATE_FORMAT
        )
    )

    class Meta:
        model = WorkerRegistration
        fields = (
            'worker_id',
            'r_date_of_issue',
            'city',
            'street',
            'house_number',
            'building_number',
            'appt_number',
        )


class WorkerRegistrationWithCitizenshipForm(WorkerRegistrationForm):
    citizenship = forms.IntegerField(required=False, widget=forms.HiddenInput())

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.helper = FormHelper()
        self.helper.form_class = 'form-horizontal'
        self.helper.form_tag = False
        self.helper.label_class = 'col-lg-4'
        self.helper.field_class = 'col-lg-8'

        self.fields['city'].required = False
        self.fields['street'].required = False

    def clean(self):
        cleaned_data = super().clean()
        required = [
            'r_date_of_issue',
            'city',
            'street',
            'house_number',
        ]
        for item in required:
            if not cleaned_data.get(item):
                self.add_error(item, 'Поле обязательно для заполнения')

    def has_changed(self):
        changed_data = self.changed_data
        changed_data.remove('citizenship')
        return bool(changed_data)


class WorkerPatentForm(forms.ModelForm):
    worker_id = forms.IntegerField(required=False, widget=forms.HiddenInput())
    date_of_issue = forms.DateField(
        label='Дата выдачи',
        input_formats=[DATE_FORMAT],
        required=False,
        widget=forms.TextInput(attrs={'placeholder': 'дд.мм.гггг'})
    )

    class Meta:
        model = WorkerPatent
        fields = (
            'worker_id',
            'date_of_issue',
            'series',
            'number',
            'issued_by',
            'profession',
            'profession_id',
        )


class WorkerPatentWithCitizenshipForm(WorkerPatentForm):
    citizenship = forms.IntegerField(required=False, widget=forms.HiddenInput())

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_class = 'form-horizontal'
        self.helper.form_tag = False
        self.helper.label_class = 'col-lg-4'
        self.helper.field_class = 'col-lg-8'

    def clean(self):
        cleaned_data = super().clean()
        try:
            citizenship = Country.objects.get(id=cleaned_data.get('citizenship'))
        except Country.DoesNotExist:
            pass
        else:
            if citizenship.name not in ['РФ', 'Казахстан', 'Киргизия',
                                        'Республика Армения', 'Белоруссия']:
                required = [
                    'date_of_issue',
                    'series',
                    'number',
                    'issued_by',
                    'profession',
                    'profession_id',
                ]
                for item in required:
                    if not cleaned_data.get(item):
                        self.add_error(item, 'Поле обязательно для заполнения')

    def has_changed(self):
        changed_data = self.changed_data
        changed_data.remove('citizenship')
        return bool(changed_data)


class WorkerMedicalCardForm(forms.ModelForm):
    worker_id = forms.IntegerField(required=False, widget=forms.HiddenInput())
    card_date_of_issue = forms.DateField(
        label='Дата выдачи',
        input_formats=[DATE_FORMAT],
        required=False,
        initial='дд.мм.гггг'
    )
    card_date_of_exp = forms.DateField(
        label='Дата окончания',
        input_formats=[DATE_FORMAT],
        required=False,
        initial='дд.мм.гггг'
    )

    class Meta:
        model = models.WorkerMedicalCard
        exclude = ['worker', ]

    def __init__(self, *args, **kwargs):
        super(WorkerMedicalCardForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_class = 'form-horizontal'
        self.helper.form_tag = False
        self.helper.label_class = 'col-lg-4'
        self.helper.field_class = 'col-lg-8'


class WorkerSelfEmploymentDataForm(forms.ModelForm):
    class Meta:
        model = models.WorkerSelfEmploymentData
        exclude = ['worker', 'deletion_ts']


class CustomerForm(forms.ModelForm):
    class Meta:
        model = Customer
        fields = ['cust_name']


class CustomerSelectionForm(forms.Form):
    customer = forms.ModelChoiceField(
        label='Клиент',
        queryset=Customer.objects.all(),
        widget=autocomplete.ModelSelect2(
            attrs={'class': 'form-control form-control-sm'},
            url="the_redhuman_is:customer-autocomplete"
        )
    )


class CustCommentsForm(forms.ModelForm):
    class Meta:
        model = CustComments
        fields = ('date', 'author', 'text', 'task_date', 'task_text')
    task_date = forms.DateField(input_formats=[DATE_FORMAT], required=False,
                                initial='дд.мм.гггг', label='Дата следующего контакта')


class OperationForm(forms.ModelForm):
    class Meta:
        model = finance.models.Operation
        fields = (
            'timepoint',
            'debet',
            'credit',
            'amount',
            'author',
            'comment',
        )
        widgets = {
            'comment': forms.Textarea(
                attrs={'cols': 48, 'rows': 4}
            ),
            'debet': autocomplete.Select2(
                url='the_redhuman_is:finance-account-autocomplete',
                attrs={'class': 'form-control form-control-sm'}
            ),
            'credit': autocomplete.Select2(
                url='the_redhuman_is:finance-account-autocomplete',
                attrs={'class': 'form-control form-control-sm'}
            ),
            'author': forms.Select(
                attrs={'class': 'form-control form-control-sm'}
            )
        }


class CutedOperationForm(forms.ModelForm):
    class Meta:
        model = finance.models.Operation
        fields = (
            'timepoint',
            'debet',
            'credit',
            'amount',
            'comment',
            'author',
        )
        widgets = {
            'debet': autocomplete.Select2(
                url='the_redhuman_is:finance-account-autocomplete',
                attrs={'class': 'form-control form-control-sm'}
            ),
            'credit': autocomplete.Select2(
                url='the_redhuman_is:finance-account-autocomplete',
                attrs={'class': 'form-control form-control-sm'}
            ),
            'author': forms.Select(
                attrs={'class': 'form-control form-control-sm'}
            )
        }


class CustomOperationForm(forms.Form):
    date = forms.DateField(
        widget=forms.widgets.DateInput(format=DATE_FORMAT), input_formats=[DATE_FORMAT],
        required=False, label='Дата'
    )
    choice = forms.ChoiceField(
        choices=(
            ("Платеж за общехозяйственные расходы из кассы", "Платеж за общехозяйственные расходы из кассы"),
            ("Выдача денег подотчетному лицу", "Выдача денег подотчетному лицу"),
            ("Платеж на 302 счет", "Платеж на 302 счет"),
            ("Поступление наличных от переводов на р/с", "Поступление наличных от переводов на р/с"),
            ("Платеж за общехозяйственные расходы с р/с Юнистрим",
             "Платеж за общехозяйственные расходы с р/с Юнистрим"),
            # ("Выплата з/п", "Выплата з/п"),
            ("Уплата налогов", "Уплата налогов"),
            ("Поступление от клиента", "Поступление от клиента"),
            ("Поступление от кредитора", "Поступление от кредитора"),
        ),
        label='Тип операции')
    amount = forms.FloatField(label='Сумма')
    comment = forms.CharField(label='Комментарий', widget=forms.Textarea(attrs={'cols': 48, 'rows': 4}))


CustomerLocationFormSet = forms.modelformset_factory(CustomerLocation, fields=(
    'location_name',
    'location_adress',
    'location_how_to_get',
))

CustomerReprFormSet = forms.modelformset_factory(CustomerRepr, fields=(
    'repr_last_name',
    'repr_name',
    'repr_patronymic',
    'position',
    'tel_number',
    'main'
))


class CustomerOrderForm(forms.ModelForm):
    bid_date_time = forms.DateField(
        input_formats=[DATE_FORMAT],
        required=False,
        initial=lambda: datetime.datetime.today()
    )
    on_date = forms.DateField(input_formats=[DATE_FORMAT], required=False, initial='дд.мм.гггг')
    on_time = forms.TimeField(input_formats=['%H:%M'], required=False, initial='ЧЧ:ММ')

    customer = forms.ModelChoiceField(
        label="Клиент",
        queryset=Customer.objects.all(),
        widget=autocomplete.ModelSelect2(url="the_redhuman_is:customer-autocomplete")
    )

    cust_location = forms.ModelChoiceField(
        label="Объект",
        queryset=CustomerLocation.objects.all(),
        widget=autocomplete.ModelSelect2(url='the_redhuman_is:customer-location-autocomplete',
                                         forward=["customer"]),
    )

    class Meta:
        model = CustomerOrder
        fields = (
            'bid_date_time',
            'on_date',
            'on_time',
            'bid_turn',
            'customer',
            'cust_location',
            'number_of_workers',
        )


CustomerOrderFormSet = forms.modelformset_factory(
    CustomerOrder,
    form=CustomerOrderForm,
    fields=(
        'bid_date_time',
        'on_date',
        'on_time',
        'bid_turn',
        'customer',
        'cust_location',
        'number_of_workers',
    ),
    widgets={
        'customer': autocomplete.ModelSelect2(url='the_redhuman_is:customer-autocomplete'),
        'cust_location': autocomplete.ModelSelect2(url='the_redhuman_is:customer-location-autocomplete',
                                                   forward=["customer"]),
    },
    can_delete=True
)


class NameForm(forms.ModelForm):
    name = forms.CharField(label='Название')


MetroFormSet = forms.modelformset_factory(
    Metro,
    form=NameForm,
    fields=(
        'name',
    ),
    can_delete=True
)


CountryFormSet = forms.modelformset_factory(
    Country,
    form=NameForm,
    fields=(
        'name',
    ),
    can_delete=True
)


PositionFormSet = forms.modelformset_factory(
    Position,
    form=NameForm,
    fields=(
        'name',
    ),
    can_delete=True
)


BankFormSet = forms.modelformset_factory(
    Bank,
    form=NameForm,
    fields=(
        'name',
    ),
    can_delete=True
)

CreditorFormSet = forms.modelformset_factory(
    Creditor,
    form=NameForm,
    fields=(
        'name',
    ),
    can_delete=True
)

AdministrationCostTypeFormSet = forms.modelformset_factory(
    AdministrationCostType,
    form=NameForm,
    fields=(
        'name',
    ),
    can_delete=True
)

IndustrialCostTypeFormSet = forms.modelformset_factory(
    IndustrialCostType,
    form=NameForm,
    fields=(
        'name',
    ),
    can_delete=True
)


class BankServiceForm(forms.ModelForm):

    class Meta:
        model = BankService
        fields = (
            'type',
            'debit',
        )
        widgets = {'debit': autocomplete.Select2(url='the_redhuman_is:finance-account-autocomplete')}


BankServiceFormSET = forms.modelformset_factory(
    BankService,
    form=BankServiceForm,
    fields=(
        'type',
        'debit',
    ),
    can_delete=True
)


class BankServiceParamsForm(forms.ModelForm):
    service = forms.ModelChoiceField(
        queryset=BankService.objects.all(),
        widget=autocomplete.ModelSelect2(url="the_redhuman_is:bank-service-autocomplete", attrs={
                    "data-placeholder": "Услуга",
                },),)

    calculator_type = forms.CharField(
        label="",
        widget=autocomplete.ModelSelect2(
                      choices=[("fix", "Фикс"),
                               ("commission1", "От исходящей суммы"),
                               ("commission2", "От входящей суммы")],
                      attrs={'data-placeholder': 'Тип комиссии'}))

    val = forms.FloatField(widget=forms.TextInput(attrs={'placeholder': 'Размер комиссии'}))

    class Meta:
        model = BankServiceParams
        fields = (
            'service',
        )


BankServiceParamsFormSET = forms.modelformset_factory(
    BankServiceParams,
    form=BankServiceParamsForm,
    fields=(
        'service',
    ),
    can_delete=True
)


class MManagerForm(forms.Form):
    worker = forms.ModelChoiceField(
        queryset=Worker.objects.all(),
        widget=autocomplete.ModelSelect2(url="the_redhuman_is:m_manager_position-autocomplete"),
        required=False,
    )


class DManagerForm(forms.Form):
    worker = forms.ModelChoiceField(
        queryset=Worker.objects.all(),
        widget=autocomplete.ModelSelect2(url="the_redhuman_is:d_manager_position-autocomplete"),
        required=False,
    )


class MPositionForm(forms.ModelForm):
    position = forms.ModelChoiceField(
        queryset=Position.objects.all(),
        widget=autocomplete.ModelSelect2(url="the_redhuman_is:position-m-minus-autocomplete")
    )

    class Meta:
        model = MaintenanceManagerPosition
        fields = (
            'position',
        )


class DPositionForm(forms.ModelForm):
    position = forms.ModelChoiceField(
        queryset=Position.objects.all(),
        widget=autocomplete.ModelSelect2(url="the_redhuman_is:position-d-minus-autocomplete")
    )

    class Meta:
        model = DevelopmentManagerPosition
        fields = (
            'position',
        )


MManagerPositionFormSET = forms.modelformset_factory(
    MaintenanceManagerPosition,
    form=MPositionForm,
    fields=(
        'position',
    ),
    can_delete=True
)


DManagerPositionFormSET = forms.modelformset_factory(
    DevelopmentManagerPosition,
    form=DPositionForm,
    fields=(
        'position',
    ),
    can_delete=True
)


class TimeSheetForm(forms.ModelForm):
    sheet_date = forms.DateField(
        label="Дата табеля",
        input_formats=["%d.%m.%Y"],
        initial="дд.мм.гггг",
        widget=forms.DateInput(attrs={"size": "10"}, format="%d.%m.%Y")
    )
    customer = forms.ModelChoiceField(
        label="Клиент",
        queryset=Customer.objects.all(),
        widget=autocomplete.ModelSelect2(url="the_redhuman_is:customer-autocomplete")
    )
    cust_location = forms.ModelChoiceField(
        label="Объект",
        queryset=CustomerLocation.objects.all(),
        widget=autocomplete.ModelSelect2(url="the_redhuman_is:customer-location-autocomplete", forward=["customer"])
    )
    customer_repr = forms.ModelChoiceField(
        label="Представитель клиента",
        queryset=CustomerRepr.objects.all(),
        widget=autocomplete.ModelSelect2(url="the_redhuman_is:customer-repr-autocomplete", forward=["customer"])
    )
    foreman = forms.ModelChoiceField(
        label="Бригадир",
        queryset=Worker.objects.filter(
            Q(position__name="Бригадир") |
            Q(position__name="Стажер")
        ),
        widget=autocomplete.ModelSelect2(url="the_redhuman_is:foreman-autocomplete")
    )

    def __init__(self, *args, **kwargs):
        super(TimeSheetForm, self).__init__(*args, **kwargs)

        key_order = [
            'sheet_date',
            'sheet_turn',
            'customer',
            'cust_location',
            'customer_repr',
            'foreman',
            'turnouts_number',
            'image',
            'image2',
            'image3',
            'image4'
        ]

        for k, v in self.fields.items():
            if k not in key_order:
                raise Exception("Key {} is missing in key_order!".format(k))

        fields = collections.OrderedDict()
        for key in key_order:
            fields[key] = self.fields[key]

        self.fields = fields

    class Meta:
        model = TimeSheet
        fields = (
            'id',
            'sheet_date',
            'sheet_turn',
            'customer',
            'cust_location',
            'customer_repr',
            'foreman',
            'turnouts_number',
            'image',
            'image2',
            'image3',
            'image4',
        )


class TimeSheetSelectForm(forms.Form):
    timesheet = forms.ModelChoiceField(
        queryset=TimeSheet.objects.filter(is_executed=False),
        label='',
        required=False
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_tag = False


class CustomerOrderModelChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return "{}>{}>{}>{}>{}".format(
            obj.bid_date_time.strftime(DATE_FORMAT),
            obj.customer,
            obj.cust_location,
            obj.bid_turn,
            obj.bid_date_time.strftime('%H:%M'),
        )


class TimeSheetWOutImagesForm(forms.ModelForm):
    customer_order = CustomerOrderModelChoiceField(
        label='Заявка',
        queryset=CustomerOrder.objects.select_related(
            'customer',
            'cust_location',
        ).filter(
            timesheet__isnull=True
        )
    )
    sheet_date = forms.DateField(
        label="Дата табеля",
        input_formats=["%d.%m.%Y"],
        widget=forms.TextInput(attrs={'placeholder': 'дд.мм.гггг'}),
    )
    customer = forms.ModelChoiceField(
        label="Клиент",
        queryset=Customer.objects.all(),
        widget=autocomplete.ModelSelect2(
            url="the_redhuman_is:customer-autocomplete"
        )
    )
    cust_location = forms.ModelChoiceField(
        label="Объект",
        queryset=CustomerLocation.objects.all(),
        widget=autocomplete.ModelSelect2(
            url="the_redhuman_is:customer-location-autocomplete",
            forward=["customer"]
        )
    )
    customer_repr = forms.ModelChoiceField(
        label="Представитель клиента",
        queryset=CustomerRepr.objects.all(),
        widget=autocomplete.ModelSelect2(
            url="the_redhuman_is:customer-repr-autocomplete",
            forward=["customer"]
        )
    )
    foreman = forms.ModelChoiceField(
        label="Бригадир",
        queryset=Worker.objects.filter(
            Q(position__name="Бригадир") | Q(position__name="Стажер")
        ),
        widget=autocomplete.ModelSelect2(
            url="the_redhuman_is:foreman-autocomplete"
        )
    )
    field_order = ['customer_order']

    class Meta:
        model = TimeSheet
        fields = (
            "sheet_date",
            "sheet_turn",
            "customer",
            "cust_location",
            "customer_repr",
            "foreman",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_class = 'form-horizontal'
        self.helper.form_tag = False
        self.helper.label_class = 'col-lg-4'
        self.helper.field_class = 'col-lg-8'

    def _save_m2m(self):
        super(TimeSheetWOutImagesForm, self)._save_m2m()
        customer_order = self.cleaned_data['customer_order']
        customer_order.timesheet = self.instance
        customer_order.save(update_fields=['timesheet'])


class WorkerTurnoutForm(forms.ModelForm):
    worker = forms.ModelChoiceField(
        label="Рабочий",
        queryset=Worker.objects.all(),
        widget=autocomplete.ListSelect2(
            url="the_redhuman_is:worker_with_contract_autocomplete"
        )
    )
    service = forms.ModelChoiceField(
        label="Услуга",
        queryset=models.CustomerService.objects.all(),
        widget=autocomplete.ModelSelect2(
            url="the_redhuman_is:customer-service-autocomplete",
            forward=["customer"]
        ),
        required=False
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        key_order = [
            "worker",
            "worker_code_name",
            "service",
            "hours_worked",
            "performance",
        ]

        for k, v in self.fields.items():
            if k not in key_order:
                raise Exception("Key {} is missing in key_order!".format(k))

        fields = collections.OrderedDict()
        for key in key_order:
            fields[key] = self.fields[key]

        self.fields = fields

        self.fields['worker_code_name'].label = 'Код'
        self.fields['worker_code_name'].widget.attrs[
            'style'
        ] = 'max-width: 50px;'

        self.helper = FormHelper()
        self.helper.form_class = 'form-horizontal'
        self.helper.form_tag = False
        self.helper.include_media = False
        self.helper.label_class = 'col-lg-4'
        self.helper.field_class = 'col-lg-8'

    class Meta:
        model = models.WorkerTurnout
        fields = ("worker", "worker_code_name", "hours_worked", "performance")


WorkerTurnoutFormSet = forms.modelformset_factory(
    WorkerTurnout,
    form=WorkerTurnoutForm
)

WorkerTurnoutFormSetWithContract = forms.modelformset_factory(
    WorkerTurnout,
    form=WorkerTurnoutForm
)


class ShowFromDateToDateForm(forms.Form):
    from_date = forms.DateField(
        widget=forms.DateInput(format=DATE_FORMAT,
                               attrs={'class': 'form-control form-control-sm'}),
        input_formats=[DATE_FORMAT],
        initial=lambda: datetime.date.today() - datetime.timedelta(days=30))
    to_date = forms.DateField(
        widget=forms.DateInput(format=DATE_FORMAT,
                               attrs={'class': 'form-control form-control-sm'}),
        input_formats=[DATE_FORMAT],
        initial=lambda: datetime.date.today())

    def clean(self):
        cd = super(ShowFromDateToDateForm, self).clean()
        for key in ['from_date', 'to_date']:
            if key not in cd.keys():
                raise forms.ValidationError('{} is required in form'.format(key))

        if cd['from_date'] > cd['to_date']:
            raise forms.ValidationError("from_date < to_date")
        return cd


class ContractForm(forms.ModelForm):
    begin_date = _dateinput_field('Дата заключения')
    end_date = _dateinput_field('Дата окончания')
    c_worker_id = forms.IntegerField(required=False, widget=forms.HiddenInput())

    def __init__(self, readonly_dates=True, *args, **kwargs):
        super(ContractForm, self).__init__(*args, **kwargs)
        if readonly_dates:
            for key in ['begin_date', 'end_date']:
                self.fields[key].widget.attrs['readonly'] = True

    class Meta:
        model = Contract
        fields = (
            'c_worker_id',
            'contractor',
            'begin_date',
            'end_date',
            'cont_type',
            'is_actual',
            'image',
            'image2',
            'image3',
        )


class ContractForm1(forms.ModelForm):
    begin_date = forms.DateField(
        label='Дата заключения',
        input_formats=[DATE_FORMAT],
        required=False,
        initial='дд.мм.гггг'
    )

    class Meta:
        model = Contract
        fields = (
            'c_worker',
            'begin_date',
            'cont_type',
            'is_actual',
            'image',
            'image2',
            'image3',
        )


ContractFormSet = forms.modelformset_factory(
    Contract,
    form=ContractForm,
    fields=(
        'begin_date',
        'c_worker',
        'cont_type',
        'is_actual',
        'image',
        'image2',
        'image3',
    ),
    widgets={
        'c_worker': autocomplete.ModelSelect2(
            url='the_redhuman_is:worker-autocomplete'
        ),
    }
)


class NoticeOfContractForm(forms.ModelForm):
    to_delete = forms.BooleanField(required=False, label='Удалить?')

    class Meta:
        model = NoticeOfContract
        fields = ('id', 'image', )


NoticeOfContractFormSet = forms.modelformset_factory(
    NoticeOfContract, extra=0,
    form=NoticeOfContractForm,
    widgets={
        'id': forms.HiddenInput,
    }
)


class NoticeOfTerminationForm(forms.ModelForm):
    to_delete = forms.BooleanField(required=False, label='Удалить?')

    class Meta:
        model = NoticeOfTermination
        fields = ('id', 'image', )


NoticeOfTerminationFormSet = forms.modelformset_factory(
    NoticeOfTermination, extra=0,
    form=NoticeOfTerminationForm,
    widgets={
        'id': forms.HiddenInput,
    }
)


class MyModelChoiceIterator(forms.models.ModelChoiceIterator):

    def __init__(self, field):
        super().__init__(field)
        self.field.choice_objects = {}

    def choice(self, obj):
        self.field.choice_objects[obj.pk] = obj
        return super().choice(obj)


class MyModelMultipleChoiceField(forms.ModelMultipleChoiceField):

    def _get_choices(self):
        if hasattr(self, '_choices'):
            return self._choices
        return MyModelChoiceIterator(self)


def years_for_select(last_year=True):
    beg_year = timezone.now().year
    if last_year:
        beg_year -= 1
    return [beg_year+i for i in range(6)]


class CalendarForm(forms.Form):
    customer = forms.ModelChoiceField(
        label="Клиент",
        queryset=Customer.objects.all(),
        widget=autocomplete.ModelSelect2(
            url="the_redhuman_is:customer-autocomplete"
        )
    )
    service = forms.ModelChoiceField(
        label="Услуга",
        queryset=models.CustomerService.objects.none(),
        widget=autocomplete.ModelSelect2(
            url="the_redhuman_is:customer-service-autocomplete",
            forward=["customer"]
        )
    )
    location = forms.ModelChoiceField(
        label="Объект",
        queryset=models.CustomerLocation.objects.none(),
        widget=autocomplete.ModelSelect2(
            url="the_redhuman_is:customer-location-autocomplete",
            forward=["customer"]
        )
    )
    display = forms.CharField(
        label="Показывать",
        widget=forms.widgets.Select(
            choices=[
                ("hours", "Часы"),
                ("performance", "Выработку"),
                ("credit", "Начисления"),
                ("debet", "Выплаты"),
                ("to_pay", "Не оплаченные"),
                ("payed", "Оплаченные"),
                ("fine", "Штрафы"),
                ("deduct", "Вычеты"),
                ("credit_minus_deduct", "Начисления - Вычеты")
            ],
            attrs={'class': "form-control form-control-sm"}
        )
    )
    sheet_turn = forms.CharField(
        label="Смена",
        widget=forms.widgets.Select(
            choices=[
                ("День", "День"),
                ("Ночь", "Ночь"),
                ("", "Без разницы"),
            ],
            attrs={'class': "form-control form-control-sm"}
        ),
        initial=''
    )
    mmanager = forms.ModelChoiceField(
        label="Мен-р по ведению",
        queryset=MaintenanceManager.objects.all(),
        required=False,
        widget=autocomplete.ModelSelect2(
            url="the_redhuman_is:m_manager-autocomplete"
        )
    )
    dmanager = forms.ModelChoiceField(
        label="Мен-р по развитию",
        queryset=DevelopmentManager.objects.all(),
        required=False,
        widget=autocomplete.ModelSelect2(
            url="the_redhuman_is:d_manager-autocomplete"
        )
    )
    show_details = forms.BooleanField(
        initial=False,
        label="Детализация",
        widget=forms.widgets.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    report_type = forms.CharField(
        label="Вид отчета",
        widget=forms.widgets.Select(
            choices=[
                ("day", "Ежедневно"),
                ("week", "Еженедельно"),
                ("month", "Ежемесячно"),
            ],
            attrs={'class': "form-control form-control-sm"}
        ),
        initial='day'
    )
    avg_or_sum = forms.CharField(
        label="Вид результата",
        widget=forms.widgets.Select(
            choices=[
                ("avg", "Среднее"),
                ("sum", "Сумма"),
            ],
            attrs={'class': "form-control form-control-sm"}
        ),
        initial='avg'
    )
    begin_date = forms.DateField(
        label="С",
        widget=forms.DateInput(
            format=DATE_FORMAT,
            attrs={'class': 'form-control  form-control-sm'}
        ),
        input_formats=[DATE_FORMAT],
    )
    end_date = forms.DateField(
        label="По",
        widget=forms.DateInput(
            format=DATE_FORMAT,
            attrs={'class': 'form-control  form-control-sm'}
        ),
        input_formats=[DATE_FORMAT],
    )

    @classmethod
    def create(cls):
        today = datetime.date.today()
        first_day = today.replace(day=1)
        return CalendarForm(
            initial={
                'begin_date': first_day,
                'end_date': today
            }
        )


class StatementWorkersForm(forms.Form):
    customer = forms.ModelChoiceField(
        label="Клиент",
        queryset=Customer.objects.all(),
        widget=forms.HiddenInput(),
        required=False,
    )
#    worker = forms.ModelChoiceField(
#        label="Рабочие",
#        queryset=Worker.objects.all(),
#        required=False,
#        widget=autocomplete.Select2Multiple(
#            url="the_redhuman_is:worker-by-turnouts-autocomplete",
#            attrs={'class': 'form-control'}
#        ),
#    )
    begin_date = forms.DateField(
        label="С",
        input_formats=[DATE_FORMAT],
        widget=forms.HiddenInput(),
        required=False,
    )
    end_date = forms.DateField(
        label="По",
        input_formats=[DATE_FORMAT],
        widget=forms.HiddenInput(),
        required=False,
    )
    is_prepayment = forms.BooleanField(
        initial=False,
        label="Аванс",
        required=False,
    )


class ServiceCalculatorForm(forms.Form):
    customer = forms.ModelChoiceField(
        label="Клиент",
        queryset=Customer.objects.all(),
        widget=autocomplete.ModelSelect2(url="the_redhuman_is:customer-autocomplete")
    )
    service = forms.ModelChoiceField(
        label="Услуга",
        queryset=models.CustomerService.objects.all(),
        widget=autocomplete.ModelSelect2(
            url="the_redhuman_is:customer-service-autocomplete",
            forward=["customer"]
        )
    )
    interval = forms.ModelChoiceField(
        label="Интервал",
        queryset=models.ServiceCalculator.objects.all(),
        widget=autocomplete.ModelSelect2(
            url="the_redhuman_is:autocharge_service_calculator_autocomplete",
            forward=["service"]
        )
    )


class PositionCalculatorForm(forms.Form):
    p_customer = forms.ModelChoiceField(
        label='Клиент',
        queryset=Customer.objects.all(),
        widget=autocomplete.ModelSelect2(url='the_redhuman_is:customer-autocomplete')
    )

    position = forms.ModelChoiceField(
        label='Должность',
        queryset=Position.objects.all()
    )

    p_interval = forms.ModelChoiceField(
        label='Интервал',
        queryset=models.ServiceCalculator.objects.all(),
        widget=autocomplete.ModelSelect2(
            url='the_redhuman_is:autocharge_position_calculator_autocomplete',
            forward=['p_customer', 'position']
        )
    )


class ServiceForm(forms.Form):
    service = forms.ModelChoiceField(
        label="Услуга",
        queryset=models.Service.objects.all(),
        widget=autocomplete.ModelSelect2(
            url="the_redhuman_is:service-autocomplete",
            forward=["customer"]
        )
    )


class WorkersDocumentsForm(forms.Form):
    photo = forms.ChoiceField(
        label="Фотография",
        choices=((1, 'С фотографиями'),
                 (0, 'Без фотографий'),
                 (-1, '-')),
        initial=-1
    )

    contract = forms.ChoiceField(
        label="Контракт",
        choices=(
            (1, 'С контрактами'),
            (0, 'Без контрактов'),
            (-1, '-')
        ),
        initial=-1
    )

    med_card = forms.ChoiceField(
        label="Мед книжка",
        choices=(
            (1, 'С мед. книжкой'),
            (0, 'Без мед. книжки'),
            (-1, '-')
        ),
        initial=-1
    )

    patent = forms.ChoiceField(
        label='Патент',
        choices=(
            (1, 'С патентами'),
            (0, 'Без патентов'),
            (-1, '-'),
        ),
        initial=-1
    )

    registration = forms.ChoiceField(
        label='Регистрация',
        choices=(
            (1, 'С регистрацией'),
            (0, 'Без регистрации'),
            (-1, '-')
        ),
        initial=-1
    )

    passport = forms.ChoiceField(
        label='Паспорт',
        choices=(
            (1, 'С паспортом'),
            (0, 'Без паспорта'),
            (-1, '-')
        ),
        initial=-1
    )


class MakeExpenseForm(forms.Form):
    customer = forms.ModelChoiceField(
        label="Клиент",
        queryset=Customer.objects.all(),
        widget=autocomplete.ModelSelect2(
            url="the_redhuman_is:customer-autocomplete"
        )
    )
    person = forms.ModelChoiceField(
        label="Подотчетное лицо",
        queryset=models.AccountablePerson.objects.all(),
        widget=autocomplete.ModelSelect2(
            url="the_redhuman_is:accountable-person-autocomplete"
        )
    )
    paysheet = forms.CharField(
        label="Ведомость",
        widget=autocomplete.Select2(
            url="the_redhuman_is:paysheet_v2_paysheet_autocomplete",
            forward=['person']
        )
    )


class PhotoLoadSessionForm(forms.Form):
    file = forms.FileField(required=False)
    comment = forms.CharField(widget=forms.Textarea(attrs={'rows': 2}),
                              required=False,
                              label='Комментарий')

    def __init__(self, *args, **kwargs):
        super(PhotoLoadSessionForm, self).__init__(*args, **kwargs)
        self.fields['file'].widget = forms.HiddenInput()
        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.layout = Layout(
            'file',
            'comment',
        )


class PhotoLoadSessionCommentForm(forms.Form):
    comment = forms.CharField(widget=forms.Textarea, required=True,
                              label='Комментарий')

    def __init__(self, *args, **kwargs):
        super(PhotoLoadSessionCommentForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.layout = Layout(
            'comment',
        )


class VacantCustomerLocationForm(forms.Form):
    location = forms.ModelMultipleChoiceField(
        label="Объекты",
        queryset=CustomerLocation.objects.none(),
        widget=autocomplete.ModelSelect2Multiple(
            url="the_redhuman_is:vacant-customer-location-autocomplete"
        )
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_class = 'form-horizontal'
        self.helper.form_tag = False
        self.helper.label_class = 'col-lg-2'
        self.helper.field_class = 'col-lg-10'


class DaysIntervalForm(forms.Form):
    def __init__(self, field_prefix=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if field_prefix:
            _rename_field(self.fields, 'first_day', field_prefix + 'first_day')
            _rename_field(self.fields, 'last_day', field_prefix + 'last_day')

    first_day = _datepicker_field('C', 'С')
    last_day = _datepicker_field('По', 'По')


class DaysPickerIntervalForm(forms.Form):
    def __init__(self, field_prefix=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if field_prefix:
            _rename_field(self.fields, 'first_day', field_prefix + 'first_day')
            _rename_field(self.fields, 'last_day', field_prefix + 'last_day')

    first_day = DateField(
        label='C',
        widget=DatePickerWidget(
            attrs={'autocomplete': 'off'},
            format='%d.%m.%Y',
            picker_options={'locale': DATEPICKER_LOCALE},
        ),
    )
    last_day = DateField(
        label='По',
        widget=DatePickerWidget(
            attrs={'autocomplete': 'off'},
            format='%d.%m.%Y',
            picker_options={'locale': DATEPICKER_LOCALE},
        ),
    )


class ManagerAndIntervalForm(DaysIntervalForm):
    manager = forms.ModelChoiceField(
        queryset=models.Worker.objects.filter(maintenancemanager__isnull=False),
        label='Менеджер',
        widget=autocomplete.ModelSelect2(
            url='the_redhuman_is:m_manager-autocomplete'
        ),
        required=False
    )


class StaffTurnoverForm(forms.Form):
    manager = forms.ModelChoiceField(
        label='Менеджер',
        queryset=models.Worker.objects.filter(maintenancemanager__isnull=False),
        widget=autocomplete.ModelSelect2(
            url='the_redhuman_is:m_manager-autocomplete'
        ),
        required=False
    )


class TimesheetTimelinessForm(ManagerAndIntervalForm):
    delay_type = forms.CharField(
        label='Показывать',
        widget=forms.widgets.Select(
            choices=[
                ('before', 'До смены'),
                ('after', 'После смены'),
            ],
            attrs={'class': 'form-control form-control-sm'}
        )
    )


class CustomerSummaryReportFilter(ManagerAndIntervalForm):
    def __init__(self, choices, *args, **kwargs):
        super(CustomerSummaryReportFilter, self).__init__(*args, **kwargs)
        self.fields['report_type'].widget.choices = choices

    customer_fetch_type = forms.CharField(
        label='Выборка клиентов',
        widget=forms.widgets.Select(
            choices=CUSTOMER_FETCH_TYPES,
            attrs={
                'class': 'form-control form-control-sm',
                'style': 'max-width: 180px;'
            }
        )
    )

    customers = forms.ModelChoiceField(
        label='Клиенты',
        queryset=Customer.objects.all(),
        widget=autocomplete.ModelSelect2Multiple(
            attrs={
                'class': 'form-control form-control-sm',
            },
            url="the_redhuman_is:customer-autocomplete"
        ),
        required=False
    )

    layout_type = forms.CharField(
        label='Разбивка',
        widget=forms.widgets.Select(
            choices=LAYOUT_TYPES,
            attrs={
                'class': 'form-control form-control-sm',
                'style': 'max-width: 160px;'
            }
        )
    )

    report_type = forms.CharField(
        label='Вариант отчета',
        widget=forms.widgets.Select(
            attrs={
                'class': 'form-control form-control-sm',
                'style': 'max-width: 140px;'
            }
        )
    )

    citizenship = forms.CharField(
        label='Гражданство',
        widget=forms.widgets.Select(
            choices=CITIZENSHIP_TYPES,
            attrs={'class': 'form-control form-control-sm'}
        ),
        required=False
    )


class FormExtension(forms.Form):
    def __init__(self, target_form=None, *args, **kwargs):
        super(FormExtension, self).__init__(*args, **kwargs)
        if target_form:
            for key in list(self.fields.keys()):
                self.fields[key].widget.attrs['form'] = target_form


class SingleDateForm(FormExtension):
    def __init__(self, field_name='date', *args, **kwargs):
        super(SingleDateForm, self).__init__(*args, **kwargs)
        if field_name != 'date':
            _rename_field(self.fields, 'date', field_name)

    date = _datepicker_field('Дата', 'Дата', lambda: timezone.now().strftime(DATE_FORMAT))


class CustomerAndLocationForm(CustomerSelectionForm):
    location = forms.ModelChoiceField(
        label="Объект",
        queryset=CustomerLocation.objects.all(),
        widget=autocomplete.ModelSelect2(
            attrs={'class': 'form-control form-control-sm'},
            url="the_redhuman_is:actual-location-autocomplete",
            forward=["customer"]
        )
    )


class AccountablePersonForm(forms.Form):
    def __init__(self, *args, field_name='person', **kwargs):
        super().__init__(*args, **kwargs)
        if field_name != 'person':
            _rename_field(self.fields, 'person', field_name)

    person = forms.ModelChoiceField(
        label="Подотчетное лицо",
        queryset=models.AccountablePerson.objects.all(),
        widget=autocomplete.ModelSelect2(
            url="the_redhuman_is:accountable-person-autocomplete"
        )
    )


class LegalEntitySelectionForm(forms.Form):
    legal_entity = forms.ModelChoiceField(
        label='Юрлицо',
        queryset=models.LegalEntity.objects.all(),
        widget=autocomplete.ModelSelect2(
            attrs={'class': 'form-control form-control-sm'},
            url='the_redhuman_is:legal-entity-autocomplete'
        )
    )


class ExpenseSelectionForm(forms.Form):
    expense = forms.ModelChoiceField(
        label='Расход',
        queryset=models.Expense.objects.all(),
        widget=autocomplete.ModelSelect2(
            attrs={'class': 'form-control form-control-sm'},
            url='the_redhuman_is:expense-autocomplete'
        )
    )


class UnpaidReconciliationSelectionForm(forms.Form):
    reconciliation = forms.ModelMultipleChoiceField(
        label='Сверка',
        queryset=models.Reconciliation.objects.all(),
        widget=autocomplete.ModelSelect2(
            attrs={'class': 'form-control form-control-sm', 'multiple': True},
            url='the_redhuman_is:reconciliation_unpaid_autocomplete'
        )
    )


class ReconciliationCreateForm(forms.Form):
    customer = forms.ModelChoiceField(
        label='Клиент',
        queryset=Customer.objects.all(),
        widget=autocomplete.ModelSelect2(
            url='the_redhuman_is:customer-autocomplete'
        ),
        error_messages={'required': 'Выберите клиента для сверки'},
    )
    location = forms.ModelChoiceField(
        label='Объект',
        queryset=CustomerLocation.objects.all(),
        required=False,
        widget=autocomplete.ModelSelect2(
            url='the_redhuman_is:actual-location-autocomplete',
            forward=['customer']
        )
    )
    create_for_each = forms.BooleanField(
        label='Создать сверки для всех объектов',
        initial=False,
        required=False,
    )
    last_day = DateField(
        label='Последний день периода',
        widget=DatePickerWidget(
            attrs={'autocomplete': 'off'},
            format='%d.%m.%Y',
            picker_options={'locale': DATEPICKER_LOCALE},
        ),
    )


class AccountsSelectionForm(forms.Form):
    debit = forms.ModelChoiceField(
        queryset=finance.models.Account.objects.all(),
        widget=autocomplete.ModelSelect2(
            url='the_redhuman_is:finance-account-autocomplete',
            attrs={'class': 'form-control form-control-sm'}
        ),
    )

    credit = forms.ModelChoiceField(
        queryset=finance.models.Account.objects.all(),
        widget=autocomplete.ModelSelect2(
            url='the_redhuman_is:finance-account-autocomplete',
            attrs={'class': 'form-control form-control-sm'}
        ),
    )


class DeliverZoneForm(forms.Form):
    zone = forms.ModelChoiceField(
        label='Зона доставки',
        queryset=ZoneGroup.objects.all(),
        widget=autocomplete.ModelSelect2(url='the_redhuman_is:delivery_zone_autocomplete')
    )


class DeliverOperatorForm(forms.Form):
    operator = forms.ModelChoiceField(
        queryset=User.objects.filter(
            is_active=True,
            groups__name='Доставка-диспетчер'
        ),
        widget=autocomplete.ModelSelect2Multiple(
            url='the_redhuman_is:delivery_operator_autocomplete'
        )
    )


class ReconciliationInvoiceForm(forms.ModelForm):
    class Meta:
        model = ReconciliationInvoice
        fields = ['number', 'date']
        widgets = {
            'date': DatePickerWidget(
                attrs={'autocomplete': 'off'},
                format='%d.%m.%Y',
                picker_options={'locale': DATEPICKER_LOCALE},
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Row(
                Field('number', css_class='form-control form-control-sm'),
                Field('date', css_class='form-control form-control-sm'),
                css_class='mt-0 mb-0',
            ),
            Row(
                SubmitNoValue(
                    'submit-set-invoice',
                    'Сохранить',
                    css_class='btn-sm btn-action btn-outline-primary',
                ),
                css_class='mt-0 mb-0',
            ),
        )
