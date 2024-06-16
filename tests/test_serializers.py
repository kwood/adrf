import asyncio

from django.test import TestCase

from .test_app.models import Animal
from .test_app.serializers import AnimalSerializer
from rest_framework.exceptions import ValidationError
import pytest


class AsyncSerializerTests(TestCase):
    """
    Tests for AsyncSerializer
    """
    @pytest.mark.asyncio
    async def async_test_create(self):
        """
        Test creating an instance using AsyncSerializer
        """
        data = {
            'name': 'Bird',
            'sound': 'tweet'
        }
        serializer = AnimalSerializer(data=data)
        await serializer.is_valid_async(raise_exception=True)
        instance = await serializer.asave()
        self.assertIsNotNone(instance)
        self.assertEqual(instance.name, 'Bird')
        self.assertEqual(instance.sound, 'tweet')

    @pytest.mark.asyncio
    async def async_test_missing_fields(self):
        """
        Test creating an instance using AsyncSerializer with missing required fields
        """
        data = {
            'name': 'Bird',
        }
        serializer = AnimalSerializer(data=data)
        with self.assertRaises(ValidationError):
            await serializer.is_valid_async(raise_exception=True)

    @pytest.mark.asyncio
    async def async_test_update(self):
        """
        Test updating an instance using AsyncSerializer
        """
        animal = await Animal.objects.acreate(name='Lion', sound='Roar')
        data = {'name': 'Cat', 'sound': 'purr'}
        serializer = AnimalSerializer(animal, data=data, partial=True)
        await serializer.is_valid_async(raise_exception=True)
        updated_instance = await serializer.asave()
        self.assertIsNotNone(updated_instance)
        self.assertEqual(updated_instance.name, 'Cat')
        self.assertEqual(updated_instance.sound, 'purr')

    # def test_async_serializer(self):
    #     asyncio.run(self.async_test_create())
    #     asyncio.run(self.async_test_update())