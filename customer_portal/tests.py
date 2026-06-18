from django.test import TestCase


class CustomerPortalTests(TestCase):
    def test_app_page_loads(self):
        response = self.client.get("/app/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Book a trusted service")
        self.assertContains(response, "My bookings")
        self.assertContains(response, "Report issue")
