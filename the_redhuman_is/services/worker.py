from datetime import timedelta
from typing import (
    Optional,
    cast,
)

from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import (
    Case,
    Count,
    Exists,
    ExpressionWrapper,
    F,
    FloatField,
    IntegerField,
    OuterRef,
    Subquery,
    Value,
    When,
)
from django.db.models.functions import Coalesce
from django.utils import timezone

from finance.models import Account
from the_redhuman_is.models.delivery import (
    ItemWorker,
    OnlineSignup,
    OnlineStatusMark,
    RequestWorkerTurnout,
)
from the_redhuman_is.models.worker import (
    Worker,
    WorkerRating,
    WorkerUser,
)
from the_redhuman_is.services import catch_lock_error
from the_redhuman_is.services.delivery import utils


@catch_lock_error
def _worker_lock(worker_id: int):
    try:
        worker = Worker.objects.select_for_update(
            nowait=True
        ).filter_mobile(
        ).get(
            pk=worker_id
        )
    except Worker.DoesNotExist:
        raise utils.ObjectNotFoundError(f'Работник {worker_id} не найден.')

    return worker


def get_accounts_for_workers(worker_ids):
    accounts = Account.objects.filter(
        worker_account__worker__in=worker_ids
    ).annotate(
        worker_id=F('worker_account__worker')
    )
    return {a.worker_id: a for a in accounts}


def update_reliability(interval=30, worker_ids=None):
    today = timezone.localdate()
    date_interval = (today - timedelta(days=interval), today - timedelta(days=1))

    ratings = WorkerRating.objects.annotate(
        signup_turnouts=Coalesce(
            Subquery(
                OnlineSignup.objects.filter(
                    worker=OuterRef('worker'),
                    date__range=date_interval,
                ).annotate(
                    has_turnout=Exists(
                        RequestWorkerTurnout.objects.filter(
                            requestworker__worker=OuterRef('worker'),
                            requestworker__request__date__range=date_interval,
                            requestworker__request__date=OuterRef('date'),
                        )
                    )
                ).filter(
                    has_turnout=True,
                ).values(
                    'worker'
                ).annotate(
                    Count('pk'),
                ).values(
                    'pk__count',
                ),
            ),
            0,
            output_field=FloatField()
        ),
        signups=Coalesce(
            Subquery(
                OnlineSignup.objects.filter(
                    worker=OuterRef('worker')
                ).values(
                    'worker'
                ).annotate(
                    Count('pk'),
                ).values(
                    'pk__count',
                ),
            ),
            0,
            output_field=FloatField(),
        ),
        no_assignments=Coalesce(
            Subquery(
                OnlineSignup.objects.filter(
                    worker=OuterRef('worker')
                ).annotate(
                    has_turnout=Exists(
                        RequestWorkerTurnout.objects.filter(
                            requestworker__worker=OuterRef('worker'),
                            requestworker__request__date__range=date_interval,
                            requestworker__request__date=OuterRef('date'),
                        )
                    ),
                    has_assignments=Exists(
                        ItemWorker.objects.filter(
                            requestworker__worker=OuterRef('worker'),
                            requestworker__request__date__range=date_interval,
                            requestworker__request__date=OuterRef('date'),
                        )
                    )
                ).filter(
                    has_turnout=False,
                    has_assignments=False,
                ).values(
                    'worker'
                ).annotate(
                    Count('pk'),
                ).values(
                    'pk__count',
                ),
            ),
            0,
            output_field=FloatField(),
        )
    ).annotate(
        assigned_signups=ExpressionWrapper(
            F('signups') - F('no_assignments'),
            output_field=IntegerField()
        )
    ).annotate(
        online_reliability=Case(
            When(
                assigned_signups=0,
                then=Value(5.),
            ),
            default=ExpressionWrapper(
                Value(5.) * F('signup_turnouts') / F('assigned_signups'),
                output_field=FloatField()
            )
        ),
    )
    if worker_ids:
        ratings = ratings.filter(
            worker__in=worker_ids
        )

    ratings.update(reliability=F('online_reliability'))


class NoWorkPermit(Exception):
    pass


def update_worker_rating(worker_id, field, value):
    with transaction.atomic():
        _worker_lock(worker_id)
        WorkerRating.objects.update_or_create(
            worker_id=worker_id,
            defaults={
                field: value,
            }
        )


def update_online_status(
        is_online: bool,
        author: User,
        worker_id: Optional[int] = None,
        workeruser: Optional[WorkerUser] = None,
):
    if worker_id is None:
        user_id = workeruser.user_id
        worker_id = cast(int, workeruser.worker_id)
    else:
        user_id = None

    with transaction.atomic():
        worker = _worker_lock(worker_id)
        if user_id is None:
            user_id = worker.workeruser.user_id

        if (
            hasattr(worker, 'banned') or
            not utils.is_citizenship_migration_ok(
                worker,
                deadline=timezone.localdate() + timedelta(days=1)
            )
        ):
            raise NoWorkPermit

        timestamp = timezone.now()
        planned_date = timezone.localdate(value=timestamp) + timedelta(days=1)

        OnlineStatusMark.objects.create(
            user_id=user_id,
            online=is_online,
            timestamp=timestamp,
            author=author,
        )
        if is_online:
            OnlineSignup.objects.update_or_create(
                date=planned_date,
                worker=worker,
                defaults={
                    'date': planned_date,
                }
            )
        else:
            OnlineSignup.objects.filter(date=planned_date, worker=worker).delete()

    return is_online
