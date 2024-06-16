from asgiref.sync import async_to_sync
from django.contrib.auth.models import User
from django.test import TestCase

from adrf.viewsets import ViewSet, ModelViewSet
from rest_framework import status
from rest_framework.response import Response
from rest_framework.test import APIRequestFactory
from tests.test_views import JSON_ERROR, sanitise_json_error
from tests.test_app.models import Animal
from tests.test_app.serializers import AnimalSerializer


factory = APIRequestFactory()


class BasicViewSet(ViewSet):
    def list(self, request):
        return Response({"method": "GET"})

    def create(self, request, *args, **kwargs):
        return Response({"method": "POST", "data": request.data})


class AsyncViewSet(ViewSet):
    async def list(self, request):
        return Response({"method": "GET"})

    async def create(self, request, *args, **kwargs):
        return Response({"method": "POST", "data": request.data})


class AnimalViewSet(ModelViewSet):
    queryset = Animal.objects.all()
    serializer_class = AnimalSerializer


class ViewSetIntegrationTests(TestCase):
    def setUp(self):
        self.list = BasicViewSet.as_view({"get": "list"})
        self.create = BasicViewSet.as_view({"post": "create"})

    def test_get_succeeds(self):
        request = factory.get("/")
        response = self.list(request)
        assert response.status_code == status.HTTP_200_OK
        assert response.data == {"method": "GET"}

    def test_logged_in_get_succeeds(self):
        user = User.objects.create_user("user", "user@example.com", "password")
        request = factory.get("/")
        # del is used to force the ORM to query the user object again
        del user.is_active
        request.user = user
        response = self.list(request)
        assert response.status_code == status.HTTP_200_OK
        assert response.data == {"method": "GET"}

    def test_post_succeeds(self):
        request = factory.post("/", {"test": "foo"})
        response = self.create(request)
        expected = {"method": "POST", "data": {"test": ["foo"]}}
        assert response.status_code == status.HTTP_200_OK
        assert response.data == expected

    def test_options_succeeds(self):
        request = factory.options("/")
        response = self.list(request)
        assert response.status_code == status.HTTP_200_OK

    def test_400_parse_error(self):
        request = factory.post("/", "f00bar", content_type="application/json")
        response = self.create(request)
        expected = {"detail": JSON_ERROR}
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert sanitise_json_error(response.data) == expected


class AsyncViewSetIntegrationTests(TestCase):
    def setUp(self):
        self.list = AsyncViewSet.as_view({"get": "list"})
        self.create = AsyncViewSet.as_view({"post": "create"})

    def test_get_succeeds(self):
        request = factory.get("/")
        response = async_to_sync(self.list)(request)
        assert response.status_code == status.HTTP_200_OK
        assert response.data == {"method": "GET"}

    def test_logged_in_get_succeeds(self):
        user = User.objects.create_user("user", "user@example.com", "password")
        request = factory.get("/")
        # del is used to force the ORM to query the user object again
        del user.is_active
        request.user = user
        response = async_to_sync(self.list)(request)
        assert response.status_code == status.HTTP_200_OK
        assert response.data == {"method": "GET"}

    def test_post_succeeds(self):
        request = factory.post("/", {"test": "foo"})
        response = async_to_sync(self.create)(request)
        expected = {"method": "POST", "data": {"test": ["foo"]}}
        assert response.status_code == status.HTTP_200_OK
        assert response.data == expected

    def test_options_succeeds(self):
        request = factory.options("/")
        response = async_to_sync(self.list)(request)
        assert response.status_code == status.HTTP_200_OK

    def test_400_parse_error(self):
        request = factory.post("/", "f00bar", content_type="application/json")
        response = async_to_sync(self.create)(request)
        expected = {"detail": JSON_ERROR}
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert sanitise_json_error(response.data) == expected

class AsyncModelViewSetIntegrationTests(TestCase):
    def setUp(self):
        self.list = AnimalViewSet.as_view({"get": "list"})
        self.retrieve = AnimalViewSet.as_view({"get": "retrieve"})
        self.create = AnimalViewSet.as_view({"post": "create"})
        self.update = AnimalViewSet.as_view({"put": "update"})
        self.delete = AnimalViewSet.as_view({"delete": "destroy"})

        self.animal = Animal.objects.create(name='Dog', sound='Woof')

    def test_create(self):
        request = factory.post('/', {'name': 'Wolf', 'sound': 'Howl'})
        response = async_to_sync(self.create)(request)
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['name'] == 'Wolf'
        assert response.data['sound'] == 'Howl'
        assert response.data['id'] is not None

    def test_update(self):
        request = factory.put('/', {'name': 'Dog', 'sound': 'Growl'})
        response = async_to_sync(self.update)(request, pk=self.animal.pk)
        assert response.status_code == status.HTTP_200_OK
        assert response.data['sound'] == 'Growl'

        # Test that the object was updated in the database
        request = factory.get('/')
        response = async_to_sync(self.retrieve)(request, pk=self.animal.pk)
        assert response.status_code == status.HTTP_200_OK
        assert response.data['sound'] == 'Growl'

    def test_list(self):
        request = factory.get('/')
        response = async_to_sync(self.list)(request)
        assert response.status_code == status.HTTP_200_OK
        assert response.data == [
            {'id': 1, 'name': 'Dog', 'sound': 'Woof'}
        ]
    
    def test_retrieve(self):
        request = factory.get('/')
        response = async_to_sync(self.retrieve)(request, pk=self.animal.pk)
        assert response.status_code == status.HTTP_200_OK
        assert response.data == {'id': self.animal.pk, 'name': 'Dog', 'sound': 'Woof'}

    def test_delete(self):
        request = factory.delete('/')
        response = async_to_sync(self.delete)(request, pk=self.animal.pk)
        assert response.status_code == status.HTTP_204_NO_CONTENT

        # Test that the object was deleted from the database
        request = factory.get('/')
        response = async_to_sync(self.list)(request)
        assert response.status_code == status.HTTP_200_OK
        assert response.data == []