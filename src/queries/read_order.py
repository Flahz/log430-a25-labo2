"""
Orders (read-only model)
SPDX - License - Identifier: LGPL - 3.0 - or -later
Auteurs : Gabriel C. Ullmann, Fabio Petrillo, 2025
"""

from db import get_sqlalchemy_session, get_redis_conn
from sqlalchemy import desc
from models.order import Order

def get_order_by_id(order_id):
    """Get order by ID from Redis"""
    r = get_redis_conn()
    return r.hgetall(order_id)

def get_orders_from_mysql(limit=9999):
    """Get last X orders"""
    session = get_sqlalchemy_session()
    return session.query(Order).order_by(desc(Order.id)).limit(limit).all()

def get_orders_from_redis(limit=9999):
    """Get last X orders from Redis"""
    r = get_redis_conn()
    
    order_keys = r.keys("order:*")
    
    if not order_keys:
        return []
    
    orders = []
    for key in order_keys:
        order_data = r.hgetall(key)
        if order_data:
            class OrderFromRedis:
                def __init__(self, id, total_amount):
                    self.id = int(id)
                    self.total_amount = float(total_amount)
            
            order = OrderFromRedis(
                id=order_data.get('id', 0),
                total_amount=order_data.get('total_amount', 0.0)
            )
            orders.append(order)
    
    orders.sort(key=lambda x: x.id, reverse=True)
    
    return orders[:limit]

def get_highest_spending_users():
    """Get top 10 users who spent the most money from Redis data"""
    r = get_redis_conn()
    order_keys = r.keys("order:*")
    
    if not order_keys:
        return []
    
    user_spending = {}
    for key in order_keys:
        order_data = r.hgetall(key)
        if order_data:
            user_id = int(order_data.get('user_id', 0))
            total_amount = float(order_data.get('total_amount', 0.0))
            
            if user_id in user_spending:
                user_spending[user_id] += total_amount
            else:
                user_spending[user_id] = total_amount
    
    user_list = [(user_id, total_spent) for user_id, total_spent in user_spending.items()]
    top_users = sorted(user_list, key=lambda x: x[1], reverse=True)[:10]
    
    result = []
    for user_id, total_spent in top_users:
        class TopSpendingUser:
            def __init__(self, user_id, total_spent, order_count):
                self.user_id = user_id
                self.total_spent = total_spent
                self.order_count = order_count
        
        order_count = sum(1 for key in order_keys 
                         if r.hget(key, 'user_id') and int(r.hget(key, 'user_id')) == user_id)
        
        user = TopSpendingUser(user_id, total_spent, order_count)
        result.append(user)
    
    return result

def get_best_selling_products_from_counters():
    """Get best selling products using Redis INCR counters"""
    r = get_redis_conn()
    
    product_keys = r.keys("product_sold:*")
    
    if not product_keys:
        return []
    
    product_sales = []
    for key in product_keys:
        key_str = key.decode('utf-8') if isinstance(key, bytes) else key
        product_id = int(key_str.split(':')[1])
        total_sold = int(r.get(key) or 0)
        
        if total_sold > 0:
            product_sales.append((product_id, total_sold))
    
    product_sales.sort(key=lambda x: x[1], reverse=True)
    
    result = []
    for product_id, total_sold in product_sales:
        class BestSellingProduct:
            def __init__(self, product_id, total_sold):
                self.product_id = product_id
                self.total_sold = total_sold
        
        product = BestSellingProduct(product_id, total_sold)
        result.append(product)
    
    return result