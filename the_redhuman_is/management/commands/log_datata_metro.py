import json

from django.core.management.base import BaseCommand

from the_redhuman_is import models


class Command(BaseCommand):
    def handle(self, *args, **options):
        result = {}

        for address in models.NormalizedAddress.objects.all():
            data = json.loads(address.raw_data)[0]

            metro = data['metro']
            if metro:
                for info in metro:
                    line = info['line']
                    name = info['name']

                    if line not in result:
                        result[line] = set()

                    result[line].add(name)

        with open('lines.json', 'w', encoding='utf-8') as f:
            f.write(
                json.dumps(
                    {k : list(v) for k, v in result.items()},
                    ensure_ascii=False,
                    indent=' ')
                )
