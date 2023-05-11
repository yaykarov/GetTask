from .models import HrSiteAccount, HrSiteReport, HrSiteAdv


from finance.models import Account as FinanceAccount

from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponse, HttpResponseRedirect
from django.urls import reverse
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from dal import autocomplete

from django.http import JsonResponse

import collections

class HrManagerAutocomplete(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        if not self.request.user.is_authenticated:
            return HrSiteAccount.objects.none()

        managers = HrSiteAccount.objects.all()

        """if self.q:
            workers = workers.filter(
                Q(name__icontains=self.q) |
                Q(last_name__icontains=self.q) |
                Q(patronymic__icontains=self.q) |
                Q(workerpassport__another_passport_number__icontains=self.q)
            ).distinct()"""

        return managers
