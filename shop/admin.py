from django.contrib import admin
from .models import UserProfile, Product, CartItem, Order, OrderItem, Message

class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'price', 'available', 'created_at')
    list_filter = ('category', 'available')
    search_fields = ('name', 'description')

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'total_amount', 'status', 'payment_status', 'created_at')
    list_filter = ('status', 'payment_status', 'created_at')
    search_fields = ('name', 'email', 'phone', 'razorpay_order_id')
    inlines = [OrderItemInline]

@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('customer', 'sender', 'created_at', 'is_read')
    list_filter = ('is_read', 'created_at')
    search_fields = ('customer__username', 'sender__username', 'content')

admin.site.register(UserProfile)
admin.site.register(CartItem)
