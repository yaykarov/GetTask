from django.test import TestCase
from model_mommy import mommy

from finance.models import Account


class AccountModelTestCase(TestCase):
    def setUp(self):
        self.ac1 = mommy.make(Account, name='t1')
        self.ac11 = mommy.make(Account, name='t2', parent=self.ac1)
        self.ac111 = mommy.make(Account, name='t3', parent=self.ac11)
        self.ac1111 = mommy.make(Account, name='t4', parent=self.ac111)
        self.ac2 = mommy.make(Account, name='t4', parent=self.ac1)

    def test_save(self):
        self.ac11.name = 'd2'
        self.ac11.save()
        self.ac1.refresh_from_db()
        self.ac2.refresh_from_db()
        self.ac11.refresh_from_db()
        self.ac111.refresh_from_db()
        self.ac1111.refresh_from_db()
        self.assertEqual(self.ac11.full_name, 't1 > d2')
        self.assertEqual(self.ac1.full_name, 't1')
        self.assertEqual(self.ac111.full_name, 't1 > d2 > t3')
        self.assertEqual(self.ac1111.full_name, 't1 > d2 > t3 > t4')
        self.assertEqual(self.ac2.full_name, 't1 > t4')

