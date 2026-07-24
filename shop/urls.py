from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('product/<int:pk>/', views.product_detail, name='product_detail'),
    
    # Auth
    path('register/', views.register_view, name='register'),
    path('register/verify-otp/', views.verify_registration_otp, name='verify_registration_otp'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('forget-password/', views.forget_password_view, name='forget_password'),
    path('forget-password/verify/', views.forget_password_verify, name='forget_password_verify'),
    path('forget-password/reset/', views.reset_password_view, name='reset_password'),

    
    # Cart
    path('cart/', views.cart_detail, name='cart_detail'),
    path('cart/add/<int:product_id>/', views.add_to_cart, name='add_to_cart'),
    path('cart/remove/<int:item_id>/', views.remove_from_cart, name='remove_from_cart'),
    path('cart/update/<int:item_id>/', views.update_cart_quantity, name='update_cart_quantity'),
    
    # Checkout & Payment
    path('checkout/', views.checkout, name='checkout'),
    path('payment/verify/', views.payment_verify, name='payment_verify'),
    path('order/success/<int:order_id>/', views.order_success, name='order_success'),
    path('previous-orders/', views.previous_orders_view, name='previous_orders'),
    path('order/cancel/<int:order_id>/', views.cancel_order_view, name='cancel_order'),
    path('order/invoice/<int:order_id>/', views.invoice_view, name='invoice_view'),
    
    # Chat
    path('chat/', views.chat_view, name='chat'),
    path('chat/get-messages/', views.get_messages_api, name='get_messages_api'),
    
    # Admin
    path('admin-dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('admin-dashboard/chat/<int:user_id>/', views.admin_chat_thread, name='admin_chat_thread'),
    path('admin-dashboard/chat/<int:user_id>/get-messages/', views.admin_get_messages_api, name='admin_get_messages_api'),
]
