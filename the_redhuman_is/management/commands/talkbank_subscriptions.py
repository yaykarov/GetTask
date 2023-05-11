from django.core.management.base import BaseCommand

from the_redhuman_is.async_utils.talk_bank.talk_bank import (
    create_talk_bank_client,
    SubscriptionStatus,
    TalkBankClient,
)


def print_subscriptions(subscriptions: SubscriptionStatus) -> None:
    if len(subscriptions.enabled) == 0:
        print('Установленных подписок нет')
    else:
        print('Установленные подписки:')
        for subscription in subscriptions.enabled:
            print(f'Id: {subscription.id}, url: {subscription.url}, событие: {subscription.event}')

    print('Доступные события для подписки:')
    print(subscriptions.available)


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('--list', required=False, action='store_true', help='Показать список подписок')
        parser.add_argument('--add_url', type=str, required=False, help='Подписать вебхук ADD_URL')
        parser.add_argument('--event', type=str, required=False, nargs='+', help='Уточнить события для подписки')
        parser.add_argument('--remove_id', type=str, required=False, help='Удалить подписку с данным Id')

    def handle(self, *args, **options):
        client: TalkBankClient = create_talk_bank_client()
        if options['list']:
            subscriptions = client.get_event_subscriptions()
            print_subscriptions(subscriptions)
        elif options['add_url'] is not None:
            events = []
            if options['event'] is not None:
                events = options['event']
            subscriptions = client.subscribe_for_events(url=options['add_url'], events=events)
            print_subscriptions(subscriptions)
        elif options['remove_id'] is not None:
            subscriptions = client.delete_subscription(subscription_id=options['remove_id'])
            print_subscriptions(subscriptions)
