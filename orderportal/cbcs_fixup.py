"Ad hoc fixup of CBCS OrderPortal forms and orders."

from orderportal import utils

utils.get_settings()

db = utils.get_db()

forms = [r.doc for r in db.view("form", "modified", include_docs=True)]
print(len(forms))

orders = [r.doc for r in db.view("order", "modified", include_docs=True)]
print(len(orders))

for form in forms:
    for field in form["fields"]:
        if field["identifier"] == "node":
            field["identifier"] = "nodes"
            print("found")
            break
    db.put(form)

for order in orders:
    try:
        single_value = order["fields"].pop("node")
    except KeyError:
        single_value = None
    multi_value = order["fields"].get("nodes", [])
    if single_value and not multi_value:
        order["fields"]["nodes"] = single_value
        print(f"fixed {order['identifier']} {order['fields']['nodes']}")
    db.put(order)
