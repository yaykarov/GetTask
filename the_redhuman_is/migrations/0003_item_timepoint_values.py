from datetime import timedelta

from django.db import migrations
from django.db.models import (
    DurationField,
    Exists,
    ExpressionWrapper,
    F,
    IntegerField,
    Min,
    OuterRef,
    Subquery,
    TimeField,
    Value,
)
from django.db.models.functions import (
    Cast,
    TruncMinute,
)


def assign_item_confirmed_timepoints(apps, schema_editor):
    DeliveryRequest = apps.get_model('the_redhuman_is', 'DeliveryRequest')
    DeliveryItem = apps.get_model('the_redhuman_is', 'DeliveryItem')
    DeliveryFirstAddress = apps.get_model('the_redhuman_is', 'DeliveryFirstAddress')
    DeliveryItem.objects.annotate(
        request_timepoint=Subquery(
            DeliveryRequest.objects.filter(
                id=OuterRef('request_id')
            ).values(
                'confirmed_timepoint'
            )[:1]
        ),
        not_first=~Exists(
            DeliveryFirstAddress.objects.filter(
                item=OuterRef('pk')
            )
        ),
    ).update(
        confirmed_timepoint=ExpressionWrapper(
            TruncMinute('request_timepoint') +
            ExpressionWrapper(
                Cast(F('not_first'), output_field=IntegerField()) *
                Value(timedelta(seconds=1), output_field=DurationField()),
                output_field=DurationField()
            ),
            output_field=TimeField()
        )
    )


def consolidate_confirmed_timepoints(apps, schema_editor):
    DeliveryRequest = apps.get_model('the_redhuman_is', 'DeliveryRequest')
    DeliveryItem = apps.get_model('the_redhuman_is', 'DeliveryItem')
    DeliveryFirstAddress = apps.get_model('the_redhuman_is', 'DeliveryFirstAddress')
    DeliveryRequest.objects.annotate(
        min_timepoint=Subquery(
            DeliveryItem.objects.filter(
                request=OuterRef('pk')
            ).values(
                'request'
            ).annotate(
                Min('confirmed_timepoint')
            ).values(
                'confirmed_timepoint__min'
            ),
            output_field=TimeField()
        ),
    ).update(
        confirmed_timepoint=TruncMinute('min_timepoint')
    )
    first_items = list(
        DeliveryItem.objects.annotate(
            first=Exists(
                DeliveryItem.objects.filter(
                    request=OuterRef('request'),
                    confirmed_timepoint__gt=OuterRef('confirmed_timepoint'),
                )
            )
        ).filter(
            first=True,
            # filter `deliveryfirstaddress__isnull=True,` here hangs the query
            # workaround: no filter + `ignore_conflicts=True`
        ).values_list(
            'pk',
            flat=True,
        )
    )
    DeliveryFirstAddress.objects.bulk_create(
        [
            DeliveryFirstAddress(item_id=pk)
            for pk in first_items
        ],
        ignore_conflicts=True
    )


class Migration(migrations.Migration):

    dependencies = [
        ('the_redhuman_is', '0002_deliveryitem_confirmed_timepoint'),
    ]

    operations = [
        migrations.RunPython(
            assign_item_confirmed_timepoints,
            reverse_code=consolidate_confirmed_timepoints,
        ),
    ]
