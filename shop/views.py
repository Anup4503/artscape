import razorpay
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.conf import settings
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib import messages
from django.db.models import Sum

from django.contrib.auth.models import User
from .models import Product, CartItem, Order, OrderItem, Message, UserProfile, OrderNotification, ProductReview

# Razorpay Client Initialization
try:
    razorpay_client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
except Exception as e:
    razorpay_client = None
    print(f"Razorpay Client initialization failed: {e}")

from django.core.exceptions import ValidationError

def validate_uploaded_file(uploaded_file, allowed_extensions, max_size_mb):
    if not uploaded_file:
        return True, ""
    import os
    ext = os.path.splitext(uploaded_file.name)[1].lower()
    if ext not in allowed_extensions:
        return False, f"Unsupported file type '{ext}'. Allowed extensions: {', '.join(allowed_extensions)}"
    if uploaded_file.size > max_size_mb * 1024 * 1024:
        return False, f"File size exceeds limit of {max_size_mb}MB."
    return True, ""

# 1. Product Catalog View
def home(request):
    category = request.GET.get('category', '')
    if category:
        products = Product.objects.filter(category=category, available=True)
    else:
        products = Product.objects.filter(available=True)
    
    categories = Product.CATEGORY_CHOICES
    return render(request, 'shop/home.html', {
        'products': products,
        'categories': categories,
        'selected_category': category
    })

def product_detail(request, pk):
    product = get_object_or_404(Product, pk=pk)
    return render(request, 'shop/product_detail.html', {'product': product})

# 2. Authentication Views
def register_view(request):
    if request.user.is_authenticated:
        return redirect('home')
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        email = request.POST.get('email', '').strip()
        
        from django.core.validators import validate_email
        try:
            validate_email(email)
        except ValidationError:
            messages.error(request, "Please enter a valid email address.")
            return render(request, 'shop/register.html', {
                'form': form,
                'email': request.POST.get('email', ''),
                'address': request.POST.get('address', '')
            })
            
        if User.objects.filter(email=email).exists():
            messages.error(request, "This email is already registered.")
            return render(request, 'shop/register.html', {
                'form': form,
                'email': request.POST.get('email', ''),
                'address': request.POST.get('address', '')
            })
            
        if form.is_valid():
            import random
            otp = str(random.randint(100000, 999999))
            
            request.session['reg_data'] = {
                'username': form.cleaned_data.get('username'),
                'password': request.POST.get('password1'),
                'email': email,
                'address': request.POST.get('address', ''),
                'otp': otp
            }
            
            from django.core.mail import send_mail
            email_body = f"Hello {form.cleaned_data.get('username')},\n\nYour OTP for registration on Art-Scape Studio is: {otp}\n\nPlease enter this on the verification screen to activate your account."
            try:
                send_mail(
                    'Art-Scape Studio Registration OTP',
                    email_body,
                    settings.DEFAULT_FROM_EMAIL,
                    [email],
                    fail_silently=False,
                )
            except Exception as e:
                print(f"Failed to send registration email: {e}")
            
            print(f"\n=========================================\n[EMAIL SIMULATION] Sending OTP {otp} to {email}\n=========================================\n")
            messages.success(request, f"OTP sent to {email}.")
            return redirect('verify_registration_otp')
    else:
        form = UserCreationForm()
    return render(request, 'shop/register.html', {'form': form})

def verify_registration_otp(request):
    reg_data = request.session.get('reg_data')
    if not reg_data:
        messages.error(request, "Registration session expired. Please register again.")
        return redirect('register')
        
    if request.method == 'POST':
        otp_entered = request.POST.get('otp', '').strip()
        if otp_entered == reg_data['otp']:
            username = reg_data['username']
            password = reg_data['password']
            email = reg_data['email']
            address = reg_data['address']
            
            user = User.objects.create_user(username=username, password=password, email=email)
            profile = user.profile
            profile.address = address
            profile.save()
            
            login(request, user)
            messages.success(request, "Registration successful!")
            del request.session['reg_data']
            return redirect('home')
        else:
            messages.error(request, "Invalid OTP. Please try again.")
            
    context = {'email': reg_data['email']}
    if settings.DEBUG:
        context['otp_helper'] = reg_data['otp']
    return render(request, 'shop/otp_verify.html', context)

def forget_password_view(request):
    if request.user.is_authenticated:
        return redirect('home')
    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        
        from django.core.validators import validate_email
        try:
            validate_email(email)
        except ValidationError:
            messages.error(request, "Please enter a valid email address.")
            return render(request, 'shop/forget_password.html')
            
        user = User.objects.filter(email=email).first()
        
        import random
        otp = str(random.randint(100000, 999999))
        
        # Mask email (e.g. u***r@domain.com)
        if email and '@' in email:
            parts = email.split('@')
            username_part = parts[0]
            domain_part = parts[1]
            if len(username_part) > 2:
                masked_username = username_part[0] + '*' * (len(username_part) - 2) + username_part[-1]
            else:
                masked_username = username_part[0] + '*'
            masked_email = f"{masked_username}@{domain_part}"
        else:
            masked_email = email
            
        if user:
            request.session['reset_data'] = {
                'otp': otp,
                'user_id': user.id,
                'email': email,
                'masked_email': masked_email
            }
            
            from django.core.mail import send_mail
            email_body = f"Hello,\n\nYou requested a password reset. Your OTP is: {otp}\n\nPlease enter this on the verification screen to proceed with resetting your password."
            try:
                send_mail(
                    'Art-Scape Studio Password Reset OTP',
                    email_body,
                    settings.DEFAULT_FROM_EMAIL,
                    [email],
                    fail_silently=False,
                )
            except Exception as e:
                print(f"Failed to send reset email: {e}")
                
            print(f"\n=========================================\n[EMAIL SIMULATION] Sending Forget Password OTP {otp} to {email}\n=========================================\n")
        else:
            # Dummy payload to protect user validation privacy
            request.session['reset_data'] = {
                'otp': '999999',
                'user_id': None,
                'email': email,
                'masked_email': masked_email
            }
            print(f"\n=========================================\n[EMAIL SIMULATION] User with email {email} not found. Simulated dummy OTP sent.\n=========================================\n")
            
        messages.success(request, "An OTP has been sent successfully to your registered email address.")
        return redirect('forget_password_verify')
        
    return render(request, 'shop/forget_password.html')

def forget_password_verify(request):
    reset_data = request.session.get('reset_data')
    if not reset_data:
        messages.error(request, "Reset session expired or invalid. Please start again.")
        return redirect('forget_password')
        
    if request.method == 'POST':
        otp_entered = request.POST.get('otp', '').strip()
        if otp_entered == reset_data['otp'] and reset_data['user_id'] is not None:
            request.session['reset_validated'] = reset_data['user_id']
            del request.session['reset_data']
            messages.success(request, "OTP validated. Please set your new password.")
            return redirect('reset_password')
        else:
            messages.error(request, "Invalid OTP or validation expired.")
            
    context = {'masked_email': reset_data['masked_email']}
    if settings.DEBUG:
        context['otp_helper'] = reset_data['otp']
    return render(request, 'shop/forget_password_verify.html', context)


def reset_password_view(request):
    user_id = request.session.get('reset_validated')
    if not user_id:
        messages.error(request, "Unauthorized password reset attempt.")
        return redirect('login')
        
    user = get_object_or_404(User, id=user_id)
    if request.method == 'POST':
        password = request.POST.get('password', '').strip()
        password_confirm = request.POST.get('password_confirm', '').strip()
        
        if len(password) < 6:
            messages.error(request, "Password must be at least 6 characters.")
            return render(request, 'shop/reset_password.html')
            
        if password != password_confirm:
            messages.error(request, "Passwords do not match.")
            return render(request, 'shop/reset_password.html')
            
        user.set_password(password)
        user.save()
        del request.session['reset_validated']
        messages.success(request, "Password reset successful! Please login with your new password.")
        return redirect('login')
        
    return render(request, 'shop/reset_password.html')


def login_view(request):
    if request.user.is_authenticated:
        return redirect('home')
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            if user is not None:
                login(request, user)
                messages.success(request, f"Welcome back, {username}!")
                next_url = request.GET.get('next', 'home')
                return redirect(next_url)
        else:
            messages.error(request, "Invalid username or password.")
    else:
        form = AuthenticationForm()
    return render(request, 'shop/login.html', {'form': form})

def logout_view(request):
    logout(request)
    messages.info(request, "Logged out successfully.")
    return redirect('home')

# 3. Shopping Cart Views
@login_required
def cart_detail(request):
    cart_items = CartItem.objects.filter(user=request.user)
    total_amount = sum(item.get_total_price() for item in cart_items)
    return render(request, 'shop/cart.html', {
        'cart_items': cart_items,
        'total_amount': total_amount
    })

@login_required
def add_to_cart(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    quantity = int(request.POST.get('quantity', 1))
    cart_item, created = CartItem.objects.get_or_create(user=request.user, product=product)
    if not created:
        cart_item.quantity += quantity
    else:
        cart_item.quantity = quantity
    cart_item.save()
    messages.success(request, f"{product.name} added to cart.")
    return redirect('cart_detail')

@login_required
def remove_from_cart(request, item_id):
    cart_item = get_object_or_404(CartItem, id=item_id, user=request.user)
    cart_item.delete()
    messages.info(request, "Item removed from cart.")
    return redirect('cart_detail')

@login_required
def update_cart_quantity(request, item_id):
    cart_item = get_object_or_404(CartItem, id=item_id, user=request.user)
    if request.method == 'POST':
        quantity = int(request.POST.get('quantity', 1))
        if quantity > 0:
            cart_item.quantity = quantity
            cart_item.save()
            return JsonResponse({'success': True, 'item_total': cart_item.get_total_price()})
        else:
            cart_item.delete()
            return JsonResponse({'success': True, 'item_removed': True})
    return JsonResponse({'success': False})

# 4. Checkout and Razorpay payments
@login_required
def checkout(request):
    cart_items = CartItem.objects.filter(user=request.user)
    if not cart_items.exists():
        messages.warning(request, "Your cart is empty.")
        return redirect('home')
    
    total_amount = sum(item.get_total_price() for item in cart_items)
    phone = getattr(request.user.profile, 'phone', '')
    address = getattr(request.user.profile, 'address', '')
    
    if request.method == 'POST':
        name = request.POST.get('name')
        email = request.POST.get('email')
        phone = request.POST.get('phone')
        address = request.POST.get('address')
        custom_text = request.POST.get('custom_text', '')
        custom_voice = request.FILES.get('custom_voice', None)
        
        if custom_voice:
            voice_allowed = ['.mp3', '.wav', '.m4a', '.ogg', '.webm']
            is_valid, err_msg = validate_uploaded_file(custom_voice, voice_allowed, 10)
            if not is_valid:
                messages.error(request, err_msg)
                return render(request, 'shop/checkout.html', {
                    'cart_items': cart_items,
                    'total_amount': total_amount,
                    'phone': phone,
                    'address': address
                })
        
        # Save order
        order = Order.objects.create(
            user=request.user,
            name=name,
            email=email,
            phone=phone,
            address=address,
            total_amount=total_amount,
            custom_text=custom_text,
            custom_voice=custom_voice,
            status='Pending',
            payment_status='Pending'
        )
        
        # Save order items
        for item in cart_items:
            OrderItem.objects.create(
                order=order,
                product=item.product,
                name=item.product.name,
                price=item.product.price,
                quantity=item.quantity
            )
        
        # Clear Cart
        cart_items.delete()
        
        # Construct UPI QR Code Link
        from urllib.parse import quote
        upi_id = getattr(settings, 'UPI_ID', 'artscape@upi')
        upi_merchant = getattr(settings, 'UPI_MERCHANT_NAME', 'Art-Scape Studio')
        upi_link = f"upi://pay?pa={upi_id}&pn={quote(upi_merchant)}&am={order.total_amount}&cu=INR&tn={quote(f'Order #{order.id}')}"
        
        # Render payment processing screen with UPI details
        return render(request, 'shop/payment.html', {
            'order': order,
            'amount': order.total_amount,
            'upi_id': upi_id,
            'merchant_name': upi_merchant,
            'upi_link': upi_link,
            'user': request.user
        })
        
    return render(request, 'shop/checkout.html', {
        'cart_items': cart_items,
        'total_amount': total_amount,
        'phone': phone,
        'address': address
    })

@login_required
@csrf_exempt
def payment_verify(request):
    if request.method == 'POST':
        upi_transaction_id = request.POST.get('upi_transaction_id', '').strip()
        local_order_id = request.POST.get('local_order_id')
        
        order = get_object_or_404(Order, id=local_order_id)
        
        # Enforce order ownership checks
        if order.user != request.user:
            return JsonResponse({'verified': False, 'error': 'Unauthorized order access'}, status=403)
            
        # If it's a mock completion
        is_mock = request.POST.get('is_mock', 'false') == 'true'
        
        if is_mock:
            if not settings.DEBUG:
                return JsonResponse({'verified': False, 'error': 'Mock payments only allowed in development'}, status=400)
            order.payment_status = 'Paid'
            order.payment_method = 'UPI'
            order.upi_transaction_id = 'mock_upi_' + str(order.id)
            order.save()
            return JsonResponse({'verified': True})
            
        if not upi_transaction_id:
            return JsonResponse({'verified': False, 'error': 'UPI Transaction ID is required'}, status=400)
            
        # Basic validation: length 8 to 20, alphanumeric
        import re
        if not re.match(r'^[a-zA-Z0-9]{8,20}$', upi_transaction_id):
            return JsonResponse({'verified': False, 'error': 'Invalid UPI Transaction ID format'}, status=400)
            
        order.payment_method = 'UPI'
        order.upi_transaction_id = upi_transaction_id
        order.payment_status = 'Pending'
        order.save()
        return JsonResponse({'verified': True})
            
    return HttpResponse("Invalid request method", status=400)

@login_required
def order_success(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    return render(request, 'shop/order_success.html', {'order': order})

# 5. Admin & User Chat Views
@login_required
def chat_view(request):
    if request.user.is_staff:
        return redirect('admin_dashboard')
        
    messages_query = Message.objects.filter(customer=request.user)
    unread_messages = messages_query.filter(is_read=False, sender__is_staff=True)
    unread_messages.update(is_read=True) # mark admin's replies as read
    
    if request.method == 'POST':
        content = request.POST.get('content', '')
        voice_note = request.FILES.get('voice_note', None)
        attachment = request.FILES.get('attachment', None)
        
        if content or voice_note or attachment:
            # File validations
            if voice_note:
                voice_allowed = ['.mp3', '.wav', '.m4a', '.ogg', '.webm']
                is_valid, err_msg = validate_uploaded_file(voice_note, voice_allowed, 10)
                if not is_valid:
                    messages.error(request, err_msg)
                    return redirect('chat')
            if attachment:
                attach_allowed = ['.png', '.jpg', '.jpeg', '.gif', '.pdf', '.txt', '.zip']
                is_valid, err_msg = validate_uploaded_file(attachment, attach_allowed, 20)
                if not is_valid:
                    messages.error(request, err_msg)
                    return redirect('chat')
            
            Message.objects.create(
                customer=request.user,
                sender=request.user,
                content=content,
                voice_note=voice_note,
                attachment=attachment
            )
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({'success': True})
            return redirect('chat')
            
    return render(request, 'shop/chat.html', {
        'chat_messages': messages_query,
    })

# 6. Admin Panel Dashboard Views
@staff_member_required
def admin_dashboard(request):
    # Total stats
    total_orders = Order.objects.count()
    paid_orders = Order.objects.filter(payment_status='Paid').count()
    total_sales = Order.objects.filter(payment_status='Paid').aggregate(Sum('total_amount'))['total_amount__sum'] or 0.00
    
    # Active orders
    pending_orders = Order.objects.all().order_by('-created_at')
    
    # Products catalog items
    products = Product.objects.all().order_by('-created_at')
    
    # Get active customer chat threads (group messages by unique user)
    # Finding users who have messaged the admin
    chat_users = User.objects.filter(chat_messages__isnull=False).distinct()
    
    # Admin Post Triggers
    if request.method == 'POST':
        if 'add_product' in request.POST:
            name = request.POST.get('name')
            description = request.POST.get('description')
            price = request.POST.get('price')
            category = request.POST.get('category')
            image = request.FILES.get('image')
            
            if name and price and image:
                Product.objects.create(
                    name=name,
                    description=description,
                    price=price,
                    category=category,
                    image=image
                )
                messages.success(request, "Art Product successfully posted to the store.")
                return redirect('admin_dashboard')
        
        elif 'mark_paid' in request.POST:
            order_id = request.POST.get('order_id')
            order = get_object_or_404(Order, id=order_id)
            order.payment_status = 'Paid'
            order.save()
            
            # Create internal order status validation notification
            if order.user:
                OrderNotification.objects.create(
                    user=order.user,
                    order=order,
                    message=f"Your payment for Order #{order.id} has been validated by Admin successfully!"
                )
            
            # Print console notification simulated SMS
            print(f"\n=========================================\n[SMS SIMULATION] Dispatching to {order.phone}:\nYour payment of INR {order.total_amount} for Order #{order.id} has been validated! We are starting work on your order.\n=========================================\n")
            
            messages.success(request, f"Order #{order.id} has been marked as Paid successfully. Notification sent.")
            return redirect('admin_dashboard')
            
        elif 'update_status' in request.POST:
            order_id = request.POST.get('order_id')
            new_status = request.POST.get('status')
            order = get_object_or_404(Order, id=order_id)
            if new_status in dict(Order.STATUS_CHOICES):
                order.status = new_status
                order.save()
                messages.success(request, f"Order #{order.id} processing status updated.")
            else:
                messages.error(request, "Invalid order status value.")
            return redirect('admin_dashboard')
            
    return render(request, 'shop/admin_dashboard.html', {
        'total_orders': total_orders,
        'paid_orders': paid_orders,
        'total_sales': total_sales,
        'orders': pending_orders,
        'products': products,
        'chat_users': chat_users,
        'categories': Product.CATEGORY_CHOICES
    })

@staff_member_required
def admin_chat_thread(request, user_id):
    customer = get_object_or_404(User, id=user_id)
    messages_query = Message.objects.filter(customer=customer)
    
    # Mark user's messages as read
    unread_messages = messages_query.filter(is_read=False, sender__is_staff=False)
    unread_messages.update(is_read=True)
    
    if request.method == 'POST':
        content = request.POST.get('content', '')
        voice_note = request.FILES.get('voice_note', None)
        attachment = request.FILES.get('attachment', None)
        
        if content or voice_note or attachment:
            # File validations
            if voice_note:
                voice_allowed = ['.mp3', '.wav', '.m4a', '.ogg', '.webm']
                is_valid, err_msg = validate_uploaded_file(voice_note, voice_allowed, 10)
                if not is_valid:
                    messages.error(request, err_msg)
                    return redirect('admin_chat_thread', user_id=customer.id)
            if attachment:
                attach_allowed = ['.png', '.jpg', '.jpeg', '.gif', '.pdf', '.txt', '.zip']
                is_valid, err_msg = validate_uploaded_file(attachment, attach_allowed, 20)
                if not is_valid:
                    messages.error(request, err_msg)
                    return redirect('admin_chat_thread', user_id=customer.id)
            
            Message.objects.create(
                customer=customer,
                sender=request.user, # admin
                content=content,
                voice_note=voice_note,
                attachment=attachment
            )
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({'success': True})
            return redirect('admin_chat_thread', user_id=customer.id)
            
    return render(request, 'shop/admin_chat.html', {
        'customer': customer,
        'chat_messages': messages_query
    })

@login_required
def previous_orders_view(request):
    orders = Order.objects.filter(user=request.user).order_by('-created_at')
    notifications = OrderNotification.objects.filter(user=request.user, is_read=False)
    notifications_list = list(notifications)
    notifications.update(is_read=True)
    return render(request, 'shop/previous_orders.html', {
        'orders': orders,
        'notifications': notifications_list
    })

@login_required
def cancel_order_view(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    if order.status == 'Pending':
        order.status = 'Cancelled'
        order.save()
        messages.success(request, f"Order #{order.id} has been cancelled successfully.")
    else:
        messages.error(request, f"Order #{order.id} cannot be cancelled as work has already started.")
    return redirect('previous_orders')

@login_required
def invoice_view(request, order_id):
    if request.user.is_staff:
        order = get_object_or_404(Order, id=order_id)
    else:
        order = get_object_or_404(Order, id=order_id, user=request.user)
    return render(request, 'shop/invoice.html', {'order': order})

@login_required
def get_messages_api(request):
    messages_query = Message.objects.filter(customer=request.user).order_by('created_at')
    unread_messages = messages_query.filter(is_read=False, sender__is_staff=True)
    unread_messages.update(is_read=True)
    
    data = []
    for msg in messages_query:
         voice_url = msg.voice_note.url if msg.voice_note else ''
         attach_url = msg.attachment.url if msg.attachment else ''
         attach_name = msg.attachment.name.split('/')[-1] if msg.attachment else ''
         
         data.append({
             'id': msg.id,
             'is_staff': msg.sender.is_staff,
             'sender': msg.sender.username,
             'content': msg.content,
             'voice_note': voice_url,
             'attachment': attach_url,
             'attachment_name': attach_name,
             'created_at': msg.created_at.strftime('%I:%M %p')
         })
    return JsonResponse({'messages': data})

@staff_member_required
def admin_get_messages_api(request, user_id):
    customer = get_object_or_404(User, id=user_id)
    messages_query = Message.objects.filter(customer=customer).order_by('created_at')
    unread_messages = messages_query.filter(is_read=False, sender__is_staff=False)
    unread_messages.update(is_read=True)
    
    data = []
    for msg in messages_query:
         voice_url = msg.voice_note.url if msg.voice_note else ''
         attach_url = msg.attachment.url if msg.attachment else ''
         attach_name = msg.attachment.name.split('/')[-1] if msg.attachment else ''
         
         data.append({
             'id': msg.id,
             'is_staff': msg.sender.is_staff,
             'sender': msg.sender.username,
             'content': msg.content,
             'voice_note': voice_url,
             'attachment': attach_url,
             'attachment_name': attach_name,
             'created_at': msg.created_at.strftime('%I:%M %p')
         })
    return JsonResponse({'messages': data})

@staff_member_required
def admin_edit_product(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    if request.method == 'POST':
        name = request.POST.get('name')
        description = request.POST.get('description')
        price = request.POST.get('price')
        category = request.POST.get('category')
        image = request.FILES.get('image')
        available = request.POST.get('available') == 'on'
        
        if name and price:
            if image:
                is_valid, err_msg = validate_uploaded_file(image, ['.jpg', '.jpeg', '.png', '.gif', '.webp'], 5)
                if not is_valid:
                    messages.error(request, err_msg)
                    return render(request, 'shop/admin_edit_product.html', {
                        'product': product,
                        'categories': Product.CATEGORY_CHOICES
                    })
                product.image = image
            
            product.name = name
            product.description = description
            product.price = price
            product.category = category
            product.available = available
            product.save()
            messages.success(request, f"Product '{name}' successfully updated.")
            return redirect('admin_dashboard')
        else:
            messages.error(request, "Name and Price are required fields.")
            
    return render(request, 'shop/admin_edit_product.html', {
        'product': product,
        'categories': Product.CATEGORY_CHOICES
    })

@staff_member_required
def admin_delete_product(request, product_id):
    if request.method == 'POST':
        product = get_object_or_404(Product, id=product_id)
        product_name = product.name
        product.delete()
        messages.success(request, f"Product '{product_name}' has been deleted successfully.")
    return redirect('admin_dashboard')



