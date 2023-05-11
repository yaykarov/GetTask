import io
import re
import requests

from django.contrib.contenttypes.models import ContentType

from the_redhuman_is.models.paysheet_v2 import WorkerReceipt
from the_redhuman_is.models.photo import Photo


_PATH_RX = re.compile('^.*/(.+)/print')


def fetch_receipt_image(receipt_pk):
    receipt = WorkerReceipt.objects.get(pk=receipt_pk)

    url = receipt.url.strip()

    number = _PATH_RX.match(url).group(1)

    response = requests.get(url)
    response.raise_for_status()

    photo, created = Photo.objects.get_or_create(
        content_type=ContentType.objects.get_for_model(WorkerReceipt),
        object_id=receipt.id
    )
    photo.image.save(
        f'{receipt.worker} {number}.jpg',
        io.BytesIO(response.content)
    )
    photo.save()
