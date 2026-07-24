import os
import django
from django.core.files import File

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'artscape.settings')
django.setup()

from django.contrib.auth.models import User
from shop.models import Product, UserProfile

def populate():
    print("Populating database...")
    import os
    admin_username = os.environ.get('DJANGO_ADMIN_USERNAME', 'admin')
    admin_password = os.environ.get('DJANGO_ADMIN_PASSWORD')
    if not admin_password:
        raise Exception("Set DJANGO_ADMIN_PASSWORD in your .env before running populate_db.py")

    if not User.objects.filter(username=admin_username).exists():
        admin = User.objects.create_superuser(admin_username, "admin@artscape.com", admin_password)
        print(f"Superuser profile '{admin_username}' created successfully with password from DJANGO_ADMIN_PASSWORD.")
    else:
        admin = User.objects.get(username=admin_username)
        print(f"Superuser '{admin_username}' already exists.")
        

    if not User.objects.filter(username="customer").exists():
        customer = User.objects.create_user("customer", "customer@artscape.com", "customer123")
        profile = customer.profile
        profile.phone = "9876543210"
        profile.address = "123 Creative Street, Design District, Delhi"
        profile.save()
        print("Customer profile 'customer' / 'customer123' created successfully.")
    else:
        print("Customer 'customer' already exists.")

    media_dir = "media/products"
    if not os.path.exists(media_dir):
        os.makedirs(media_dir)
        
    dummy_image_path = os.path.join(media_dir, "dummy_art.png")
    if not os.path.exists(dummy_image_path):
        try:
            from PIL import Image, ImageDraw
            img = Image.new('RGB', (400, 400), color = '#1a2230')
            d = ImageDraw.Draw(img)
            d.text((100, 190), "Art-Scape Studio", fill=(242, 168, 76))
            img.save(dummy_image_path)
            print("Generated dummy product image at:", dummy_image_path)
        except Exception as e:
            with open(dummy_image_path, "wb") as f:
                f.write(b"")
            print("Wrote empty binary file for product image.")
    
    items = [
        {
            "name": "Ocean Shore Resin Coasters (Set of 4)",
            "description": "Bespoke handcrafted resin coaster circles resembling white ocean tide waves breaking on golden sand shore beaches. Heat-insulated and perfect for tea cups or cocktails.",
            "price": 1499.00,
            "category": "resin"
        },
        {
            "name": "Mystique Nebula Canvas Painting",
            "description": "Premium 16x20 inch acrylic painting depicting planetary clouds and deep stellar space. Features rich fluorescent gold and purple hues.",
            "price": 3899.00,
            "category": "acrylic"
        },
        {
            "name": "Amber Sunrise Meadows",
            "description": "Textured palette knife oil painting on stretched linen canvas. Showcases beautiful natural light and dynamic volumetric cloud layers.",
            "price": 5499.00,
            "category": "oil"
        },
        {
            "name": "Golden Mandala Embroidered Runner",
            "description": "Silk fabric table runner lined with fine cotton threads and hand-woven gold beads. Depicts symmetry and spiritual calmness.",
            "price": 999.00,
            "category": "fabric"
        },
        {
            "name": "Bohemian Resin & Flower Pendant",
            "description": "Custom handmade resin jewelry piece containing real dried baby's breath flowers. Suspended on a premium bronze chain.",
            "price": 699.00,
            "category": "custom"
        }
    ]
    
    for item in items:
        if not Product.objects.filter(name=item["name"]).exists():
            prod = Product.objects.create(
                name=item["name"],
                description=item["description"],
                price=item["price"],
                category=item["category"],
                available=True
            )
            with open(dummy_image_path, 'rb') as f:
                prod.image.save("art_sample_%s.png" % item["category"], File(f))
            prod.save()
            print("Inserted artwork:", prod.name)
        else:
            print("Product already exists:", item["name"])
            
    print("Database population completed successfully!")

if __name__ == '__main__':
    populate()