import base64
import binascii
import uuid

from django.core.files.base import ContentFile
from rest_framework import serializers


class Base64ImageField(serializers.ImageField):
    """Decode a data URL; ImageField validates its actual image contents."""

    def to_internal_value(self, data):
        if not isinstance(data, str) or not data.startswith('data:image/'):
            raise serializers.ValidationError(
                'Передайте изображение в base64.'
            )
        try:
            header, encoded = data.split(';base64,', 1)
            if not encoded or len(encoded) > 14 * 1024 * 1024:
                raise ValueError
            decoded = base64.b64decode(encoded, validate=True)
        except (ValueError, binascii.Error):
            raise serializers.ValidationError(
                'Некорректное изображение base64.'
            )
        if len(decoded) > 10 * 1024 * 1024:
            raise serializers.ValidationError(
                'Изображение должно быть не больше 10 МБ.'
            )
        extensions = {
            'image/jpeg': 'jpg',
            'image/png': 'png',
            'image/webp': 'webp',
            'image/gif': 'gif',
        }
        extension = extensions.get(header[5:])
        if extension is None:
            raise serializers.ValidationError(
                'Поддерживаются JPEG, PNG, WebP и GIF.'
            )
        return super().to_internal_value(
            ContentFile(decoded, name=f'{uuid.uuid4().hex}.{extension}')
        )
