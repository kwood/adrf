from rest_framework.response import Response
from rest_framework import status
from rest_framework.mixins import (
    CreateModelMixin,
    ListModelMixin,
    RetrieveModelMixin,
    UpdateModelMixin,
    DestroyModelMixin,
)
from asgiref.sync import sync_to_async


class AsyncCreateModelMixin(CreateModelMixin):
    """
    Create a model instance asynchronously.
    """

    async def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        await self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    async def perform_create(self, serializer):
        await serializer.asave()


class AsyncListModelMixin:
    """
    List a queryset asynchronously.
    """

    async def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        items = await sync_to_async(getattr)(serializer, "data")
        return Response(items)


class AsyncRetrieveModelMixin:
    """
    Retrieve a model instance asynchronously.
    """

    async def retrieve(self, request, *args, **kwargs):
        instance = await self.get_object()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)


class AsyncUpdateModelMixin:
    """
    Update a model instance asynchronously.
    """

    async def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = await self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        await self.perform_update(serializer)

        if getattr(instance, "_prefetched_objects_cache", None):
            # If 'prefetch_related' has been applied to a queryset, we need to
            # forcibly invalidate the prefetch cache on the instance.
            instance._prefetched_objects_cache = {}

        return Response(serializer.data)

    async def perform_update(self, serializer):
        await serializer.asave()

    async def partial_update(self, request, *args, **kwargs):
        kwargs["partial"] = True
        return await self.aupdate(request, *args, **kwargs)


class AsyncDestroyModelMixin:
    """
    Destroy a model instance asynchronously.
    """

    async def destroy(self, request, *args, **kwargs):
        instance = await self.get_object()
        await self.perform_destroy(instance)
        return Response(status=status.HTTP_204_NO_CONTENT)

    async def perform_destroy(self, instance):
        await instance.adelete()
