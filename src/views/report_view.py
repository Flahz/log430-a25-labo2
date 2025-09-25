"""
Report view
SPDX - License - Identifier: LGPL - 3.0 - or -later
Auteurs : Gabriel C. Ullmann, Fabio Petrillo, 2025
"""
from views.template_view import get_template, get_param
from queries.read_order import get_highest_spending_users, get_best_selling_products_from_counters
from queries.read_user import get_user_by_id
from queries.read_product import get_product_by_id

def show_highest_spending_users():
    """ Show report of highest spending users """
    top_users = get_highest_spending_users()
    
    html_content = "<h2>Les plus gros acheteurs</h2>"
    
    if not top_users:
        html_content += "<p>Aucun acheteur trouvé.</p>"
    else:
        html_content += "<table border='1' style='border-collapse: collapse; width: 100%;'>"
        html_content += "<tr><th>Nom</th><th>Total dépensé</th><th>Nombre de commandes</th></tr>"
        
        for user in top_users:
            user_info = get_user_by_id(user.user_id)
            user_name = user_info.get('name', f'Utilisateur {user.user_id}')
            
            html_content += f"<tr>"
            html_content += f"<td>{user_name}</td>"
            html_content += f"<td>{user.total_spent:.2f} $</td>"
            html_content += f"<td>{user.order_count}</td>"
            html_content += f"</tr>"
        
        html_content += "</table>"
    
    return get_template(html_content)

def show_best_sellers():
    """ Show report of best selling products """
    best_sellers = get_best_selling_products_from_counters()
    
    html_content = "<h2>Les articles les plus vendus</h2>"
    
    if not best_sellers:
        html_content += "<p>Aucun article vendu trouvé.</p>"
    else:
        html_content += "<table border='1' style='border-collapse: collapse; width: 100%;'>"
        html_content += "<tr><th>Nom du produit</th><th>SKU</th><th>Prix unitaire</th><th>Total vendu</th></tr>"
        
        for product in best_sellers:
            product_info = get_product_by_id(product.product_id)
            product_name = product_info.get('name', f'Produit {product.product_id}')
            product_sku = product_info.get('sku', 'N/A')
            product_price = product_info.get('price', 0.0)
            
            html_content += f"<tr>"
            html_content += f"<td>{product_name}</td>"
            html_content += f"<td>{product_sku}</td>"
            html_content += f"<td>{product_price:.2f} $</td>"
            html_content += f"<td>{product.total_sold}</td>"
            html_content += f"</tr>"
        
        html_content += "</table>"
    
    return get_template(html_content)