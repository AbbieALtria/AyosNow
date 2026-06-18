from django.test import TestCase


class ProviderPortalTests(TestCase):
    def test_provider_page_loads(self):
        response = self.client.get("/provider/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "AyosNow Provider")
        self.assertContains(response, "Request payout")
