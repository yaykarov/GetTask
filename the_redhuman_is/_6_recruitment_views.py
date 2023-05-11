# -*- coding: utf-8 -*-
from .auth import staff_account_required

from .models import Worker, RecruitmentOrder, WorkersForOrder
from .forms import WorkerCommentsForm, ForHRWorkerForm

from django.shortcuts import render, redirect
from django.db.models import Q, Avg, Sum, Count

from datetime import datetime, date
import datetime


""" Подбор, главная """
#Подбор, на работе
@staff_account_required
def recruitment_at_work(request):
    orders = RecruitmentOrder.objects.filter(is_actual=True).annotate(Count('workersfororder'))
    workers = Worker.objects.filter(
    Q(workersfororder__isnull=True)|Q(workersfororder__order__is_actual=False)
    ).annotate(Count('worker_turnouts', distinct=True)
    ).filter(worker_turnouts__timesheet__is_executed=False
    ).order_by('-worker_turnouts__count')
    return render(request, 'the_redhuman_is/recruitment_at_work.html', {'orders': orders, 'workers': workers})


# Добавить рабочих в заявку
@staff_account_required
def recruitment_order(request, pk):
    order = RecruitmentOrder.objects.get(pk=pk)
    workers = Worker.objects.filter(
    Q(workersfororder__isnull=True)|Q(workersfororder__order__is_actual=False)
    ).exclude(
    worker_turnouts__timesheet__is_executed=False
    ).annotate(Count('worker_turnouts')).order_by('-worker_turnouts__count')#, Count('worker_turnouts__timesheet__sheet_turn="День"')
    wfs = WorkersForOrder.objects.filter(order=order).annotate(Count('worker__worker_turnouts'))
    if "q" in request.GET and request.GET["q"]:
        q = request.GET.get("q")
        workers = Worker.objects.filter(
        Q(workersfororder__isnull=True)|Q(workersfororder__order__is_actual=False),
        last_name__icontains=q
        ).exclude(
        worker_turnouts__timesheet__is_executed=False
        ).annotate(Count('worker_turnouts')).order_by('-worker_turnouts__count')
        return render(request, 'the_redhuman_is/recruitment_order.html', {'workers': workers, 'order': order, 'wfs': wfs})
    return render(request, 'the_redhuman_is/recruitment_order.html', {'workers': workers, 'order': order, 'wfs': wfs})


# Добавить рабочего в заявку
@staff_account_required
def add_worker_into_order(request, pk_w, pk_o):
    WorkersForOrder.objects.create(
    order = RecruitmentOrder.objects.get(pk=pk_o),
    worker = Worker.objects.get(pk=pk_w)
    )
    return redirect('the_redhuman_is:recruitment_order', pk=pk_o)


#Добавить доп. информацию(язык, где живет, желание работать у нас) по рабочему
@staff_account_required
def clarify_worker_data(request, pk):
    worker = Worker.objects.get(pk=pk)
    user = request.user
    today = datetime.date.today()
    if request.method == "POST":
        form = ForHRWorkerForm(request.POST or None)
        c_form = WorkerCommentsForm(request.POST or None)
        if form.is_valid() or c_form.is_valid():
            form = form.save(commit=False)
            worker.metro = form.metro
            worker.status = form.status
            worker.speaks_russian = form.speaks_russian
            worker.save()
            comment = c_form.save(commit=False)
            comment.worker = worker
            comment.date = today
            comment.save()
            return redirect('the_redhuman_is:recruitment')
    else:
        form = ForHRWorkerForm(instance=worker)
        c_form = WorkerCommentsForm(initial={
                'author': user
                })
        return render(request, 'the_redhuman_is/worker_to_clarify.html', {'worker': worker, 'form': form, 'c_form': c_form})
