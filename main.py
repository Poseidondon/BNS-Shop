from flask import Flask, render_template, redirect, request, abort
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from data import db_session
from data.__all_models import *
from data.forms import *

from PIL import Image
from os import remove
from datetime import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = 'yandexlyceum_secret_key'
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0

login_manager = LoginManager()
login_manager.init_app(app)


def change_url_args(url, arg, value, mode='change'):
    if mode == 'change':
        if '?' in url:
            args = list(filter(lambda x: arg not in x, url.split('?')[1].split('&')))
            return '?' + '&'.join(sorted(args + [arg + '=' + value]))
        return '?' + arg + '=' + value
    elif mode == 'change_list':
        if '?' in url:
            args = list(filter(lambda x: arg not in x, url.split('?')[1].split('&')))
            return '?' + '&'.join(sorted(args + [arg + '=' + i for i in value]))
        return '?' + '&'.join(sorted([arg + '=' + i for i in value]))


def format_path(url):
    return ('|' + '|'.join(url.split('/')[3:])).replace('?', ';')


@app.after_request
def add_header(response):
    # response.cache_control.no_store = True
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, post-check=0, pre-check=0, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '-1'
    return response


@login_manager.user_loader
def load_user(user_id):
    session = db_session.create_session()
    return session.query(User).get(user_id)


@app.route('/')
def index():
    return redirect('/shop')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(request.url_root)


@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        session = db_session.create_session()
        user = session.query(User).filter(User.email == form.email.data).first()
        if user and user.check_password(form.password.data):
            login_user(user, remember=form.remember_me.data)
            return redirect("/")
        return render_template('login.html', title='BNS | Авторизация',
                               message="Неправильный логин или пароль",
                               form=form)
    return render_template('login.html', title='BNS | Авторизация', form=form)


@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        if form.password.data != form.password_again.data:
            return render_template('register.html', title='BNS | Регистрация',
                                   form=form,
                                   message="Пароли не совпадают")
        session = db_session.create_session()
        if session.query(User).filter(User.email == form.email.data).first():
            return render_template('register.html', title='BNS | Регистрация',
                                   form=form,
                                   message="Такой пользователь уже есть")
        user = User(
            surname=form.surname.data,
            name=form.name.data,
            email=form.email.data,
            address=form.address.data
        )
        user.set_password(form.password.data)
        if len(session.query(User).all()) == 0:
            user.access_level = 2
        session.add(user)
        session.commit()
        return redirect('/login')
    return render_template('register.html', title='BNS | Регистрация', form=form)


@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    session = db_session.create_session()

    if current_user.purchase_history:
        history = eval(current_user.purchase_history)
    else:
        history = ''
    users = session.query(User).all()
    user_params = (current_user.surname, current_user.name, current_user.address)

    if request.method == 'POST':
        for user in users:
            user.access_level = int(request.form.get('select_' + str(user.id)))
        session.commit()
        return redirect('/profile')

    return render_template('profile.html', title='BNS | Личный кабинет', users=users, history=history,
                           user_params=user_params)


@app.route('/profile/balance', methods=['GET', 'POST'])
@login_required
def balance():
    session = db_session.create_session()
    form = ChangeBalance()
    if request.method == 'POST':
        if form.validate_on_submit():
            user = session.query(User).filter(User.id == current_user.id).first()
            user.balance += int(request.form['amount'])
            session.commit()
            return redirect('/shop')

    return render_template('balance.html', title='BNS | Баланс', form=form)


@app.route('/profile/change_params', methods=['GET', 'POST'])
@login_required
def change_params():
    session = db_session.create_session()
    if request.method == 'POST':
        user = session.query(User).filter(User.id == current_user.id).first()
        user.surname = request.form['surname']
        user.name = request.form['name']
        user.address = request.form['address']
        session.commit()

    return redirect('/profile')


@app.route('/shop', methods=['GET', 'POST'])
def shop():
    session = db_session.create_session()
    filter_args = request.args.getlist('tags-filter')
    tags = session.query(Tag).all()

    if request.args.get('availability-filter'):
        availability_filter = int(request.args.get('availability-filter'))
    else:
        availability_filter = 0

    if request.args.get('order'):
        order = int(request.args.get('order'))
    else:
        order = 0
    if order == 0:
        products_query = session.query(Product).order_by(Product.price).all()
    elif order == 1:
        products_query = session.query(Product).order_by(Product.price.desc()).all()
    elif order == 2:
        products_query = session.query(Product).order_by(Product.name).all()
    else:
        products_query = session.query(Product).order_by(Product.name).all()

    if filter_args:
        products = []
        for product in products_query:
            if set([i.name for i in product.tags]) & set(filter_args):
                products.append(product)
    else:
        products = products_query

    if request.method == 'POST':
        tag_filter = request.form.getlist('tags-filter')
        availability_filter = request.form.get('availability-filter')
        if availability_filter:
            url = request.base_url + change_url_args(request.url, 'availability-filter', availability_filter)
        else:
            url = request.base_url + change_url_args(request.url, 'availability-filter', '0')
        return redirect(change_url_args(url, 'tags-filter', tag_filter, mode='change_list'))

    return render_template('shop.html', title='BNS | Магазин', products=products, order=order, format_path=format_path,
                           change_url_args=change_url_args, tags=tags, availability_filter=availability_filter,
                           filter=filter_args, str=str)


@app.route('/shop/add-to-cart/<int:id>/<string:prev_adr>', methods=['GET', 'POST'])
def add_to_cart(id, prev_adr='/shop'):
    if not current_user.is_authenticated:
        return redirect('/login')

    session = db_session.create_session()
    user = session.query(User).filter(User.id == current_user.id).first()
    if str(id) + ', ' in user.cart:
        user.cart = user.cart.replace(str(id) + ', ', '')
    else:
        user.cart += str(id) + ', '
    session.commit()
    return redirect(prev_adr.replace(';', '?').replace('|', '/'))


@app.route('/shop/add_product', methods=['GET', 'POST'])
@login_required
def add_product():
    if current_user.access_level < 1:
        abort(403)

    form = AddProductForm()
    session = db_session.create_session()
    chosen_tags = request.form.getlist('tags')
    if form.validate_on_submit() and form.image.validate(form, extra_validators=[FileRequired()]):
        if session.query(Product).filter(Product.name == form.name.data).first():
            return render_template('add_product.html', title='BNS | Добавить продукт',
                                   form=form, tags=session.query(Tag), chosen_tags=chosen_tags,
                                   tag_names=lambda x: [i.name for i in x], message="Товар с таким названием уже есть")
        if not request.form.getlist('tags'):
            return render_template('add_product.html', title='BNS | Добавить продукт',
                                   form=form, tags=session.query(Tag), chosen_tags=chosen_tags,
                                   tag_names=lambda x: [i.name for i in x], message="Выберите хотя бы 1 тег")

        product = Product(name=form.name.data,
                          description=form.description.data,
                          price=form.price.data,
                          amount=form.amount.data)
        for tag in chosen_tags:
            if session.query(Tag).filter(Tag.name == tag).first():
                new_tag = session.query(Tag).filter(Tag.name == tag).first()
            else:
                new_tag = Tag(name=tag)
                session.add(new_tag)
            product.tags.append(new_tag)
        session.add(product)
        session.commit()

        f_name = 'static/images/' + str(product.id) + '.png'
        f = open(f_name, 'wb')
        f.write(form.image.data.read())
        f.close()
        im = Image.open(f_name)
        im.resize((150, 150)).save(f_name)
        return redirect('/shop')
    return render_template('add_product.html', title='BNS | Добавить продукт', form=form, tags=session.query(Tag),
                           chosen_tags=chosen_tags, tag_names=lambda x: [i.name for i in x])


@app.route('/shop/product/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_product(id):
    if current_user.access_level < 1:
        abort(403)

    form = AddProductForm()
    session = db_session.create_session()
    product = session.query(Product).filter(Product.id == id).first()
    if request.method == "GET":
        if product:
            form.name.data = product.name
            form.description.data = product.description
            form.price.data = product.price
            form.amount.data = product.amount
            form.image.label = 'Изменить изображение'
        else:
            abort(404)
    if form.validate_on_submit():
        chosen_tags = request.form.getlist('tags')
        duplicate = session.query(Product).filter(Product.name == form.name.data).first()
        if duplicate:
            if duplicate.id != product.id:
                return render_template('add_product.html', title='BNS | Редактировать продукт',
                                       form=form, tags=session.query(Tag), chosen_tags=chosen_tags,
                                       tag_names=lambda x: [i.name for i in x],
                                       message="Товар с таким названием уже есть")
        if not request.form.getlist('tags'):
            return render_template('add_product.html', title='BNS | Редактировать продукт',
                                   form=form, tags=session.query(Tag), chosen_tags=chosen_tags,
                                   tag_names=lambda x: [i.name for i in x], message="Выберите хотя бы 1 тег")

        if product:
            product.name = form.name.data
            product.description = form.description.data
            product.price = form.price.data
            product.amount = form.amount.data

            product.tags.clear()
            for tag in chosen_tags:
                if session.query(Tag).filter(Tag.name == tag).first():
                    new_tag = session.query(Tag).filter(Tag.name == tag).first()
                else:
                    new_tag = Tag(name=tag)
                    session.add(new_tag)
                if new_tag not in product.tags:
                    product.tags.append(new_tag)

            if form.image.data:
                f_name = 'static/images/' + str(product.id) + '.png'
                f = open(f_name, 'wb')
                f.write(form.image.data.read())
                f.close()
                im = Image.open(f_name)
                im.resize((150, 150)).save(f_name)
            session.commit()
            return redirect('/shop')
        else:
            abort(404)
    return render_template('add_product.html', title='BNS | Редактировать продукт', form=form, tags=session.query(Tag),
                           chosen_tags=[i.name for i in product.tags],
                           tag_names=lambda x: [i.name for i in x])


@app.route('/shop/delete_product/<int:id>')
@login_required
def product_delete(id):
    if current_user.access_level < 1:
        abort(403)

    session = db_session.create_session()
    product = session.query(Product).filter(Product.id == id).first()
    if product:
        for tag in product.tags:
            if len(tag.products) == 1:
                session.delete(tag)
        session.delete(product)
        session.commit()
    else:
        abort(404)
    remove('static/images/' + str(id) + '.png')
    return redirect('/shop')


@app.route('/cart')
def cart():
    if not current_user.is_authenticated:
        return redirect('/login')

    session = db_session.create_session()
    cart_list = session.query(User).filter(User.id == current_user.id).first().cart.split(', ')[:-1]
    products_ids = list(set([int(i) for i in cart_list]))
    products = [session.query(Product).filter(Product.id == i).first() for i in products_ids]
    return render_template('cart.html', title='BNS | Корзина', products=products, str=str, format_path=format_path,
                           get_ids=lambda x: [i.id for i in x])


@app.route('/order/<order_data_unformed>/<total>', methods=['GET', 'POST'])
def order(order_data_unformed, total):
    if not current_user.is_authenticated:
        return redirect('/login')

    order_data = {int(i[0]): int(i[1]) for i in [j.split('-') for j in order_data_unformed.split(';')]}
    session = db_session.create_session()

    order_str = []
    for el in order_data:
        product = session.query(Product).filter(Product.id == el).first()
        product.amount -= order_data[el]
        order_str.append(f'{product.name} {order_data[el]} шт.')

    if current_user.purchase_history:
        history = eval(current_user.purchase_history)
    else:
        history = {}
    date = datetime.now().strftime('%H:%M - %d.%m.%Y')
    if date in history:
        history[date].append((', '.join(order_str), total))
    else:
        history[date] = [(', '.join(order_str), total)]

    user = session.query(User).filter(User.id == current_user.id).first()
    if user.balance < int(total):
        return redirect('/profile/balance')
    else:
        user.balance -= int(total)

    user.purchase_history = str(history)
    user.cart = ''
    session.commit()
    return redirect('/shop')


def main():
    db_session.global_init("db/shop.sqlite")

    session = db_session.create_session()
    print('Аккаунт владельца:\nEmail: mail@mail.ru\nПароль: 321')

    app.run()


if __name__ == '__main__':
    main()
