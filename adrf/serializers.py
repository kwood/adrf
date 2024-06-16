
import asyncio
import traceback

from rest_framework.exceptions import ValidationError
from rest_framework.serializers import (
    ModelSerializer as DRFModelSerializer,
    ListSerializer as DRFListSerializer,
    raise_errors_on_nested_writes
)
from rest_framework.utils import model_meta
from asgiref.sync import sync_to_async
from django.db import models


class BaseAsyncSerializerMixin:
    async def is_valid(self, *, raise_exception=False):
        assert hasattr(self, 'initial_data'), (
            'Cannot call `.is_valid()` as no `data=` keyword argument was '
            'passed when instantiating the serializer instance.'
        )

        if not hasattr(self, '_validated_data'):
            try:
                self._validated_data = await self.run_validation(self.initial_data)
            except ValidationError as exc:
                self._validated_data = {}
                self._errors = exc.detail
            else:
                self._errors = {}

        if self._errors and raise_exception:
            raise ValidationError(self.errors)

        if not hasattr(self, '_data'):
            if self.instance is not None and not getattr(self, '_errors', None):
                self._data = await self.to_representation(self.instance)
            elif hasattr(self, '_validated_data') and not getattr(self, '_errors', None):
                self._data = await self.to_representation(self.validated_data)
            else:
                self._data = self.get_initial()

        return not bool(self._errors)
    
    @property
    def data(self):
        if hasattr(self, 'initial_data') and not hasattr(self, '_validated_data'):
            msg = (
                'When a serializer is passed a `data` keyword argument you '
                'must call `.is_valid()` before attempting to access the '
                'serialized `.data` representation.\n'
                'You should either call `.is_valid()` first, '
                'or access `.initial_data` instead.'
            )
            raise AssertionError(msg)
        return self._data

    async def run_validation(self, data):
        """
        A coroutine version of run_validation.
        """
        # There are sync-only methods buried deep in the validation process
        # for now, take the easy route of calling sync_to_async here — but ideally
        # we should refactor the validation process to be async-friendly.
        return await sync_to_async(self.run_validation)(data)



class ListSerializer(BaseAsyncSerializerMixin, DRFListSerializer):
    """
    Async version of DRF's ListSerializer.
    """
    async def to_representation(self, data):
        """
        List of object instances -> List of dicts of primitive datatypes.
        """
        # Dealing with nested relationships, data can be a Manager,
        # so, first get a queryset from the Manager if needed
        iterable = [d async for d in data.all()] if isinstance(data, models.Manager) else data

        return [
            self.child.to_representation(item) for item in iterable
        ]
    
    @property
    def data(self):
        ret = super().data
        return ReturnList(ret, serializer=self)

class ModelSerializer(BaseAsyncSerializerMixin, DRFModelSerializer):
    """
    Async version of DRF's ModelSerializer.
    """
    class Meta:
        list_serializer_class = ListSerializer

    async def acreate(self, validated_data):
        raise_errors_on_nested_writes('create', self, validated_data)

        ModelClass = self.Meta.model

        # Remove many-to-many relationships from validated_data.
        # They are not valid arguments to the default `.create()` method,
        # as they require that the instance has already been saved.
        info = model_meta.get_field_info(ModelClass)
        many_to_many = {}
        for field_name, relation_info in info.relations.items():
            if relation_info.to_many and (field_name in validated_data):
                many_to_many[field_name] = validated_data.pop(field_name)

        try:
            instance = await ModelClass._default_manager.acreate(**validated_data)
        except TypeError:
            tb = traceback.format_exc()
            msg = (
                'Got a `TypeError` when calling `%s.%s.create()`. '
                'This may be because you have a writable field on the '
                'serializer class that is not a valid argument to '
                '`%s.%s.create()`. You may need to make the field '
                'read-only, or override the %s.create() method to handle '
                'this correctly.\nOriginal exception was:\n %s' %
                (
                    ModelClass.__name__,
                    ModelClass._default_manager.name,
                    ModelClass.__name__,
                    ModelClass._default_manager.name,
                    self.__class__.__name__,
                    tb
                )
            )
            raise TypeError(msg)

        # Save many-to-many relationships after the instance is created.
        if many_to_many:
            for field_name, value in many_to_many.items():
                field = getattr(instance, field_name)
                field.set(value)

        return instance
    
    async def asave(self, **kwargs):
        assert 'commit' not in kwargs, (
            "'commit' is not a valid keyword argument to the 'asave()' method. "
            "If you need to access data before committing to the database then "
            "inspect 'serializer.validated_data' instead. "
            "You can also pass additional keyword arguments to 'asave()' if you "
            "need to set extra attributes on the saved model instance. "
            "For example: 'serializer.asave(owner=request.user)'.'"
        )

        validated_data = {**self.validated_data, **kwargs}

        if self.instance is not None:
            self.instance = await self.aupdate(self.instance, validated_data)
            assert self.instance is not None, (
                '`update()` did not return an object instance.'
            )
        else:
            self.instance = await self.acreate(validated_data)
            assert self.instance is not None, (
                '`create()` did not return an object instance.'
            )

        return self.instance
    
    async def aupdate(self, instance, validated_data):
        raise_errors_on_nested_writes('update', self, validated_data)
        info = model_meta.get_field_info(instance)

        # Simply set each attribute on the instance, and then save it.
        # Note that unlike `.create()` we don't need to treat many-to-many
        # relationships as being a special case. During updates we already
        # have an instance pk for the relationships to be associated with.
        m2m_fields = []
        for attr, value in validated_data.items():
            if attr in info.relations and info.relations[attr].to_many:
                m2m_fields.append((attr, value))
            else:
                setattr(instance, attr, value)

        await instance.asave()

        # Note that many-to-many fields are set after updating instance.
        # Setting m2m fields triggers signals which could potentially change
        # updated instance and we do not want it to collide with .update()
        m2m_set_tasks = [getattr(instance, field_name).aset(value) for field_name, value in m2m_fields]
        await asyncio.gather(*m2m_set_tasks)

        return instance