from django.test import SimpleTestCase

from the_redhuman_is.services import app_flavors


class AppFlavorTest(SimpleTestCase):
    def test_default_flavor(self):
        self.assertEqual(
            app_flavors.APP_FLAVOR,
            app_flavors.AppFlavor('EXTERNAL_USER')
        )
