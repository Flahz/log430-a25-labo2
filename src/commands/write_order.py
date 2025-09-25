"""
Orders (write-only model)
SPDX - License - Identifier: LGPL - 3.0 - or -later
Auteurs : Gabriel C. Ullmann, Fabio Petrillo, 2025
"""
from models.product import Product
from models.order_item import OrderItem
from models.order import Order
from queries.read_order import get_orders_from_mysql
from db import get_sqlalchemy_session, get_redis_conn

def add_order(user_id: int, items: list):
    """Insert order with items in MySQL, keep Redis in sync"""
    if not user_id or not items:
        raise ValueError("Vous devez indiquer au moins 1 utilisateur et 1 item pour chaque commande.")

    try:
        product_ids = []
        for item in items:
            product_ids.append(int(item['product_id']))
    except Exception as e:
        print(e)
        raise ValueError(f"L'ID Article n'est pas valide: {item['product_id']}")
    session = get_sqlalchemy_session()

    try:
        products_query = session.query(Product).filter(Product.id.in_(product_ids)).all()
        price_map = {product.id: product.price for product in products_query}
        total_amount = 0
        order_items_data = []
        
        for item in items:
            pid = int(item["product_id"])
            qty = float(item["quantity"])

            if not qty or qty <= 0:
                raise ValueError(f"Vous devez indiquer une quantité superieure à zéro.")

            if pid not in price_map:
                raise ValueError(f"Article ID {pid} n'est pas dans la base de données.")

            unit_price = price_map[pid]
            total_amount += unit_price * qty
            order_items_data.append({
                'product_id': pid,
                'quantity': qty,
                'unit_price': unit_price
            })
        
        new_order = Order(user_id=user_id, total_amount=total_amount)
        session.add(new_order)
        session.flush() 
        
        order_id = new_order.id

        for item_data in order_items_data:
            order_item = OrderItem(
                order_id=order_id,
                product_id=item_data['product_id'],
                quantity=item_data['quantity'],
                unit_price=item_data['unit_price']
            )
            session.add(order_item)

        session.commit()

        # TODO: ajouter la commande à Redis
        add_order_to_redis(order_id, user_id, total_amount, items)

        return order_id

    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()

def delete_order(order_id: int):
    """Delete order in MySQL, keep Redis in sync"""
    session = get_sqlalchemy_session()
    try:
        order = session.query(Order).filter(Order.id == order_id).first()
        
        if order:
            session.delete(order)
            session.commit()

            # TODO: supprimer la commande à Redis
            delete_order_from_redis(order_id)
            return 1  
        else:
            return 0  
            
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()

def add_order_to_redis(order_id, user_id, total_amount, items):
    """Insert order to Redis and update product counters"""
    r = get_redis_conn()
      
    order_key = f"order:{order_id}"
    order_data = {
        'id': order_id,
        'user_id': user_id,
        'total_amount': str(total_amount),
        'items_count': len(items)
    }
    
    for i, item in enumerate(items):
        order_data[f'item_{i}_product_id'] = str(item['product_id'])
        order_data[f'item_{i}_quantity'] = str(item['quantity'])
        
        product_counter_key = f"product_sold:{item['product_id']}"
        r.incrby(product_counter_key, int(item['quantity']))
    
    r.hset(order_key, mapping=order_data)
    print(f"Order {order_id} added to Redis with product counters updated")

def delete_order_from_redis(order_id):
    """Delete order from Redis and update product counters"""
    r = get_redis_conn()
    order_key = f"order:{order_id}"
    
    order_data = r.hgetall(order_key)
    if order_data:
        items_count = int(order_data.get('items_count', 0))
        
        for i in range(items_count):
            product_id_key = f'item_{i}_product_id'
            quantity_key = f'item_{i}_quantity'
            
            if product_id_key in order_data and quantity_key in order_data:
                product_id = order_data[product_id_key]
                quantity = int(order_data[quantity_key])
                
                product_counter_key = f"product_sold:{product_id}"
                r.decrby(product_counter_key, quantity)
                
                if int(r.get(product_counter_key) or 0) <= 0:
                    r.delete(product_counter_key)
    
    r.delete(order_key)
    print(f"Order {order_id} deleted from Redis with product counters updated")

def sync_all_orders_to_redis():
    """ Sync orders from MySQL to Redis """
    r = get_redis_conn()
    orders_in_redis = r.keys("order:*")
    
    if len(orders_in_redis) > 0:
        print(f'Redis already contains {len(orders_in_redis)} orders, no need to sync!')
        return len(orders_in_redis)
    
    rows_added = 0
    session = get_sqlalchemy_session()
    
    try:
        orders_from_mysql = get_orders_from_mysql()
        print(f"Found {len(orders_from_mysql)} orders in MySQL to sync to Redis")
        
        for order in orders_from_mysql:
            order_items = session.query(OrderItem).filter(OrderItem.order_id == order.id).all()
            
            items = []
            for item in order_items:
                items.append({
                    'product_id': item.product_id,
                    'quantity': item.quantity
                })
            
            add_order_to_redis(order.id, order.user_id, order.total_amount, items)
            rows_added += 1
            
        print(f"Successfully synced {rows_added} orders from MySQL to Redis")
        
    except Exception as e:
        print(f"Error during sync: {e}")
        return 0
    finally:
        session.close()
        return rows_added