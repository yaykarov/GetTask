from django.views.generic.list import BaseListView

from dal.autocomplete import Select2QuerySetView

from rest_framework.exceptions import ValidationError
from rest_framework.views import APIView

from the_redhuman_is import models

from the_redhuman_is.dac_view import (
    administration_cost_types,
    industrial_cost_types,
    materials,
    workers_for_customer,
)


class Select2QuerySetAPIView(Select2QuerySetView, APIView):
    """
    React-компонент, отвечающий за отображение списка на фронте поддерживает следующую разметку
    (можно возвращать ее из get_label):

    - Цвет фона текста: <span style="background: #000000;">TEST</span>
    - Цвет текста: <span style="color: #000000;">TEST</span>
    - Подчеркнутый текст: <span style="text-decoration: underline;">TEST</span>
    - Жирный: <span style="font-weight: 700;">TEST</span>
    - Курсив: <span style="font-style: oblique;">TEST</span>
    - Зачеркнутый текст: <span style="text-decoration: line-through;">TEST</span>
    - Несколько свойств: <span style="background: black; color: red;">TEST</span>
    """

    def get(self, request, *args, **kwargs):
        if 'id' not in request.GET:
            return super(Select2QuerySetAPIView, self).get(request, *args, **kwargs)
        try:
            ids = [int(pk) for pk in request.GET['id'].split(',')]
        except ValueError:
            raise ValidationError(
                'Параметр `id` должен быть списком целых чисел через запятую.'
            )
        self.paginate_by = None
        self.object_list = BaseListView.get_queryset(self).filter(id__in=ids).order_by()
        context = self.get_context_data()
        return self.render_to_response(context)


class CustomerAutocomplete(Select2QuerySetAPIView):
    queryset = models.Customer.objects.all().order_by('cust_name')

    def get_queryset(self):
        customers = models.Customer.objects.filter(
            is_actual=True
        ).order_by('cust_name')

        if self.q:
            customers = customers.filter(cust_name__icontains=self.q)

        return customers


class WorkerByCustomerAutocomplete(Select2QuerySetAPIView):
    queryset = models.Worker.objects.all()

    def get_queryset(self):
        return workers_for_customer(self)


class AdministrationCostTypeAutocomplete(Select2QuerySetAPIView):
    queryset = models.AdministrationCostType.objects.all().order_by('name')

    def get_queryset(self):
        return administration_cost_types(self)


class IndustrialCostTypeAutocomplete(Select2QuerySetAPIView):
    queryset = models.IndustrialCostType.objects.all().order_by('name')

    def get_queryset(self):
        return industrial_cost_types(self)


class MaterialAutocomplete(Select2QuerySetAPIView):
    queryset = models.MaterialType.objects.all().order_by('pk')

    def get_queryset(self):
        return materials(self)

    def get_result_label(self, item):
        return item.name
