from django.test import TestCase


class OpsPortalTests(TestCase):
    def test_ops_page_loads(self):
        response = self.client.get("/ops/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "AyosNow Ops")
        self.assertContains(response, "Complaints")
        self.assertContains(response, "Finance")
