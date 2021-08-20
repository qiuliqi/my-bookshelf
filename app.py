from flask import Flask, request, render_template, url_for, flash, redirect
from gevent import pywsgi
from flask_sqlalchemy import SQLAlchemy  # 数据库扩展类
import os
import sys
import click
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import LoginManager, UserMixin,login_user, login_required, logout_user,current_user


WIN = sys.platform.startswith('win')
if WIN:  # 如果是 Windows 系统，使用三个斜线
    prefix = 'sqlite:///'
else:  # 否则使用四个斜线
    prefix = 'sqlite:////'

app = Flask(__name__)
app.config['SECRET_KEY'] = 'dev'  # 等同于 app.secret_key = 'dev'
app.config['SQLALCHEMY_DATABASE_URI'] = prefix + os.path.join(app.root_path, 'data.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False  # 关闭对模型修改的监控
# 在扩展类实例化前加载配置
db = SQLAlchemy(app)  # 初始化扩展，传入程序实例 app
login_manager = LoginManager(app)  # 实例化登录扩展类
login_manager.login_view = 'login'


# 用户表
class User(db.Model,UserMixin):  # 表名将会是 user（自动生成，小写处理）
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(20))
    username = db.Column(db.String(20))  # 用户名
    password_hash = db.Column(db.String(128))  # 密码散列值

    def set_password(self, password):  # 用来设置密码的方法，接受密码作为参数
        self.password_hash = generate_password_hash(password)  # 将生成的密码保持到对应字段

    def validate_password(self, password):  # 用于验证密码的方法，接受密码作为参数
        return check_password_hash(self.password_hash, password)  # 返回布尔值


# 留言表
class Movie(db.Model):  # 表名将会是 movie
    id = db.Column(db.Integer, primary_key=True)  # 主键
    content = db.Column(db.String(60))  # 留言内容
    name = db.Column(db.String(6))  # 昵称


# 阅读记录表
class Read(db.Model):  # 表名将会是 read
    id = db.Column(db.Integer, primary_key=True)  # 主键
    uesrname = db.Column(db.String(20))  # 用户名
    bookname = db.Column(db.String(20))  # 书名
    zjid = db.Column(db.Integer)  # 书名


# 初始化数据库
@app.cli.command()  # 注册为命令
@click.option('--drop', is_flag=True, help='删除后创建.')  # 设置选项
def initdb(drop):
    """初始化数据库."""
    if drop:  # 判断是否输入了选项
        db.drop_all()  # 删除数据库
    db.create_all()
    click.echo('已初始化的数据库.')


# 生成管理员账号
@app.cli.command()
@click.option('--username', prompt=True, help='The username used to login.')
@click.option('--password', prompt=True, hide_input=True, confirmation_prompt=True, help='The password used to login.')
def admin(username, password):
    """Create user."""
    db.create_all()

    user = User.query.first()
    if user is not None:
        click.echo('Updating user...')
        user.username = username
        user.set_password(password)  # 设置密码
    else:
        click.echo('Creating user...')
        user = User(username=username, name='Admin')
        user.set_password(password)  # 设置密码
        db.session.add(user)

    db.session.commit()  # 提交数据库会话
    click.echo('Done.')


# 初始化 Flask-Login
@login_manager.user_loader
def load_user(user_id):  # 创建用户加载回调函数，接受用户 ID 作为参数
    user = User.query.get(int(user_id))  # 用 ID 作为 User 模型的主键查询对应的用户
    return user  # 返回用户对象


# 首页
@app.route('/', methods=['GET', 'POST'])
def index():
    # 处理新增留言
    if request.method == 'POST':  # 判断是否是 POST 请求
        # 获取表单数据
        content = request.form.get('content')  # 传入表单对应输入字段的 name 值
        name = request.form.get('name')
        # 验证数据
        if not content or not name or len(name) > 6 or len(content) > 60:
            flash('输入无效.')  # 显示错误提示
            return redirect(url_for('index'))  # 重定向回主页
        # 保存表单数据到数据库
        movie = Movie(content=content, name=name)  # 创建记录
        db.session.add(movie)  # 添加到数据库会话
        db.session.commit()  # 提交数据库会话
        flash('您的留言已提交成功.')
        return redirect(url_for('index'))  # 重定向回主页
    # 读取留言信息
    ly_lists = Movie.query.all()
    # 读取小说列表
    book_lists = os.listdir('static/book')
    return render_template('index.html', book_lists=book_lists, ly_lists=ly_lists)


# 登录页
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        if not username or not password:
            flash('输入无效.')
            return redirect(url_for('login'))

        user = User.query.filter_by(username=username).first()
        if user:
            # 验证用户名和密码是否一致
            if username == user.username and user.validate_password(password):
                login_user(user)  # 登入用户
                flash(current_user.username + '，欢迎回家！')
                return redirect(url_for('index'))  # 重定向到主页

        flash('无效的用户名或密码.')  # 如果验证失败，显示错误消息
        return redirect(url_for('login'))  # 重定向回登录页面

    return render_template('login.html')


# 注册页
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        # 检测正确性
        if not username or not password or len(username) > 20 or len(password) > 20:
            flash('输入无效.')
            return redirect(url_for('signup'))
        # 调戏大佬
        if username.lower() == 'admin':
            flash('大佬，管理员是小秋秋哦！')
            return redirect(url_for('signup'))
        # 检查账号重复项
        users = User.query.filter_by(username=username).first()
        if users:  # 如果查询到，则重复
            flash('注册账号重复，请重新输入！')
            return redirect(url_for('signup'))
        else:  # 没有查询到，则注册
            user = User(username=username, name=username)
            user.set_password(password)  # 设置密码
            db.session.add(user)
            db.session.commit()  # 提交数据库会话
            flash('注册成功！')
            return redirect(url_for('login'))  # 前往登录页

    return render_template('signup.html')


# 会员管理
@app.route('/admin')
@login_required  # 用于视图保护，后面会详细介绍
def admin():
    if current_user.id == 1:  # 如果会员id为 1
        # 查询所有会员信息
        admins = User.query.all()
        return render_template('admin.html', admins=admins)


# 删除会员
@app.route('/admin/delete/<int:admin_id>', methods=['POST'])
@login_required  # 用于视图保护，后面会详细介绍
def admindelete(admin_id):
    if admin_id != 1:
        admim = User.query.get_or_404(admin_id)  # 获取会员记录
        name = admim.username
        # 删除阅读记录
        readjls = Read.query.filter_by(uesrname=name).all()
        if readjls:
            for readjl in readjls:
                db.session.delete(readjl)
        # 删除会员
        db.session.delete(admim)
        db.session.commit()  # 提交数据库会话
        flash('会员已删除！')

    return redirect(url_for('admin'))  # 重定向回会员页


# 登出页
@app.route('/logout')
@login_required  # 用于视图保护，后面会详细介绍
def logout():
    logout_user()  # 登出用户
    flash('欢迎下次光临！')
    return redirect(url_for('index'))  # 重定向回首页


# 删除留言
@app.route('/movie/delete/<int:movie_id>', methods=['POST'])  # 限定只接受 POST 请求
@login_required  # 用于视图保护，后面会详细介绍
def delete(movie_id):
    movie = Movie.query.get_or_404(movie_id)  # 获取电影记录
    db.session.delete(movie)  # 删除对应的记录
    db.session.commit()  # 提交数据库会话
    flash('留言已删除.')
    return redirect(url_for('index'))  # 重定向回主页


# 目录页
@app.route('/book/<book_id>')
def book_page(book_id='许仙志.txt'):
    book_path = 'static/book/' + book_id
    with open(book_path, 'r', encoding='utf-8') as f:
        txts = f.readlines()
    nums = int(len(txts) / 100) + 1
    page_nums = range(1, int(nums))
    return render_template('page.html', book_id=book_id, page_nums=page_nums)


# 阅读记录
@app.route('/record')
@login_required  # 用于视图保护，后面会详细介绍
def record():
    # 数据库查找阅读记录
    zj_ids = Read.query.filter_by(uesrname=current_user.username).all()  # 返回包含所有查询记录的列表
    return render_template('record.html', zj_ids=zj_ids)


# 阅读页
@app.route('/<book_id>/<int:movie_id>', methods=['GET', 'POST'])
def home(book_id='许仙志.txt', movie_id=1):
    book_path = 'static/book/' + book_id
    with open(book_path, 'r', encoding='utf-8') as f:
        txts = f.readlines()
    # 如果已经登录，则记录阅读记录
    if current_user.is_authenticated:
        username = current_user.username
        if movie_id == 1:  # 如果直接点阅读访问第一章，则查询阅读记录
            xj_ids = Read.query.filter_by(uesrname=username, bookname=book_id).first()
            if xj_ids:  # 如果查询到，这读取章节id
                movie_id = xj_ids.zjid
            else:  # 如果查询不到到，则创建记录
                r1 = Read(uesrname=username, bookname=book_id, zjid=movie_id)  # # 创建一个 Read 记录
                db.session.add(r1)  # 把新创建的记录添加到数据库会话
                db.session.commit()  # 提交数据库会话，只需要在最后调用一次即可
        else:  # 如果不是阅读第一章，则更新阅读记录
            xj_ids = Read.query.filter_by(uesrname=username, bookname=book_id).first()
            if xj_ids:
                xj_ids.zjid = movie_id
                db.session.commit()  # 注意仍然需要调用这一行来提交改动
            else:  # 如果查询不到到，则创建记录
                r1 = Read(uesrname=username, bookname=book_id, zjid=movie_id)  # # 创建一个 Read 记录
                db.session.add(r1)  # 把新创建的记录添加到数据库会话
                db.session.commit()  # 提交数据库会话，只需要在最后调用一次即可

                # 更新
                xj_ids = Read.query.filter_by(uesrname=username, bookname=book_id).first()
                xj_ids.zjid = movie_id
                db.session.commit()  # 注意仍然需要调用这一行来提交改动

    txt_mun = movie_id * 100
    return render_template('home.html', book_id=book_id, movie_id=movie_id, contents=txts[txt_mun-100:txt_mun])


@app.errorhandler(404)  # 传入要处理的错误代码
def page_not_found(e):  # 接受异常对象作为参数
    return render_template('404.html'), 404  # 返回模板和状态码


if __name__ == '__main__':
    server = pywsgi.WSGIServer(('0.0.0.0', 5000), app)
    server.serve_forever()
