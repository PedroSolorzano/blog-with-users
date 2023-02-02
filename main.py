from flask import Flask, render_template, redirect, url_for, flash, request, abort
from flask_bootstrap import Bootstrap
from flask_ckeditor import CKEditor
from datetime import date
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import relationship
from flask_login import UserMixin, login_user, LoginManager, login_required, current_user, logout_user
from forms import CreatePostForm, RegisterForm, LoginForm, CommentForm
from flask_gravatar import Gravatar
from functools import wraps
from sqlalchemy import ForeignKey
import os
import re

# Time
from datetime import datetime
time = datetime.now()


app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('8BYkEfBA6O6donzWlSihBXox7C0sKR6b')
ckeditor = CKEditor(app)
Bootstrap(app)

# CONNECT TO DB
app.app_context().push()
uri = os.getenv("DATABASE_URL")  # or other relevant config var
if uri and uri.startswith("postgres://"):
    uri = uri.replace("postgres://", "postgresql://", 1)
# rest of connection code using the connection string `uri`
app.config['SQLALCHEMY_DATABASE_URI'] = uri
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Login Manager
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Gravatar
gravatar = Gravatar(app,
                    size=100,
                    rating='g',
                    default='retro',
                    force_default=False,
                    force_lower=False,
                    use_ssl=False,
                    base_url=None)


# CONFIGURE TABLES
class User(db.Model, UserMixin):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100), nullable=False, unique=True)
    password = db.Column(db.String(100), nullable=False)
    name = db.Column(db.String(1000), nullable=False)
    comments = relationship("Comment", back_populates="comment_author")
    posts = relationship("BlogPost", back_populates="author")


class BlogPost(db.Model):
    __tablename__ = "blog_posts"
    id = db.Column(db.Integer, primary_key=True)
    author_id = db.Column(db.Integer, ForeignKey('users.id'))
    author = relationship("User", back_populates="posts")
    title = db.Column(db.String(250), unique=True, nullable=False)
    subtitle = db.Column(db.String(250), nullable=False)
    date = db.Column(db.String(250), nullable=False)
    body = db.Column(db.Text, nullable=False)
    img_url = db.Column(db.String(250), nullable=False)
    comments = relationship("Comment", back_populates="parent_post")


class Comment(db.Model):
    __tablename__ = "comments"
    id = db.Column(db.Integer, primary_key=True)
    author_id = db.Column(db.Integer, ForeignKey('users.id'))
    comment_author = relationship("User", back_populates="comments")
    post_id = db.Column(db.Integer, ForeignKey('blog_posts.id'))
    parent_post = relationship("BlogPost", back_populates="comments")
    text = db.Column(db.String(1000), nullable=False)


db.create_all()


# LoginManager
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(user_id)


# Decorators
def admin_only(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # If id is not 2 then return abort with 403 error
        if current_user.id != 1:
            return abort(403)
        # Otherwise continue with the route function
        return f(*args, **kwargs)
    return decorated_function


# Routes
@app.route('/')
def get_all_posts():
    posts = db.session.query(BlogPost).all()
    return render_template("index.html", all_posts=posts, logged_in=current_user.is_authenticated)


@app.route('/register', methods=['POST', 'GET'])
def register():
    login_form = LoginForm()
    register_form = RegisterForm()
    user = User.query.filter_by(email=register_form.email.data).first()
    if request.method == 'POST' and register_form.validate_on_submit() and not user:
        hashed_password = generate_password_hash(register_form.password.data, method='sha256', salt_length=8)
        new_user = User(email=register_form.email.data,
                        password=hashed_password,
                        name=register_form.name.data)
        db.session.add(new_user)
        db.session.commit()
        # Login user
        login_user(new_user)
        return redirect(url_for('get_all_posts', logged_in=current_user.is_authenticated))
    elif request.method == 'POST' and register_form.validate_on_submit() and user:
        flash('That user already exists, log in instead!')
        return redirect(url_for('login', form=login_form, logged_in=current_user.is_authenticated))
    else:
        return render_template("register.html", form=register_form, logged_in=current_user.is_authenticated)


@app.route('/login', methods=['POST', 'GET'])
def login():
    login_form = LoginForm()
    register_form = RegisterForm()
    if request.method == 'GET':
        return render_template("login.html", form=login_form, logged_in=current_user.is_authenticated)

    if request.method == 'POST' and login_form.validate_on_submit():
        user = User.query.filter_by(email=login_form.email.data).first()

        if not user:
            flash("This email doesn't exist, please register first.")
            return redirect(url_for('register', form=register_form, logged_in=current_user.is_authenticated))
        elif current_user.is_active:
            flash('User already logged in.')
            return redirect(url_for('login', form=login_form, logged_in=current_user.is_authenticated))
        elif user and check_password_hash(user.password, login_form.password.data):
            # Login user
            login_user(user)
            return redirect(url_for('get_all_posts', logged_in=current_user.is_authenticated))
        else:
            flash('Incorrect password, please try again.')
            return redirect(url_for('login', form=login_form, logged_in=current_user.is_authenticated))


@app.route('/logout')
def logout():
    if current_user.is_authenticated:
        logout_user()
        return redirect(url_for('get_all_posts', logged_in=current_user.is_authenticated))
    else:
        return redirect(url_for('get_all_posts', logged_in=current_user.is_authenticated))


@app.route("/post/<int:post_id>", methods=["GET", "POST"])
@login_required
def show_post(post_id):
    comment_form = CommentForm()
    if request.method == 'GET':
        requested_post = BlogPost.query.get(post_id)
        return render_template("post.html",
                               post=requested_post,
                               logged_in=current_user.is_authenticated,
                               form=comment_form,
                               time=time)
    elif request.method == 'POST' and comment_form.validate_on_submit():
        new_comment = Comment(
            author_id=current_user.id,
            post_id=post_id,
            text=comment_form.body.data)
        db.session.add(new_comment)
        db.session.commit()
        return redirect(url_for('show_post',
                                post_id=post_id,
                                logged_in=current_user.is_authenticated,
                                time=time))


@app.route("/about")
def about():
    return render_template("about.html", logged_in=current_user.is_authenticated)


@app.route("/contact")
def contact():
    return render_template("contact.html", logged_in=current_user.is_authenticated)


@app.route("/new-post", methods=["POST", "GET"])
@login_required
@admin_only
def add_new_post():
    form = CreatePostForm()
    if request.method == "POST" and form.validate_on_submit():
        new_post = BlogPost(
            author_id=current_user.id,
            title=form.title.data,
            subtitle=form.subtitle.data,
            body=form.body.data,
            img_url=form.img_url.data,
            author=current_user,
            date=date.today().strftime("%B %d, %Y")
        )
        db.session.add(new_post)
        db.session.commit()
        return redirect(url_for("get_all_posts", logged_in=current_user.is_authenticated))
    else:
        return render_template("make-post.html", form=form, logged_in=current_user.is_authenticated)


@app.route("/edit-post/<int:post_id>", methods=["POST", "GET"])
@login_required
@admin_only
def edit_post(post_id):
    post = BlogPost.query.get(post_id)
    edit_form = CreatePostForm(
        title=post.title,
        subtitle=post.subtitle,
        img_url=post.img_url,
        body=post.body
    )
    if request.method == "POST" and edit_form.validate_on_submit():
        post.title = edit_form.title.data
        post.subtitle = edit_form.subtitle.data
        post.img_url = edit_form.img_url.data
        post.body = edit_form.body.data
        db.session.commit()
        return redirect(url_for("show_post", post_id=post.id, logged_in=current_user.is_authenticated))
    else:
        return render_template("make-post.html", form=edit_form, logged_in=current_user.is_authenticated)


@app.route("/delete/<int:post_id>")
@login_required
@admin_only
def delete_post(post_id):
    post_to_delete = BlogPost.query.get(post_id)
    db.session.delete(post_to_delete)
    db.session.commit()
    return redirect(url_for('get_all_posts', logged_in=current_user.is_authenticated))


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True)
