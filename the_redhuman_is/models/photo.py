from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils import timezone


def content_file_name(instance, filename):
    return '{}/{}/{}'.format('photo', instance.id, filename)


class Photo(models.Model):
    timestamp = models.DateTimeField(
        default=timezone.now
    )
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.PROTECT,
        null=True,
        db_index=False,
    )
    object_id = models.PositiveIntegerField(null=True)
    content_object = GenericForeignKey('content_type', 'object_id')
    image = models.ImageField(upload_to=content_file_name)

    def __str__(self):
        return 'Photo {}'.format(self.pk)

    def set_image(self, image, delete_current=True):
        if self.image and delete_current:
            self.image.delete()
        self.image = image
        self.save()

    def change_target(self, target):
        self.content_type = ContentType.objects.get_for_model(type(target))
        self.object_id = target.id
        self.save()

    class Meta:
        indexes = [
            models.Index(
                fields=['content_type', 'object_id'],
                name='photo_contenttype_object_index',
            ),
        ]


# Todo: от этого больше вреда, чем пользы, похоже
#@receiver(pre_delete, sender=Photo)
#def _photo_model_delete(sender, instance, **kwargs):
#    instance.image.delete(False)


def save_single_photo(target, image):
    photo, created = Photo.objects.get_or_create(
        content_type=ContentType.objects.get_for_model(type(target)),
        object_id=target.id
    )
    photo.set_image(image)
    return photo


def add_photo(target, image):
    photo = Photo.objects.create(
        content_type=ContentType.objects.get_for_model(type(target)),
        object_id=target.id,
    )
    photo.set_image(image)
    return photo


def get_photos(target):
    return Photo.objects.filter(
        content_type=ContentType.objects.get_for_model(type(target)),
        object_id=target.id
    )
