from flask import Flask, render_template, redirect, url_for, flash, request, g, abort
from flask_bootstrap import Bootstrap
from flask_ckeditor import CKEditor
from datetime import date
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import relationship
from flask_login import UserMixin, login_user, LoginManager, login_required, current_user, logout_user
from flask_gravatar import Gravatar
from forms import RegisterForm, LoginForm, CreatePostForm, CommentForm
from functools import wraps
from sqlalchemy import Table, Column, Integer, ForeignKey
import os




app = Flask(__name__)
# app.config['SECRET_KEY'] = '8BYkEfBA6O6donzWlSihBXox7C0sKR6b' #sqlite
app.config['SECRET_KEY'] = os.environ.get("SECRET_KEY") #postgre

ckeditor = CKEditor(app)
Bootstrap(app)

##CONNECT TO DB
# app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///blog.db'  #sqlite
# app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get("DATABASE_URL") #postgre
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get("DATABASE_URL",  "sqlite:///blog.db")

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

login_manager = LoginManager()
login_manager.init_app(app)


##CREATE BLOG TABLE IN DB

class User(UserMixin, db.Model):
    __tablename__ = "user" #⭐️先生の回答にはこの行がある
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(100))
    name = db.Column(db.String(1000))
    # One to Many relationship Between the User Table (Parent) and the Comment table
    posts = relationship("BlogPost", back_populates="author")
    comments = relationship("Comment", back_populates="commenter")


class BlogPost(db.Model):
    __tablename__ = "blog_posts"
    id = db.Column(db.Integer, primary_key=True)
    author = db.Column(db.String(250), nullable=False)
    title = db.Column(db.String(250), unique=True, nullable=False)
    subtitle = db.Column(db.String(250), nullable=False)
    date = db.Column(db.String(250), nullable=False)
    body = db.Column(db.Text, nullable=False)
    img_url = db.Column(db.String(250), nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    author = relationship("User", back_populates="posts")

    # One to Many relationship between each BlogPost object (Parent) and Comment object
    comments = relationship("Comment", back_populates="posts")


class Comment(db.Model):
    __tablename__ = "comments"
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.Text, nullable=False)

    # One to Many relationship Between the User Table (Parent) and the Comment table
    commenter_id = db.Column(db.Integer, ForeignKey('user.id'))
    commenter = relationship("User", back_populates="comments")

    # One to Many relationship between each BlogPost object (Parent) and Comment object
    posts_id = db.Column(db.Integer, ForeignKey('blog_posts.id'))
    posts = relationship("BlogPost", back_populates="comments")


# CREATE ALL TABLES
db.create_all()


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


def admin_only(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        #If id is not 1 then return abort with 403 error
        if current_user.id != 1:
            return abort(403)
        #Otherwise continue with the route function
        return f(*args, **kwargs)
    return decorated_function


@app.route('/')
def get_all_posts():
    #下の方法だと、ログアウトした時にエラーが出てしまう⭐️解消方法が分からないので、adminを渡すのをやめて、先生の方法に合わせている
    # admin = False
    posts = BlogPost.query.all()

    # # Only Admin user can edit/post/delete posts.
    # if current_user.id == 1:
    #     admin = True
    return render_template("index.html", all_posts=posts, logged_in=current_user.is_authenticated)
    # return render_template("index.html", all_posts=posts, logged_in=current_user.is_authenticated, admin=admin)


@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegisterForm()
    if form.validate_on_submit():

        if db.session.query(User).filter(User.email==form.email.data).limit(1).all():
            #User already exists
            flash("You've already signed up with that email, log in instead!")
            return redirect(url_for('login'))

        # パスワードの平文を、暗号化（モデル）
        password_salted = generate_password_hash(
            form.password.data,
            method='pbkdf2:sha256',
            salt_length=8
        )

        #モデル（DBにアクセスする部分）
        new_user = User(
            email=form.email.data,
            password=password_salted,
            name=form.name.data
        )
        db.session.add(new_user)
        db.session.commit()

        #register後、自動login
        login_user(new_user)
        return redirect(url_for('get_all_posts'))
    return render_template("register.html", form=form)


@app.route('/login', methods=['GET', 'POST'])
def login():

    form = LoginForm()
    #　先にfalseの場合には、if文から抜けたい
    if not form.validate_on_submit():
        return render_template("login.html", form=form, logged_in=current_user.is_authenticated)

    mail = form.email.data
    password = form.password.data

    user = User.query.filter_by(email=mail).first()
    print(user)

    if not user:
        flash('The email does not exist. Please try again.')
        return redirect(url_for('login'))

    print("check_password_hash(user.password, password)", check_password_hash(user.password, password))
    if not check_password_hash(user.password, password):
        flash('Password is incorrect')
        return redirect(url_for('login'))

    login_user(user)
    # flash('Logged in successfully.')  #ログアウトしても、flashはcoockieで残っているので、表示される
    return redirect(url_for('get_all_posts'))



@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('get_all_posts'))


@app.route("/post/<int:post_id>", methods=['GET', 'POST'])
def show_post(post_id):
    form = CommentForm()
    # admin = False
    # # Only Admin user can edit/post/delete posts.
    # if current_user.id == 1:
    #     admin = True

    if form.validate_on_submit():
        if not current_user.is_authenticated:
            flash("You need to login or register to comment")
            return redirect(url_for('login'))

        new_comment = Comment(
            text=form.comments.data,
            commenter=current_user,
            posts_id=post_id
        )

        db.session.add(new_comment)
        db.session.commit()
        return redirect(url_for("get_all_posts"))

    all_comments = Comment.query.filter_by(posts_id=post_id).all()
    print(all_comments)

    Gravatar(app,
             size=100,
             rating='g',
             default='retro',
             force_default=False,
             force_lower=False,
             use_ssl=False,
             base_url=None)
    gravatar = Gravatar()

    requested_post = BlogPost.query.get(post_id) #これって、何のために必要？自分で追加してる。
    return render_template \
        ("post.html",
         post=requested_post,
         logged_in=current_user.is_authenticated,
         form=form,
         all_comments=all_comments,
         gravatar=gravatar
         )

    # return render_template("post.html", post=requested_post, admin=admin)


@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/contact")
def contact():
    return render_template("contact.html")


@app.route("/new-post", methods=['GET', 'POST'])
@login_required
@admin_only
def add_new_post():

    # # Only Admin user can edit/post/delete posts.
    # if current_user.id == 1:
    #     admin = True

    form = CreatePostForm()
    if form.validate_on_submit():
        new_post = BlogPost(
            title=form.title.data,
            subtitle=form.subtitle.data,
            body=form.body.data,
            img_url=form.img_url.data,
            author=current_user,
            date=date.today().strftime("%B %d, %Y")
        )
        db.session.add(new_post)
        db.session.commit()
        return redirect(url_for("get_all_posts"))
    return render_template("make-post.html", form=form, logged_in=current_user.is_authenticated)
    # return render_template("make-post.html", form=form, admin=admin)



@app.route("/edit-post/<int:post_id>", methods=['GET', 'POST'])
@admin_only
def edit_post(post_id):
    post = BlogPost.query.get(post_id)
    edit_form = CreatePostForm(
        title=post.title,
        subtitle=post.subtitle,
        img_url=post.img_url,
        # author=post.author,
        body=post.body
    )
    if edit_form.validate_on_submit():
        post.title = edit_form.title.data
        post.subtitle = edit_form.subtitle.data
        post.img_url = edit_form.img_url.data
        # post.author = edit_form.author.data #⭐️ AttributeError: 'CreatePostForm' object has no attribute 'author'
        post.body = edit_form.body.data
        db.session.commit()
        return redirect(url_for("show_post", post_id=post.id))

    return render_template("make-post.html", form=edit_form)


@app.route("/delete/<int:post_id>")
@admin_only
def delete_post(post_id):
    post_to_delete = BlogPost.query.get(post_id)
    db.session.delete(post_to_delete)
    db.session.commit()
    return redirect(url_for('get_all_posts'))


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)
