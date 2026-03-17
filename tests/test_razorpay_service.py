import hashlib
import hmac
import unittest

from app.billing import razorpay_service


class RazorpayServiceTests(unittest.TestCase):
    def test_verify_payment_accepts_valid_signature(self):
        original_secret = razorpay_service.settings.razorpay_key_secret
        razorpay_service.settings.razorpay_key_secret = "super-secret"
        try:
            payment_id = "pay_test_123"
            signature = hmac.new(
                b"super-secret",
                payment_id.encode(),
                hashlib.sha256,
            ).hexdigest()
            self.assertTrue(razorpay_service.verify_payment(payment_id, signature))
            self.assertFalse(razorpay_service.verify_payment(payment_id, "bad-signature"))
        finally:
            razorpay_service.settings.razorpay_key_secret = original_secret


if __name__ == "__main__":
    unittest.main()
