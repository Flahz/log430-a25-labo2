## Question 1
* Lorsque l'application démarre, la synchronisation entre Redis et MySQL est-elle initialement déclenchée par quelle méthode ? Veuillez inclure le code pour illustrer votre réponse.

La synchronisation initiale entre Redis et MySQL est déclenchée dans le bloc principal d'exécution (`if __name__ == "__main__":`) du fichier `store_manager.py`. Après avoir vérifié que MySQL est prêt, l'application appelle `sync_all_orders_to_redis()` une seule fois au démarrage, avant de démarrer le serveur HTTP. Cette méthode charge toutes les commandes existantes depuis MySQL vers Redis pour initialiser le cache.

**Code qui illustre la réponse :**

```python
if __name__ == "__main__":
    import time
    
    print("Waiting for MySQL to be ready...")
    max_retries = 30
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            from db import get_sqlalchemy_session
            session = get_sqlalchemy_session()
            session.execute('SELECT 1')
            session.close()
            print("MySQL is ready!")
            break
        except Exception as e:
            retry_count += 1
            print(f"Waiting for MySQL... (attempt {retry_count}/{max_retries})")
            time.sleep(2)
    
    print("Starting initial sync of orders from MySQL to Redis...")
    try:
        synced_orders = sync_all_orders_to_redis()
        print(f"Initial sync completed: {synced_orders} orders available in Redis")
    except Exception as e:
        print(f"Warning: Initial sync failed - {e}")
        print("Application will continue but Redis cache may be empty")
    
    server = HTTPServer(("0.0.0.0", 5000), StoreManager)
    print("Server running on http://0.0.0.0:5000")
    server.serve_forever()
```

## Question 2

* Quelles méthodes avez-vous utilisées pour lire des données à partir de Redis ? Veuillez inclure le code pour illustrer votre réponse.

Nous utilisons **deux méthodes principales** pour lire des données à partir de Redis :

### 1. `KEYS` - Pour récupérer les clés correspondant à un pattern
```python
def get_orders_from_redis(limit=9999):
    """Get last X orders from Redis"""
    r = get_redis_conn()
    
    order_keys = r.keys("order:*")
    
    if not order_keys:
        return []
```

### 2. `HGETALL` - Pour récupérer toutes les données d'un hash
```python
def get_order_by_id(order_id):
    """Get order by ID from Redis"""
    r = get_redis_conn()
    return r.hgetall(order_id)

for key in order_keys:
    order_data = r.hgetall(key)
    if order_data:
```

**Structure des données stockées :**
- **Clé :** `"order:1"`, `"order:2"`, etc.
- **Type :** Hash Redis
- **Contenu du hash :**
```
"order:1" → {
    "id": "1",
    "user_id": "1", 
    "total_amount": "1999.99",
    "items_count": "0",
    "item_0_product_id": "1",
    "item_0_quantity": "1"
}
```
## Question 3
* Quelles méthodes avez-vous utilisées pour ajouter des données dans Redis ? Veuillez inclure le code pour illustrer votre réponse.

Nous utilisons la méthode **`HSET`** avec le paramètre `mapping` pour ajouter des données dans Redis sous forme de hash.

### Comparaison des approches :

**Approche traditionnelle (sans mapping) :**
```python
r.hset("order:1", "id", "1")
r.hset("order:1", "user_id", "1") 
r.hset("order:1", "total_amount", "1999.99")
r.hset("order:1", "items_count", "2")
r.hset("order:1", "item_0_product_id", "1")
r.hset("order:1", "item_0_quantity", "1")
```
*Cette approche nécessite 6 communications réseau séparées avec Redis.*

**Approche optimisée (avec mapping) :**
```python
order_data = {
    'id': order_id,
    'user_id': user_id,
    'total_amount': str(total_amount),
    'items_count': len(items),
    'item_0_product_id': str(item['product_id']),
    'item_0_quantity': str(item['quantity'])
}

r.hset(order_key, mapping=order_data)
```
*Cette approche nécessite une seule communication réseau avec Redis.*

### `HSET` avec `mapping` - Implémentation complète

```python
def add_order_to_redis(order_id, user_id, total_amount, items):
    """Insert order to Redis"""
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
    
    r.hset(order_key, mapping=order_data)
    print(f"Order {order_id} added to Redis")
```

**Avantages du paramètre `mapping` :**
- **Performance** : Une seule communication réseau au lieu de plusieurs
- **Atomique** : Toutes les données sont écrites simultanément
- **Efficace** : Réduit la latence réseau
- **Lisible** : Code plus clair et concis

**Utilisation dans l'application :**
- Appelée automatiquement lors de chaque nouvelle commande dans `add_order()`
- Utilisée lors de la synchronisation initiale dans `sync_all_orders_to_redis()`

## Question 4
* Quelles méthodes avez-vous utilisées pour supprimer des données dans Redis ? Veuillez inclure le code pour illustrer votre réponse.

Nous utilisons la méthode **`DELETE`** pour supprimer complètement une clé et toutes ses données associées dans Redis.

### `DELETE` - Pour supprimer une clé complète

```python
def delete_order_from_redis(order_id):
    """Delete order from Redis"""
    r = get_redis_conn()
    order_key = f"order:{order_id}"
    r.delete(order_key)
    print(f"Order {order_id} deleted from Redis")
```

**Pourquoi utiliser `DELETE` plutôt que `HDEL` :**
- `DELETE` supprime la clé entière (`"order:1"` et tout son contenu)
- `HDEL` supprimerait seulement des champs spécifiques du hash
- Dans notre cas, nous voulons supprimer complètement la commande, donc `DELETE` est approprié

## Question 5
* Si nous souhaitions créer un rapport similaire, mais présentant les produits les plus vendus, les informations dont nous disposons actuellement dans Redis sont-elles suffisantes, ou devrions-nous chercher dans les tables sur MySQL ? Si nécessaire, quelles informations devrions-nous ajouter à Redis ? Veuillez inclure le code pour illustrer votre réponse.

**Réponse : OUI, les informations dans Redis sont suffisantes !**

Redis contient toutes les données nécessaires : le product_id, la quantité disponible, et tous les autres produits de chaque commande.

Les données stockées dans Redis contiennent toutes les informations nécessaires pour créer un rapport des produits les plus vendus :

### Données disponibles dans Redis :
```
"order:1" → {
    "id": "1",
    "user_id": "1", 
    "total_amount": "1999.99",
    "items_count": "2",
    "item_0_product_id": "1",
    "item_0_quantity": "5",
    "item_1_product_id": "2",
    "item_1_quantity": "3"
}
```

### Implémentation du rapport des produits les plus vendus :

```python
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
```

