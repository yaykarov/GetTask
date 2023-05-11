# -*- coding: utf-8 -*-

from crispy_forms.helper import FormHelper
from dal import autocomplete
from django import forms
from django.contrib.auth.models import User
from django.forms import widgets

from applicants.models import Applicant, ApplicantSource, Status, StatusInitial

from the_redhuman_is.models import CustomerLocation

from the_redhuman_is.forms import _datepicker_field


class ApplicantLocationModelChoiceField(forms.ModelChoiceField):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.show_full_name = True

    def label_from_instance(self, obj):
        if self.show_full_name:
            return obj.full_name()
        else:
            return obj.location_name


class ApplicantForm(forms.ModelForm):
    author = forms.ModelChoiceField(
        queryset=User.objects.filter(
            groups__name__in=[
                'Подборщики',
                'Подборщики внешние',
                'Подборщики руководитель'
            ]
        ).distinct(),
        label='Автор',
        required=False
    )
    location = ApplicantLocationModelChoiceField(
        queryset=CustomerLocation.objects.filter(
            is_actual=True,
            customer_id__is_actual=True,
            vacantcustomerlocation__isnull=False
        ),
        required=False,
        label='Объект'
    )
    status = forms.ModelChoiceField(
        queryset=Status.objects.filter(active=True),
        initial=lambda: StatusInitial.objects.get().status,
        label='Статус',
        widget=autocomplete.ModelSelect2(
            url="applicants:status-autocomplete",
            forward=['status_hidden', 'source'],
            attrs={
                'data-minimum-input-length': 0,
                'data-width': '100%',
            },
        )
    )
    status_hidden = forms.IntegerField(
        required=False,
        widget=forms.HiddenInput()
    )
    init_date = _datepicker_field('Дата первого контакта')
    next_date = _datepicker_field('Дата следующего контакта')

    class Meta:
        model = Applicant
        fields = '__all__'
        exclude = ('active', 'init_date', 'last_edited')

        widgets = {
            'comment': forms.Textarea(attrs={'rows': 5, 'cols': 63}),
        }

    class Media:
        js = ('autocomplete_light/forward.js',)

    def __init__(self, *args, **kwargs):
        location_pk = kwargs.get('location_pk')
        if location_pk:
            kwargs.pop('location_pk')
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_class = 'form-horizontal'
        self.helper.form_tag = False
        self.helper.label_class = 'col-lg-4'
        self.helper.field_class = 'col-lg-8'

        if location_pk:
            self.fields['location'].queryset = CustomerLocation.objects.filter(pk=location_pk)
            self.fields['location'].show_full_name = False


class ApplicantBaseFilterForm(forms.Form):
    manager = forms.ModelChoiceField(
        queryset=User.objects.all(),
        label='Менеджер',
        widget=autocomplete.ModelSelect2(
            url='applicants:manager_autocomplete'
        ),
        required=False
    )

    source = forms.ModelChoiceField(
        queryset=ApplicantSource.objects.all(),
        label='Источник',
        widget=autocomplete.ModelSelect2(
            url='applicants:source_autocomplete'
        ),
        required=False
    )

    first_day = _datepicker_field('С')
    last_day = _datepicker_field('С')


class ListFilterForm(ApplicantBaseFilterForm):
    interval_type = forms.CharField(
        label='Фильтр по:',
        widget=widgets.Select(
            choices=[
                ('init_date', 'Дата занесения'),
                ('next_date', 'Дата след. контакта'),
                ('last_edited', 'Время посл. ред-я'),
                ('turnout_date', 'Дата выхода'),
            ],
            attrs={'class': "form-control form-control-sm"}
        )
    )


class FunnelFilterForm(ApplicantBaseFilterForm):
    pass


class ConveyorFilterForm(ApplicantBaseFilterForm):
    pass
