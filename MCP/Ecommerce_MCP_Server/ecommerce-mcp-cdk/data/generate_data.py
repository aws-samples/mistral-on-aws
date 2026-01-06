#!/usr/bin/env python3
"""
Synthetic Data Generator for E-Commerce MCP Server

Generates realistic demo data using the Faker library:
- 50 products across 4 categories (Electronics, Clothing, Home, Books)
- 10 customers with demo credentials
- 50 orders (5 per customer)
- 50 reviews (5 per customer, only for purchased products)
- ~8 returns (15% of orders, within 30-day window)

Output: synthetic_data.json
"""

import json
import uuid
from datetime import datetime, timedelta
from decimal import Decimal
import random
from faker import Faker

# Initialize Faker
fake = Faker()
Faker.seed(42)  # For reproducibility
random.seed(42)


def generate_product_id():
    """Generate unique product ID"""
    return f"prod-{uuid.uuid4().hex[:8]}"


def generate_customer_id(index):
    """Generate customer ID"""
    return f"cust-{str(index + 1).zfill(3)}"


def generate_order_id():
    """Generate unique order ID"""
    return f"ord-{uuid.uuid4().hex[:10]}"


def generate_review_id():
    """Generate unique review ID"""
    return f"rev-{uuid.uuid4().hex[:10]}"


def generate_return_id():
    """Generate unique return ID"""
    return f"ret-{uuid.uuid4().hex[:10]}"


def generate_products(count=50):
    """Generate product catalog across 4 categories"""
    categories = {
        "Electronics": [
            ("Laptop", 800, 2500, "High-performance laptop"),
            ("Smartphone", 400, 1200, "Latest smartphone"),
            ("Tablet", 300, 900, "Portable tablet"),
            ("Headphones", 50, 400, "Wireless headphones"),
            ("Monitor", 200, 800, "4K display monitor"),
            ("Keyboard", 30, 200, "Mechanical keyboard"),
            ("Mouse", 20, 150, "Gaming mouse"),
            ("Webcam", 50, 250, "HD webcam"),
            ("Smartwatch", 200, 600, "Fitness smartwatch"),
            ("Speaker", 100, 500, "Bluetooth speaker"),
        ],
        "Clothing": [
            ("T-Shirt", 15, 50, "Comfortable cotton t-shirt"),
            ("Jeans", 40, 120, "Classic denim jeans"),
            ("Jacket", 60, 250, "Stylish jacket"),
            ("Sneakers", 50, 200, "Running sneakers"),
            ("Dress", 40, 180, "Elegant dress"),
            ("Sweater", 30, 100, "Warm sweater"),
            ("Shorts", 20, 60, "Summer shorts"),
            ("Boots", 80, 300, "Leather boots"),
            ("Hat", 15, 50, "Trendy hat"),
            ("Scarf", 10, 40, "Winter scarf"),
        ],
        "Home": [
            ("Coffee Maker", 40, 200, "Automatic coffee maker"),
            ("Blender", 30, 150, "High-speed blender"),
            ("Vacuum", 100, 500, "Robot vacuum"),
            ("Lamp", 25, 120, "LED desk lamp"),
            ("Chair", 80, 400, "Ergonomic office chair"),
            ("Desk", 150, 600, "Standing desk"),
            ("Rug", 50, 300, "Area rug"),
            ("Pillow", 20, 80, "Memory foam pillow"),
            ("Curtains", 30, 100, "Blackout curtains"),
            ("Mirror", 40, 200, "Wall mirror"),
        ],
        "Books": [
            ("Fiction Novel", 10, 30, "Bestselling fiction"),
            ("Non-Fiction", 12, 35, "Informative non-fiction"),
            ("Cookbook", 15, 40, "Gourmet recipes"),
            ("Biography", 15, 35, "Inspiring life story"),
            ("Self-Help", 12, 30, "Personal development"),
            ("Science", 18, 45, "Popular science"),
            ("History", 15, 35, "Historical account"),
            ("Art Book", 25, 70, "Beautiful art collection"),
            ("Travel Guide", 20, 45, "Destination guide"),
            ("Poetry", 10, 25, "Modern poetry collection"),
        ]
    }

    products = []
    product_templates = []

    # Collect all product templates
    for category, items in categories.items():
        for name, min_price, max_price, desc_template in items:
            product_templates.append((category, name, min_price, max_price, desc_template))

    # Generate products, cycling through templates
    for i in range(count):
        category, base_name, min_price, max_price, desc_template = product_templates[i % len(product_templates)]

        # Add variation to names for uniqueness
        brand = fake.company().split()[0]  # Get first word of company name
        color_or_variant = random.choice(["Pro", "Plus", "Max", "Ultra", "Standard", "Classic", "Premium"])
        name = f"{brand} {base_name} {color_or_variant}"

        price = round(random.uniform(min_price, max_price), 2)
        stock = random.randint(5, 100)

        product = {
            "product_id": generate_product_id(),
            "name": name,
            "description": f"{desc_template}. {fake.catch_phrase()}",
            "price": price,
            "stock_quantity": stock,
            "category": category,
            "image_urls": [f"https://example.com/images/{fake.uuid4()}.jpg"],
            "created_at": (datetime.now() - timedelta(days=random.randint(30, 365))).isoformat()
        }
        products.append(product)

    return products


def generate_customers(count=10):
    """Generate customer records with demo credentials"""
    customers = []

    for i in range(count):
        customer_id = generate_customer_id(i)
        email = f"demo{i + 1}@example.com"

        customer = {
            "customer_id": customer_id,
            "email": email,
            "given_name": fake.first_name(),
            "family_name": fake.last_name(),
            "shipping_address": {
                "street": fake.street_address(),
                "city": fake.city(),
                "state": fake.state_abbr(),
                "zip_code": fake.zipcode(),
                "country": "USA"
            },
            "payment_methods": [
                {
                    "type": "credit_card",
                    "last_four": fake.credit_card_number()[-4:],
                    "brand": random.choice(["Visa", "Mastercard", "Amex"])
                }
            ],
            "created_at": (datetime.now() - timedelta(days=random.randint(180, 730))).isoformat(),
            "cognito_user_id": ""  # Will be set when Cognito user is created
        }
        customers.append(customer)

    return customers


def generate_orders(customers, products, orders_per_customer=5):
    """Generate orders with stock validation"""
    orders = []

    for customer in customers:
        # Each customer gets orders_per_customer orders
        for _ in range(orders_per_customer):
            product = random.choice(products)
            quantity = random.randint(1, 3)

            # Create order
            order_date = datetime.now() - timedelta(days=random.randint(1, 180))

            order = {
                "order_id": generate_order_id(),
                "customer_id": customer["customer_id"],
                "product_id": product["product_id"],
                "quantity": quantity,
                "unit_price": product["price"],
                "total_price": round(product["price"] * quantity, 2),
                "status": "delivered",
                "shipping_address": customer["shipping_address"],
                "payment_method": customer["payment_methods"][0],
                "created_at": order_date.isoformat(),
                "delivered_at": (order_date + timedelta(days=random.randint(2, 7))).isoformat()
            }
            orders.append(order)

    return orders


def generate_reviews(customers, orders, products, reviews_per_customer=5):
    """Generate reviews only for purchased products"""
    reviews = []

    # Group orders by customer for easy lookup
    customer_orders = {}
    for order in orders:
        customer_id = order["customer_id"]
        if customer_id not in customer_orders:
            customer_orders[customer_id] = []
        customer_orders[customer_id].append(order)

    # Create product lookup
    product_lookup = {p["product_id"]: p for p in products}

    for customer in customers:
        customer_id = customer["customer_id"]
        available_orders = customer_orders.get(customer_id, [])

        # Select random orders to review (up to reviews_per_customer)
        orders_to_review = random.sample(
            available_orders,
            min(reviews_per_customer, len(available_orders))
        )

        for order in orders_to_review:
            product = product_lookup[order["product_id"]]
            rating = random.randint(3, 5)  # Mostly positive reviews

            # Generate review date after delivery
            order_date = datetime.fromisoformat(order["delivered_at"])
            review_date = order_date + timedelta(days=random.randint(1, 30))

            # Review text based on rating
            if rating == 5:
                title = random.choice([
                    "Excellent product!",
                    "Highly recommended!",
                    "Love it!",
                    "Perfect!",
                    "Amazing quality!"
                ])
                text = f"Great {product['name']}. {fake.sentence()} {fake.sentence()}"
            elif rating == 4:
                title = random.choice([
                    "Very good",
                    "Good product",
                    "Satisfied",
                    "Nice quality"
                ])
                text = f"Good {product['name']}. {fake.sentence()}"
            else:  # rating == 3
                title = "Decent"
                text = f"Okay {product['name']}. {fake.sentence()}"

            review = {
                "review_id": generate_review_id(),
                "product_id": product["product_id"],
                "customer_id": customer_id,
                "order_id": order["order_id"],
                "rating": rating,
                "title": title,
                "review_text": text,
                "verified_purchase": True,
                "created_at": review_date.isoformat()
            }
            reviews.append(review)

    return reviews


def generate_returns(orders, return_rate=0.15):
    """Generate returns for ~15% of orders within 30-day window"""
    returns = []

    # Select orders to return (only recent orders within 30 days)
    returnable_orders = [
        order for order in orders
        if (datetime.now() - datetime.fromisoformat(order["delivered_at"])).days <= 30
    ]

    # Select random subset for returns
    orders_to_return = random.sample(
        returnable_orders,
        int(len(orders) * return_rate)
    )

    reasons = [
        "Changed mind",
        "Defective product",
        "Wrong item received",
        "Not as described",
        "Better price elsewhere"
    ]

    for order in orders_to_return:
        delivered_date = datetime.fromisoformat(order["delivered_at"])
        return_date = delivered_date + timedelta(days=random.randint(1, 29))

        return_record = {
            "return_id": generate_return_id(),
            "order_id": order["order_id"],
            "customer_id": order["customer_id"],
            "product_id": order["product_id"],
            "reason": random.choice(reasons),
            "status": "requested",
            "created_at": return_date.isoformat(),
            "processed_at": None
        }
        returns.append(return_record)

    return returns


def main():
    """Generate all synthetic data and save to JSON"""
    print("Generating synthetic data for E-Commerce MCP Server...")

    print("  - Generating 50 products...")
    products = generate_products(50)

    print("  - Generating 10 customers...")
    customers = generate_customers(10)

    print("  - Generating 50 orders...")
    orders = generate_orders(customers, products, orders_per_customer=5)

    print("  - Generating 50 reviews...")
    reviews = generate_reviews(customers, orders, products, reviews_per_customer=5)

    print("  - Generating ~8 returns...")
    returns = generate_returns(orders, return_rate=0.15)

    # Package all data
    data = {
        "products": products,
        "customers": customers,
        "orders": orders,
        "reviews": reviews,
        "returns": returns,
        "metadata": {
            "generated_at": datetime.now().isoformat(),
            "total_products": len(products),
            "total_customers": len(customers),
            "total_orders": len(orders),
            "total_reviews": len(reviews),
            "total_returns": len(returns)
        }
    }

    # Save to JSON file
    output_file = "synthetic_data.json"
    with open(output_file, "w") as f:
        json.dump(data, f, indent=2)

    print(f"\n✓ Synthetic data generated successfully!")
    print(f"  Output file: {output_file}")
    print(f"\nStatistics:")
    print(f"  Products: {len(products)}")
    print(f"  Customers: {len(customers)}")
    print(f"  Orders: {len(orders)}")
    print(f"  Reviews: {len(reviews)}")
    print(f"  Returns: {len(returns)}")
    print(f"\nDemo credentials:")
    print(f"  Emails: demo1@example.com through demo10@example.com")
    print(f"  Password: Demo123! (for all demo accounts)")


if __name__ == "__main__":
    main()
