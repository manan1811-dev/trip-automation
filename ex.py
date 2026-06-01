transactions = [
    {"item": "Laptop", "category": "Electronics", "price": 1200.00, "quantity": 2},
    {"item": "Mouse", "category": "Electronics", "price": 45.00, "quantity": 5},
    {"item": "Notebook", "category": "Stationery", "price": 12.00, "quantity": 10},
    {"item": "Desk", "category": "Furniture", "price": 250.00, "quantity": 1},
    {"item": "Monitor", "category": "Electronics", "price": 300.00, "quantity": 3},
    {"item": "Pen", "category": "Stationery", "price": 3.00, "quantity": 500}
]

output = {}

for t in transactions:

    category = t["category"]
    revenue = t["price"] * t["quantity"]

    if category not in output:
        output[category] = {
            "total_revenue": 0,
            "most_expensive_item": t["item"],
            "highest_price": t["price"]  
        }

    output[category]["total_revenue"] += revenue
    if t["price"] > output[category]["highest_price"]:
        output[category]["highest_price"] = t["price"]
        output[category]["most_expensive_item"] = t["item"]

print(output)

for category in output:
    # print(f"Category: {category}")
    del output[category]["highest_price"]

print(output)