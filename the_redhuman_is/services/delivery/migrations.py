from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType

from the_redhuman_is.models import (
    Photo,
    WorkerUser,
)
from the_redhuman_is.models.delivery import (
    ArrivalLocation,
    AssignedWorker,
    AssignedWorkerAuthor,
    AssignedWorkerTurnout,
    DeliveryItem,
    DeliveryRequest,
    ItemWorker,
    ItemWorkerDiscrepancyCheck,
    ItemWorkerFinish,
    ItemWorkerFinishConfirmation,
    ItemWorkerRejection,
    ItemWorkerStart,
    ItemWorkerStartConfirmation,
    Location,
    PhotoRejectionComment,
    RequestWorker,
    RequestWorkerTurnout,
    TurnoutDiscrepancyCheck,
    TurnoutPhoto,
    WorkerConfirmation,
    WorkerRejection,
)


def location_factory(location):
    yield location

    if location is None:
        while True:
            yield None

    while True:
        yield Location.objects.create(
            timestamp=location.timestamp,
            provider=location.provider,
            latitude=location.latitude,
            longitude=location.longitude,
            time=location.time,
        )


def migrate_delivery_data():
    default_author = User.objects.get(username='admin')

    delivery_requests = DeliveryRequest.objects.all(
    ).order_by(
        'id'
    )

    for request in delivery_requests:
        requestworkers = []

        assigned_workers = AssignedWorker.objects.select_related(
            'assignedworkerauthor__author',
            'worker__workeruser__user',
            'confirmed_by',
            'turnout__turnout',
            'arrivallocation__location',
        ).filter(
            request=request
        ).order_by(
            'id'
        )
        delivery_items = DeliveryItem.objects.filter(
            request=request
        ).order_by(
            'id'
        )

        for assigned_worker in assigned_workers:
            try:
                author = assigned_worker.assignedworkerauthor.author
                timestamp = assigned_worker.assignedworkerauthor.timestamp
            except AssignedWorkerAuthor.DoesNotExist:
                author = default_author
                timestamp = request.timestamp

            try:
                workeruser_user = assigned_worker.worker.workeruser.user
            except WorkerUser.DoesNotExist:
                workeruser_user = default_author

            requestworker = RequestWorker.objects.create(
                timestamp=timestamp,
                author=author,
                request=request,
                worker=assigned_worker.worker,
            )
            requestworkers.append(requestworker)

            if assigned_worker.confirmed:
                if assigned_worker.confirmed_by is not None:
                    confirmed_by = assigned_worker.confirmed_by
                else:
                    confirmed_by = default_author
                WorkerConfirmation.objects.create(
                    timestamp=timestamp,
                    author=confirmed_by,
                    requestworker=requestworker,
                )

            try:
                assigned_worker_turnout = assigned_worker.turnout
                request_worker_turnout = RequestWorkerTurnout.objects.create(
                    timestamp=assigned_worker_turnout.timestamp,
                    requestworker=requestworker,
                    workerturnout=assigned_worker_turnout.turnout,
                )
            except AssignedWorkerTurnout.DoesNotExist:
                request_worker_turnout = None

            itemworkers = []
            for item in delivery_items:
                item = ItemWorker.objects.create(
                    timestamp=timestamp,
                    author=author,
                    item=item,
                    requestworker=requestworker,
                )
                itemworkers.append(item)

            # 7 AWs have turnouts (with positive hours) but no AL as of 2021-04-19
            try:
                arrival_location = assigned_worker.arrivallocation
            except ArrivalLocation.DoesNotExist:
                arrival_location = None

            if arrival_location is not None:
                arrival_photo = Photo.objects.filter(
                    content_type=ContentType.objects.get_for_model(ArrivalLocation),
                    object_id=arrival_location.pk,
                ).select_related(
                    'photorejectioncomment__author'
                ).first()  # at most 1 photo per AL as of 2021-04-19
                turnout_photo = TurnoutPhoto.objects.select_related(
                    'photo'
                ).filter(
                    location=arrival_location
                ).first()  # one to one, guaranteed at most 1 record per AL
                turnout_discrepancy_check = TurnoutDiscrepancyCheck.objects.filter(
                    turnout=arrival_location
                ).first()  # one to one, guaranteed at most 1 record per AL

                # iws--location is one to one
                location = location_factory(arrival_location.location)
                for itemworker in itemworkers:
                    start = ItemWorkerStart.objects.create(
                        timestamp=arrival_location.timestamp,
                        author=workeruser_user,
                        itemworker=itemworker,
                        location=next(location),
                        is_suspicious=arrival_location.is_suspicious,
                    )
                    if turnout_discrepancy_check is not None:
                        ItemWorkerDiscrepancyCheck.objects.create(
                            timestamp=turnout_discrepancy_check.timestamp,
                            author=turnout_discrepancy_check.author,
                            itemworkerstart=start,
                            is_ok=turnout_discrepancy_check.is_ok,
                            comment=turnout_discrepancy_check.comment,
                        )
                    autoconfirm = True
                    if arrival_photo is not None:
                        start_photo = Photo.objects.create(
                            content_type=ContentType.objects.get_for_model(ItemWorkerStart),
                            object_id=start.pk,
                            image=arrival_photo.image,
                            timestamp=arrival_location.timestamp,
                        )
                        try:
                            arrival_rejection_comment = arrival_photo.photorejectioncomment
                            PhotoRejectionComment.objects.create(
                                timestamp=arrival_rejection_comment.timestamp,
                                author=arrival_rejection_comment.author,
                                photo=start_photo,
                                rejection_comment=arrival_rejection_comment.rejection_comment
                            )
                            autoconfirm = False
                        except PhotoRejectionComment.DoesNotExist:
                            pass

                    if autoconfirm:
                        ItemWorkerStartConfirmation.objects.create(
                            timestamp=arrival_location.timestamp,
                            author=author,
                            itemworkerstart=start
                        )

                    if turnout_photo is not None:
                        # new photo object
                        finish_photo = Photo.objects.create(
                            content_type=ContentType.objects.get_for_model(ItemWorker),
                            object_id=itemworker.pk,
                            image=turnout_photo.photo.image,
                            timestamp=turnout_photo.timestamp,
                        )

                        # turnoutphoto photos have no rejection comments as of 2021-04-19
                        if turnout_photo.photo_rejected:
                            PhotoRejectionComment.objects.create(
                                timestamp=turnout_photo.timestamp,
                                author=default_author,
                                photo=finish_photo,
                                rejection_comment=turnout_photo.rejection_comment
                            )

                        finish = ItemWorkerFinish.objects.create(
                            timestamp=turnout_photo.timestamp,
                            author=author,
                            itemworker=itemworker,
                            # different location objects for IWS and IWF
                            location=next(location),
                            photo=finish_photo,
                        )
                        if request_worker_turnout is None:
                            finish_photo.change_target(finish)
                        else:
                            finish_photo.change_target(
                                request_worker_turnout.workerturnout.timesheet
                            )
                            ItemWorkerFinishConfirmation.objects.create(
                                timestamp=request_worker_turnout.timestamp,
                                author=default_author,
                                itemworkerfinish=finish
                            )


def delete_new_data():
    ItemWorkerFinishConfirmation.objects.all().delete()
    PhotoRejectionComment.objects.filter(
        photo__content_type=ContentType.objects.get_for_model(ItemWorkerFinish)
    ).delete()
    ItemWorkerFinish.objects.all().delete()
    Photo.objects.filter(
        content_type=ContentType.objects.get_for_model(ItemWorkerFinish)
    ).delete()
    ItemWorkerStartConfirmation.objects.all().delete()
    PhotoRejectionComment.objects.filter(
        photo__content_type=ContentType.objects.get_for_model(ItemWorkerStart)
    ).delete()
    Photo.objects.filter(
        content_type=ContentType.objects.get_for_model(ItemWorkerStart)
    ).delete()
    ItemWorkerDiscrepancyCheck.objects.all().delete()
    ItemWorkerStart.objects.all().delete()
    ItemWorkerRejection.objects.all().delete()
    ItemWorker.objects.all().delete()
    WorkerConfirmation.objects.all().delete()
    WorkerRejection.objects.all().delete()
    RequestWorkerTurnout.objects.all().delete()
    RequestWorker.objects.all().delete()
