from django.test import TestCase
from django.urls import reverse
from django.contrib.auth.models import User
from shop.models import Product, CartItem, Order, OrderItem, Message

class ShopTests(TestCase):
    def setUp(self):
        # Create test user
        self.user = User.objects.create_user(username='testuser', password='password123')
        
        # Create test products
        self.product1 = Product.objects.create(
            name='Test Resin Coaster',
            description='A beautiful resin piece',
            price=500.00,
            category='resin',
            available=True
        )
        self.product2 = Product.objects.create(
            name='Test Oil Landscape',
            description='Volumetric cloud art',
            price=2000.00,
            category='oil',
            available=True
        )
        self.product_unavailable = Product.objects.create(
            name='Hidden Painting',
            description='Not for sale',
            price=1000.00,
            category='acrylic',
            available=False
        )

    def test_home_view(self):
        # Test basic loading
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Test Resin Coaster')
        self.assertContains(response, 'Test Oil Landscape')
        self.assertNotContains(response, 'Hidden Painting')

        # Test category filtering
        response = self.client.get(reverse('home') + '?category=resin')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Test Resin Coaster')
        self.assertNotContains(response, 'Test Oil Landscape')

    def test_product_detail_view(self):
        # Test existing product
        response = self.client.get(reverse('product_detail', args=[self.product1.id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Test Resin Coaster')

        # Test non-existent product
        response = self.client.get(reverse('product_detail', args=[999]))
        self.assertEqual(response.status_code, 404)

    def test_cart_operations(self):
        # Must be logged in
        response = self.client.post(reverse('add_to_cart', args=[self.product1.id]), {'quantity': 2})
        # Check login redirect
        self.assertEqual(response.status_code, 302)

        # Login and repeat
        self.client.login(username='testuser', password='password123')
        response = self.client.post(reverse('add_to_cart', args=[self.product1.id]), {'quantity': 2})
        self.assertEqual(response.status_code, 302) # Redirect to cart_detail
        
        # Verify CartItem created
        cart_item = CartItem.objects.get(user=self.user, product=self.product1)
        self.assertEqual(cart_item.quantity, 2)
        self.assertEqual(cart_item.get_total_price(), 1000.00)

        # Update cart quantity (via AJAX POST)
        response = self.client.post(reverse('update_cart_quantity', args=[cart_item.id]), {'quantity': 3})
        self.assertEqual(response.status_code, 200)
        cart_item.refresh_from_db()
        self.assertEqual(cart_item.quantity, 3)

        # Remove from cart
        response = self.client.get(reverse('remove_from_cart', args=[cart_item.id]))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(CartItem.objects.filter(id=cart_item.id).exists())

    def test_checkout_empty_cart(self):
        # Checkout with empty cart should redirect
        self.client.login(username='testuser', password='password123')
        response = self.client.get(reverse('checkout'))
        self.assertEqual(response.status_code, 302)

    def test_payment_verify_unauthorized_user(self):
        # Create an order for testuser
        order = Order.objects.create(
            user=self.user,
            name="Test User",
            email="test@user.com",
            phone="12345",
            address="Test",
            total_amount=100.00
        )
        
        # Create user2 and log in
        user2 = User.objects.create_user(username='user2', password='password123')
        self.client.login(username='user2', password='password123')
        
        # user2 attempts to mark testuser's order as paid
        response = self.client.post(reverse('payment_verify'), {
            'local_order_id': order.id,
            'is_mock': 'true'
        })
        self.assertEqual(response.status_code, 403)
        order.refresh_from_db()
        self.assertEqual(order.payment_status, 'Pending')

    def test_payment_verify_mock_disabled_in_production(self):
        # Create order for testuser
        order = Order.objects.create(
            user=self.user,
            name="Test User",
            email="test@user.com",
            phone="12345",
            address="Test",
            total_amount=100.00
        )
        self.client.login(username='testuser', password='password123')
        
        # Force production mode settings
        with self.settings(DEBUG=False):
            response = self.client.post(reverse('payment_verify'), {
                'local_order_id': order.id,
                'is_mock': 'true'
            })
            self.assertEqual(response.status_code, 400)
            order.refresh_from_db()
            self.assertEqual(order.payment_status, 'Pending')
            
    def test_payment_verify_upi_valid_utr(self):
        order = Order.objects.create(
            user=self.user,
            name="Test User",
            email="test@user.com",
            phone="12345",
            address="Test",
            total_amount=100.00
        )
        self.client.login(username='testuser', password='password123')
        
        response = self.client.post(reverse('payment_verify'), {
            'local_order_id': order.id,
            'upi_transaction_id': 'ABC123456789'
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['verified'], True)
        
        order.refresh_from_db()
        self.assertEqual(order.payment_method, 'UPI')
        self.assertEqual(order.upi_transaction_id, 'ABC123456789')
        self.assertEqual(order.payment_status, 'Pending')

    def test_payment_verify_upi_invalid_utr(self):
        order = Order.objects.create(
            user=self.user,
            name="Test User",
            email="test@user.com",
            phone="12345",
            address="Test",
            total_amount=100.00
        )
        self.client.login(username='testuser', password='password123')
        
        response = self.client.post(reverse('payment_verify'), {
            'local_order_id': order.id,
            'upi_transaction_id': '1'  # Too short
        })
        self.assertEqual(response.status_code, 400)
        order.refresh_from_db()
        self.assertNotEqual(order.payment_method, 'UPI')

    def test_admin_mark_order_paid(self):
        order = Order.objects.create(
            user=self.user,
            name="Test User",
            email="test@user.com",
            phone="12345",
            address="Test",
            total_amount=100.00,
            payment_method='UPI',
            upi_transaction_id='123456789012',
            payment_status='Pending'
        )
        
        # Non-staff user attempt
        self.client.login(username='testuser', password='password123')
        response = self.client.post(reverse('admin_dashboard'), {
            'mark_paid': '1',
            'order_id': order.id
        })
        self.assertEqual(response.status_code, 302)  # Redirects to login/unauthorized since not staff
        order.refresh_from_db()
        self.assertEqual(order.payment_status, 'Pending')
        
        # Staff user
        admin_user = User.objects.create_superuser(username='admin', password='password123', email='admin@test.com')
        self.client.login(username='admin', password='password123')
        
        response = self.client.post(reverse('admin_dashboard'), {
            'mark_paid': '1',
            'order_id': order.id
        })
        self.assertEqual(response.status_code, 302)  # Redirects to admin_dashboard on success
        
        order.refresh_from_db()
        self.assertEqual(order.payment_status, 'Paid')
            
    def test_checkout_invalid_file_extension(self):
        self.client.login(username='testuser', password='password123')
        # Add item to cart so checkout view doesn't redirect
        CartItem.objects.create(user=self.user, product=self.product1, quantity=1)
        
        # Attempt to upload malicious python script as voice note
        from django.core.files.uploadedfile import SimpleUploadedFile
        malicious_file = SimpleUploadedFile("exploit.py", b"print('hacked')", content_type="text/x-python")
        
        response = self.client.post(reverse('checkout'), {
            'name': 'Test User',
            'email': 'test@user.com',
            'phone': '12345',
            'address': 'Test Address',
            'custom_voice': malicious_file
        })
        self.assertEqual(response.status_code, 200) # Form re-rendered with error message
        # Verify order was not created
        self.assertEqual(Order.objects.count(), 0)

    def test_chat_invalid_file_size(self):
        self.client.login(username='testuser', password='password123')
        
        from django.core.files.uploadedfile import SimpleUploadedFile
        # Over 20MB file
        huge_file = SimpleUploadedFile("huge_image.png", b"0" * (21 * 1024 * 1024), content_type="image/png")
        
        response = self.client.post(reverse('chat'), {
            'content': 'Check this file out',
            'attachment': huge_file
        })
        self.assertEqual(response.status_code, 302) # Redirects back with request error
        # Verify message was not created
        self.assertEqual(Message.objects.count(), 0)

    def test_registration_email_otp_flow(self):
        # Request registration
        response = self.client.post(reverse('register'), {
            'username': 'newuser',
            'password1': 'newpassword123',
            'password2': 'newpassword123',
            'email': 'newuser@example.com',
            'address': '123 New St'
        })
        # Verify redirects to verify-otp
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('verify_registration_otp'))
        
        # Verify email is sent
        from django.core import mail
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Art-Scape Studio Registration OTP", mail.outbox[0].subject)
        
        # Extract OTP from session
        session = self.client.session
        reg_data = session.get('reg_data')
        self.assertIsNotNone(reg_data)
        otp = reg_data['otp']
        
        # Submit correct OTP
        response = self.client.post(reverse('verify_registration_otp'), {
            'otp': otp
        })
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('home'))
        
        # Verify user created with correct email/address
        new_user = User.objects.get(username='newuser')
        self.assertEqual(new_user.email, 'newuser@example.com')
        self.assertEqual(new_user.profile.address, '123 New St')

    def test_forget_password_email_otp_flow(self):
        # Register a user info with email
        user_with_email = User.objects.create_user(username='resetuser', password='oldpassword', email='reset@example.com')
        
        # Post forget password request
        response = self.client.post(reverse('forget_password'), {
            'email': 'reset@example.com'
        })
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('forget_password_verify'))
        
        # Verify email sent
        from django.core import mail
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Art-Scape Studio Password Reset OTP", mail.outbox[0].subject)
        
        # Get OTP from session
        session = self.client.session
        reset_data = session.get('reset_data')
        self.assertIsNotNone(reset_data)
        otp = reset_data['otp']
        
        # Verify OTP
        response = self.client.post(reverse('forget_password_verify'), {
            'otp': otp
        })
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('reset_password'))
        
        # Reset password
        response = self.client.post(reverse('reset_password'), {
            'password': 'newpassword123',
            'password_confirm': 'newpassword123'
        })
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('login'))
        
        # Verify password is changed
        self.client.logout()
        login_success = self.client.login(username='resetuser', password='newpassword123')
        self.assertTrue(login_success)



