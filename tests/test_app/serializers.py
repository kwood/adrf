
from adrf.serializers import ModelSerializer

from .models import Animal


class AnimalSerializer(ModelSerializer):
    """
    Animal serializer for testing
    """
    class Meta:
        model = Animal
        fields = ['id', 'name', 'sound']