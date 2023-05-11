from django.contrib.auth.models import User
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils import timezone


class Comment(models.Model):
    timestamp = models.DateTimeField(
        default=timezone.now
    )
    author = models.ForeignKey(
        User,
        on_delete=models.PROTECT
    )

    text = models.TextField()

    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.PROTECT,
        db_index=False,
    )
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')

    class Meta:
        indexes = [
            models.Index(
                fields=['content_type', 'object_id', '-timestamp'],
                name='comment_object_ts_idx',
            ),
        ]
