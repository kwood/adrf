from django.db import models


class Animal(models.Model):
    """
    Animal model for testing
    """
    name = models.CharField(max_length=100)
    sound = models.CharField(max_length=100)

    def __str__(self):
        return self.name