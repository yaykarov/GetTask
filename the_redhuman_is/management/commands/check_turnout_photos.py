from django.core.management.base import BaseCommand


from the_redhuman_is import models


class Command(BaseCommand):
    def handle(self, *args, **options):
        turnouts = models.RequestWorkerTurnout.objects.all()
        for turnout in turnouts:
            timesheet = turnout.workerturnout.timesheet
            if not models.get_photos(timesheet).exists():
                print(timesheet)
