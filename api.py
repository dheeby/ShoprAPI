from flask import Flask, session
from flask_restplus import Api, Resource, fields, reqparse
from flask.ext.mysql import MySQL
from decimal import Decimal
import json

app = Flask(__name__)
api = Api(app, version='1.0', title='Shopr API', description='Documentation for the Shopr RESTful API')

ns_srv = api.namespace('server', description='Server')
ns_acc = api.namespace('accounts', description='Accounts')
ns_pro = api.namespace('products', description='Products')
ns_usr = api.namespace('user', description='User')

# MySQL configurations
app.config['MYSQL_DATABASE_USER'] = 'shopradmin'
app.config['MYSQL_DATABASE_PASSWORD'] = 'shopradmin'
app.config['MYSQL_DATABASE_DB'] = 'shopr'
app.config['MYSQL_DATABASE_HOST'] = 'shoprdevdb.c3qsazu8diam.us-east-1.rds.amazonaws.com'

mysql = MySQL()
mysql.init_app(app)

conn = None
cursor = None

NUM_VENDORS = 2

@ns_srv.route('/ping', endpoint='ping')
@ns_srv.response(200, 'Success')
class Ping(Resource):
    def get(self):
        """Check to see if API server is alive"""
        return {'message': 'success'}, 200

@ns_acc.route('/login', endpoint='login')
@ns_acc.response(200, 'Success')
@ns_acc.response(422, 'Invalid email and/or password')
@ns_acc.response(500, 'Internal server error')
class Login(Resource):
    login_fields = ns_acc.model('LoginModel', {
        'email': fields.String(description='Login email', required=True),
        'password': fields.String(description='Login password', required=True)
    })
    @api.doc(body=login_fields)
    def post(self):
        """Login authentication with email and password"""
        try:
            parser = reqparse.RequestParser()
            parser.add_argument('email', required=True, type=str, location='json', help='Login email')
            parser.add_argument('password', required=True, type=str, location='json', help='Login password')
            args = parser.parse_args()
            
            sql = " \
                SELECT id \
                FROM users \
                WHERE email=%s AND password=%s"
            connectionSetup()
            cursor.execute(sql, [args['email'], args['password']]) 
            data = cursor.fetchone()
            connectionTeardown()

            if data is None:
                return {'message': 'Invalid email and/or password'}, 422
            else:
                session['user_id'] = data[0]
                return {'message': 'Login success', 'id': data[0]}, 200
        except Exception as e:
            return {'message': str(e)}, 500

@ns_acc.route('/logout')
@ns_acc.response(200, 'Success')
class Logout(Resource):
    def post(self):
        """Invalidate the current session"""
        if 'user_id' in session:
            session.pop('user_id', None)
            return {'message': 'Logged out'}, 200
        else:
            return {'message': 'Already logged out'}, 200

@ns_acc.route('/register')
@ns_acc.response(200, 'Success')
@ns_acc.response(422, 'Registration failure')
@ns_acc.response(500, 'Internal server error')
class Register(Resource):
    register_fields = ns_acc.model('RegisterModel', {
        'username': fields.String(description='Username to register', required=True),
        'password': fields.String(description='Password to register', required=True),
        'firstname': fields.String(description='First name to register', required=True),
        'lastname': fields.String(description='Last name to register', required=True),
        'email': fields.String(description='Email to register', required=True)
    })
    @api.doc(body=register_fields)
    def post(self):
        """Registers a new account"""
        try:
            parser = reqparse.RequestParser()
            parser.add_argument('username', required=True, type=str, help='Username to register')
            parser.add_argument('password', required=True, type=str, help='Password to register')
            parser.add_argument('firstname', required=True, type=str, help='First name to register')
            parser.add_argument('lastname', required=True, type=str, help='Last name to register')
            parser.add_argument('email', required=True, type=str, help='Email to register')
            args = parser.parse_args()

            proc = 'spRegister'
            values = (args['username'], args['password'], args['email'], args['firstname'], args['lastname'])
            connectionSetup()
            cursor.callproc(proc, values)
            data = cursor.fetchall()
            connectionTeardown()

            if len(data) is 0:
                conn.commit()
                return {'message': 'Account registration success'}, 200
            else:
                return {'message': 'Account registration failure'}, 422
        except Exception as e:
            return {'message': str(e)}, 500

@ns_acc.route('/change-password')
@ns_acc.response(200, 'Success')
@ns_acc.response(403, 'Authorization failed')
@ns_acc.response(500, 'Internal server error')
class ChangePassword(Resource):
    acc_fields = ns_acc.model('ChangePasswordModel', {
        'email': fields.String(description='Account email', required=True),
        'password': fields.String(description='Account password', required=True)
    })
    @api.doc(body=acc_fields)
    def post(self):
        """Change the password of the current logged in account"""
        try:
            if 'user_id' in session:
                parser = reqparse.RequestParser()
                parser.add_argument('email', required=True, type=str, help='Account email')
                parser.add_argument('password', required=True, type=str, help='Account password')
                args = parser.parse_args()
                
                sql = " \
                    UPDATE users \
                    SET PASSWORD=%s \
                    WHERE email=%s AND id=%s"
                connectionSetup()
                rows_changed = cursor.execute(sql, [args['password'], args['email'], str(session['user_id'])])
                conn.commit()
                connectionTeardown()
                if rows_changed is 0:
                    return {'message': 'The email provided is not registered with your account'}, 403
                else:
                    return {'message': 'Password successfully changed', 'email': args['email']}, 200
            else:
                return {'message': 'You must be logged in to change your password'}, 403
        except Exception as e:
            return {'message': str(e)}, 500

@ns_pro.route('/search')
@ns_pro.response(200, 'Success')
@ns_pro.response(500, 'Internal server error')
@ns_pro.doc(params={
    'query': 'Search query',
    'minprice': 'Minimum price filter',
    'maxprice': 'Maximum price filter',
    'category': 'Product category filter',
    'orderby': 'Results ordering property',
    'order': 'Order asc or desc',
    'page': 'Results page number'
})
class Search(Resource):
    def get(self):
        """Search for products"""
        try:
            parser = reqparse.RequestParser()
            parser.add_argument('query', required=True, type=str, help='Search query')
            parser.add_argument('minprice', type=float, help='Minimum price')
            parser.add_argument('maxprice', type=float, help='Maximum price')
            parser.add_argument('category', type=str, help='Product category')
            parser.add_argument('orderby', type=str, help='Ordering property')
            parser.add_argument('order', type=str, help='Order direction')
            parser.add_argument('page', type=int, help='Page number')
            args = parser.parse_args()
            
            filters = []
            if args['minprice'] is not None:
                filters.append("sale_price > " + str(args['minprice']))
            if args['maxprice'] is not None:
                filters.append("sale_price < " + str(args['maxprice']))
            if args['category'] is not None:
                filters.append("category_path LIKE '%" + args['category'] + "%'")
            
            sql = " \
                SELECT ds, upc, name, max(regular_price) as regular_price, \
                    min(case when sale_price > 0 then sale_price else regular_price end) as sale_price, \
                    image, thumbnail, short_desc, \
                    long_desc, cust_review_count, cust_review_avg, category_path \
                FROM products \
                WHERE name LIKE '%"
            subqueries = args['query'].split()
            sql = sql + subqueries[0] + ""
            if len(subqueries) > 1:
                sql = sql + "%' AND name LIKE '%" + "%' AND name LIKE '%".join(map(str, subqueries[1:]))
            sql = sql + "%'"
            for filter in filters:
                sql += (" AND " + filter)

            sql = sql + " GROUP BY upc "
            
            _orderby = args['orderby']
            if _orderby is not None and _orderby in ['sale_price', 'cust_review_count', 'cust_review_avg']:
                sql += " ORDER BY " + _orderby
                _order = args['order']
                if _order is not None and _order in ['asc', 'desc']:
                    sql += " " + _order
                else:
                    sql += " DESC"
            else:
                sql += " ORDER BY upc,cust_review_count DESC"

            _page = args['page']
            if _page is not None and int(_page) >= 0:
                sql += " LIMIT " + str(_page * 25) + ",25"
            else:
                sql += " LIMIT 0,25"

            if 'user_id' in session:
                insertIntoHistory(args['query'])

            connectionSetup()
            cursor.execute(sql)
            response = tableToJson(cursor), 200
            connectionTeardown()
            return response, 200
        except Exception as e:
            return {'message': str(e)}, 500

@ns_pro.route('/get-product')
@ns_pro.response(200, 'Success')
@ns_pro.doc(params={
    'upc': 'Product UPC',
    'vendor': 'Product vendor'
})
class GetProduct(Resource):
    def get(self):
        """Get product information for a specific product"""
        try:
            parser = reqparse.RequestParser()
            parser.add_argument('upc', required=True, type=str, help='Product UPC')
            parser.add_argument('vendor', required=False, type=str, help='Product vendor')
            args = parser.parse_args()

            sql = " \
                SELECT ds, upc, name, regular_price, sale_price, image, thumbnail, short_desc, \
                    long_desc, cust_review_count, cust_review_avg, vendor, category_path \
                FROM products \
                WHERE upc=%s"
            _vendor = args['vendor']
            if _vendor is not None:
                sql = sql + " AND vendor='" + _vendor + "' LIMIT " + str(NUM_VENDORS)
            connectionSetup()
            cursor.execute(sql, [args['upc']])
            response = tableToJson(cursor)
            connectionTeardown()
            return response, 200
        except Exception as e:
            return {'message': str(e)}, 500

@ns_pro.route('/top-deals')
@ns_pro.response(200, 'Success')
@ns_pro.response(500, 'Internal server error')
@ns_pro.doc(params={
    'category': 'Product category'
})
class TopDeals(Resource):
    def get(self):
        """Get the top product savings by category"""
        try:
            parser = reqparse.RequestParser()
            parser.add_argument('category', required=False, type=str, help='Product categoy')
            args = parser.parse_args()

            _category = ''
            if args['category'] is not None:
                _category = args['category']
            sql = " \
                SELECT upc, vendor, name, regular_price, sale_price, image, thumbnail, short_desc, \
                    long_desc, cust_review_count, cust_review_avg \
                FROM products \
                WHERE sale_price > 0 AND regular_price < 9999 \
                    AND category_path LIKE '%" + _category + "%' \
                GROUP BY category_path \
                ORDER BY regular_price - sale_price DESC \
                LIMIT 50"
            connectionSetup()
            cursor.execute(sql)
            response = tableToJson(cursor)
            connectionTeardown()
            return response, 200
        except Exception as e:
            return {'message': str(e)}, 500

@ns_usr.route('/history')
@ns_usr.response(200, 'Success')
@ns_usr.response(500, 'Internal server error')
class History(Resource):
    def get(self):
        """Get the search history for the current logged in user"""
        try:
            if 'user_id' in session:
                sql = " \
                    SELECT search \
                    FROM history \
                    WHERE user_id=%s \
                    ORDER BY time DESC \
                    LIMIT 10"
                connectionSetup()
                cursor.execute(sql, [str(session['user)id'])])
                response = tableToJson(cursor)
                connectionTeardown()
                return response, 200
            else:
                return json.loads('[]'), 200
        except Exception as e:
            return {'message': str(e)}, 500

@ns_usr.route('/shopping-cart')
@ns_usr.response(200, 'Success')
@ns_usr.response(403, 'Authorization failed')
@ns_usr.response(500, 'Internal server error')
class Cart(Resource):
    def get(self):
        """Get the list of products in the shopping cart"""
        try:
            if 'user_id' in session:
                sql = " \
                    SELECT t1.upc, t1.vendor, t1.quantity, t2.upc, t2.name, t2.thumbnail, \
                    t2.image, t2.short_desc, t2.long_desc, t2.cust_review_count, \
                    t2.cust_review_avg, t2.category_path, t3.regular_price, t3.sale_price \
                    FROM shopping_cart t1 \
                    INNER JOIN product_info t2 \
                    INNER JOIN product_prices t3 \
                    ON t1.upc=t2.upc AND t1.vendor=t2.vendor \
                    AND t1.upc=t3.upc AND t1.vendor=t3.vendor AND t1.user_id=%s"
                connectionSetup()
                cursor.execute(sql, [str(session['user_id'])])
                response = tableToJson(cursor)
                connectionTeardown()
                return response, 200
            else:
                return {'message': 'You must be logged in to access your shopping cart'}, 403
        except Exception as e:
            return {'message': str(e)}, 500
    
    cart_fields = ns_usr.model('CartModel', {
        'upc': fields.String(description='Product UPC', required=True),
        'quantity': fields.Integer(description='Quantity', required=True, min=1),
        'vendor': fields.String(description='Product vendor', required=True, enum=['BESTBUY', 'WALMART'])
    })
    @api.doc(body=cart_fields)
    def post(self):
        """Add a product to the shopping cart"""
        try:
            if 'user_id' in session:
                parser = reqparse.RequestParser()
                parser.add_argument('upc', required=True, type=str, location='json', help='Product UPC')
                parser.add_argument('quantity', required=True, type=int, location='json', help='Quantity')
                parser.add_argument('vendor', required=True, type=str, location='json', help='Product vendor')
                args = parser.parse_args()
                
                insertIntoCart(args['upc'], args['quantity'], args['vendor'])
                return {'message': 'Product successfully added to shopping cart', 'upc': args['upc']}, 200
            else:
                return {'message': 'You must be logged in to add to your shopping cart'}, 403
        except Exception as e:
            return {'message': str(e)}, 500

@ns_srv.route('/feedback')
@ns_srv.response(200, 'Sent feedback success')
@ns_srv.response(500, 'Internal server error')
class Feedback(Resource):
    feedback_fields = ns_srv.model('FeedbackModel', {
        'name': fields.String(description='Name', required=True, min_length=3, max_length=80),
        'email': fields.String(description='Email', required=True, min_length=3, max_length=100),
        'comments': fields.String(description='Comments', required=True, min_length=1, max_length=500)
    })
    @api.doc(body=feedback_fields)
    def post(self):
        """Send feedback"""
        try:
            parser = reqparse.RequestParser()
            parser.add_argument('name', required=True, type=str, location='json', help='Name')
            parser.add_argument('email', required=True, type=str, location='json', help='Email')
            parser.add_argument('comments', required=True, type=str, location='json', help='Comments')
            args = parser.parse_args()
            
            insertIntoFeedback(args['name'], args['email'], args['comments'])
            return {'message': 'Feedback sent successfully'}, 200
        except Exception as e:
            return {'message': str(e)}, 500

@ns_usr.route('/wishlist')
@ns_usr.response(200, 'Success')
@ns_usr.response(403, 'Authorization failed')
@ns_usr.response(500, 'Failure')
class Wishlist(Resource):
    def get(self):
        """Get the list of products in the wishlist"""
        try:
            if 'user_id' in session:
                sql = " \
                    SELECT t1.upc, t1.vendor, t2.upc, t2.name, t2.thumbnail, \
                    t2.image, t2.short_desc, t2.long_desc, t2.cust_review_count, \
                    t2.cust_review_avg, t2.category_path, t3.regular_price, t3.sale_price \
                    FROM wishlist t1 \
                    INNER JOIN product_info t2 \
                    INNER JOIN product_prices t3 \
                    ON t1.upc=t2.upc AND t1.vendor=t2.vendor \
                    AND t1.upc=t3.upc AND t1.vendor=t3.vendor AND t1.user_id=%s"
                connectionSetup()
                cursor.execute(sql, [str(session['user_id'])])
                response = tableToJson(cursor)
                connectionTeardown()
                return response, 200
            else:
                return {'message', 'You must be logged in to access your wishlist'}, 403
        except Exception as e:
            return {'message': str(e)}, 500
    wishlist_fields = ns_usr.model('WishlistModel', {
        'upc': fields.String(description='Product UPC', required=True),
        'vendor': fields.String(description='Product vendor', required=True, enum=['BESTBUY', 'WALMART'])
    })
    @api.doc(body=wishlist_fields)
    def post(self):
        """Add a product to the wishlist"""
        try:
            if 'user_id' in session:
                parser = reqparse.RequestParser()
                parser.add_argument('upc', required=True, type=str, location='json', help='Product UPC')
                parser.add_argument('vendor', required=True, type=str, location='json', help='Product vendor')
                args = parser.parse_args()

                insertIntoWishlist(args['upc'], args['vendor'])
                return {'message': 'Product successfully added to wishlist', 'upc': args['upc']}, 200
            else:
                return {'message', 'You must be logged in to add to your wishlist'}, 403
        except Exception as e:
            return {'message': str(e)}, 500

def connectionSetup():
    global conn
    conn = mysql.connect()
    global cursor
    cursor = conn.cursor()

def connectionTeardown():
    conn.close()

def insertIntoHistory(search):
    sql = "INSERT INTO history (user_id,search,time) VALUES (%s,%s,%s)"
    connectionSetup()
    cursor.execute(sql, [str(session['user_id']), search, 'NOW()'])
    conn.commit()
    connectionTeardown()

def insertIntoCart(upc, quantity, vendor):
    sql = "INSERT INTO shopping_cart (user_id,upc,quantity,vendor,time) VALUES (%s,%s,%s,%s,%s)"
    connectionSetup()
    cursor.execute(sql, [str(session['user_id']), upc, quantity, vendor, 'NOW()'])
    conn.commit()
    connectionTeardown()

def insertIntoFeedback(name, email, comments):
    sql = "INSERT INTO feedback (name,email,comments) VALUES (%s,%s,%s)"
    connectionSetup()
    cursor.execute(sql, [name, email, comments])
    conn.commit()
    connectionTeardown()

def insertIntoWishlist(upc, vendor):
    sql = "INSERT INTO wishlist (user_id,upc,vendor,time) VALUES (%s,%s,%s,%s)"
    connectionSetup()
    cursor.execute(sql, [str(session['user_id']), upc, vendor, 'NOW()'])
    conn.commit()
    connectionTeardown()

def tableToJson(crs):
    rows = [x for x in crs]
    cols = [x[0] for x in crs.description]
    results = []
    for row in rows:
        data = {}
        for prop, val in zip(cols, row):
            if isinstance(val, Decimal):
                data[prop] = float(val)
            elif hasattr(val, 'isoformat'):
                data[prop] = val.isoformat()
            else:
                if isinstance(val, unicode) and val.startswith('"') and val.endswith('"'):
                    data[prop] = val[1:-1]
                else:
                    data[prop] = val
        results.append(data)
    return json.loads(json.dumps(results, indent=4, sort_keys=True, ensure_ascii=False))

if __name__ == '__main__':
    app.secret_key = 'cb74517602a13d66c219a8df9fbf026672b1ca1675ff324c8b5346f2da43a1ba'
    app.run(host='0.0.0.0', port=5000, debug=True)
