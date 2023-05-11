import datetime

from django.core.management import BaseCommand
from django.utils import timezone

from the_redhuman_is import models
from the_redhuman_is import tasks


def send_message(worker, date):
    token = models.DeliveryWorkerFCMToken.objects.filter(
        user=worker.workeruser.user
    ).order_by(
        'timestamp'
    ).last()
    if token is not None:
        date_str = date.strftime(format='%d.%m')
        title = 'Заявки на завтра'
        text = f'{worker.name}, Вы готовы завтра, {date_str}, выполнять заявки?'
        tasks.send_push_notification(
            None,
            None,
            {
                'gt_action': 'gt_online_confirmation',
                'gt_title': title,
                'gt_text': text,
                'gt_yes_text': 'Готов',
                'gt_no_text': 'Нет',
            },
            'online_status_mark',
            token.token
        )


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('--zone', type=str, required=True)

    def handle(self, *args, **options):
        zone = models.ZoneGroup.objects.values('pk', 'weekendrest').get(code=options['zone'])

        weekday_now = timezone.localdate().isoweekday()
        # Friday or Saturday
        if weekday_now == 5 or weekday_now == 6 and zone['weekendrest'] is not None:
            return

        workers = models.Worker.objects.all(
        ).with_is_online_tomorrow(
        ).filter(
            workerzone__zone=zone['pk'],
            banned__isnull=True,
            is_online_tomorrow=None
        )

        tomorrow = datetime.date.today() + datetime.timedelta(days=1)
        for worker in workers:
            send_message(worker, tomorrow)
