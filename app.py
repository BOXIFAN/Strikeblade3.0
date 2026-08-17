import json
import os
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from flask import Flask, jsonify, redirect, render_template, request, session, url_for


app = Flask(__name__)
app.secret_key = os.environ.get("APP_SECRET_KEY", "dev-secret-change-before-deploy")
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
PRODUCTS_FILE = DATA_DIR / "products.json"
ARTICLES_FILE = DATA_DIR / "articles.json"
PRODUCT_UPLOAD_DIR = BASE_DIR / "static" / "uploads" / "products"
ARTICLE_UPLOAD_DIR = BASE_DIR / "static" / "uploads" / "articles"
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
MANAGE_USERNAME = os.environ.get("MANAGE_USERNAME", "uniquede")
MANAGE_PASSWORD = os.environ.get("MANAGE_PASSWORD", "350234")
WEAPON_TYPES = [
    "单手",
    "双手",
    "综合",
]
PRODUCT_ORIGINS = [
    "欧洲",
    "亚洲",
    "亚欧大陆风格",
]
PRODUCT_PERIODS = [
    "古代（公元前-500）",
    "中世纪（500-1500）",
    "近世（1500-1800）",
    "近代（1800-1914）",
    "现代（1914至今）",
    "综合时期",
]


def ensure_storage():
    DATA_DIR.mkdir(exist_ok=True)
    PRODUCT_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    ARTICLE_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    if not PRODUCTS_FILE.exists():
        PRODUCTS_FILE.write_text("[]\n", encoding="utf-8")
    if not ARTICLES_FILE.exists():
        ARTICLES_FILE.write_text("[]\n", encoding="utf-8")


def load_products():
    ensure_storage()
    return json.loads(PRODUCTS_FILE.read_text(encoding="utf-8"))


def save_products(products):
    ensure_storage()
    PRODUCTS_FILE.write_text(
        json.dumps(products, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def load_articles(include_drafts=False):
    ensure_storage()
    articles = json.loads(ARTICLES_FILE.read_text(encoding="utf-8"))
    if include_drafts:
        return articles
    return [article for article in articles if article.get("status") == "发布"]


def save_articles(articles):
    ensure_storage()
    ARTICLES_FILE.write_text(
        json.dumps(articles, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def get_product(product_id):
    return next((product for product in load_products() if product["id"] == product_id), None)


def get_article(article_id, include_drafts=False):
    return next(
        (article for article in load_articles(include_drafts=include_drafts) if article["id"] == article_id),
        None,
    )


def save_uploaded_file(file_storage, upload_dir=PRODUCT_UPLOAD_DIR, url_prefix="uploads/products"):
    if not file_storage or not file_storage.filename:
        return ""

    extension = Path(file_storage.filename).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        return ""

    filename = f"{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid4().hex[:8]}{extension}"
    upload_dir.mkdir(parents=True, exist_ok=True)
    file_storage.save(upload_dir / filename)
    return f"{url_prefix}/{filename}"


def product_from_form(existing=None):
    existing = existing or {}
    main_image = save_uploaded_file(request.files.get("main_image")) or existing.get("main_image", "")
    removed_images = set(request.form.getlist("remove_detail_images"))
    detail_images = [
        image for image in existing.get("detail_images", []) if image not in removed_images
    ]
    detail_images.extend(
        path for path in (save_uploaded_file(file) for file in request.files.getlist("detail_images")) if path
    )

    return {
        "id": existing.get("id", uuid4().hex),
        "name": request.form.get("name", "").strip(),
        "category": request.form.get("category", existing.get("category", "")).strip(),
        "weapon_type": request.form.get("weapon_type", "").strip(),
        "origin": request.form.get("origin", "").strip(),
        "period": request.form.get("period", "").strip(),
        "status": request.form.get("status", "正在销售"),
        "steel": request.form.get("steel", "").strip(),
        "length": request.form.get("length", "").strip(),
        "price_note": request.form.get("price_note", "").strip(),
        "summary": request.form.get("summary", "").strip(),
        "description": request.form.get("description", "").strip(),
        "main_image": main_image,
        "detail_images": detail_images,
        "show_on_home": request.form.get("show_on_home") == "on",
        "updated_at": datetime.now().isoformat(timespec="seconds"),
    }


def article_from_form(existing=None):
    existing = existing or {}
    cover_image = (
        save_uploaded_file(
            request.files.get("cover_image"),
            ARTICLE_UPLOAD_DIR,
            "uploads/articles",
        )
        or existing.get("cover_image", "")
    )

    return {
        "id": existing.get("id", uuid4().hex),
        "title": request.form.get("title", "").strip(),
        "summary": request.form.get("summary", "").strip(),
        "status": request.form.get("status", "草稿"),
        "cover_image": cover_image,
        "content_html": request.form.get("content_html", "").strip(),
        "updated_at": datetime.now().isoformat(timespec="seconds"),
    }


@app.route("/")
def index():
    products = [
        product
        for product in load_products()
        if product.get("show_on_home") and product.get("status") in {"正在销售", "开团"}
    ]
    return render_template("index.html", products=products)


@app.route("/products")
def all_products():
    selected_type = request.args.get("type", "全部")
    selected_origin = request.args.get("origin", "全部")
    selected_period = request.args.get("period", "全部")
    products = [
        product
        for product in load_products()
        if product.get("status") != "隐藏"
    ]

    if selected_type != "全部":
        products = [
            product for product in products if product.get("weapon_type") == selected_type
        ]

    if selected_origin != "全部":
        products = [
            product for product in products if product.get("origin") == selected_origin
        ]

    if selected_period != "全部":
        products = [
            product for product in products if product.get("period") == selected_period
        ]

    return render_template(
        "products.html",
        products=products,
        weapon_types=WEAPON_TYPES,
        product_origins=PRODUCT_ORIGINS,
        product_periods=PRODUCT_PERIODS,
        selected_type=selected_type,
        selected_origin=selected_origin,
        selected_period=selected_period,
    )


@app.route("/products/<product_id>")
def product_detail(product_id):
    product = get_product(product_id)
    if not product:
        return redirect(url_for("index"))
    return render_template("product_detail.html", product=product)


@app.route("/buying-guide")
def buying_guide():
    return render_template("buying_guide.html")


@app.route("/research")
def research():
    return render_template("articles.html", articles=load_articles())


@app.route("/research/<article_id>")
def article_detail(article_id):
    article = get_article(article_id)
    if not article:
        return redirect(url_for("research"))
    return render_template("article_detail.html", article=article)


@app.route("/custom")
def custom():
    return render_template("custom.html")


@app.route("/contact")
def contact():
    return render_template("contact.html")


@app.route("/manage", methods=["GET", "POST"])
def manage():
    if not session.get("manage_authenticated"):
        username_matches = request.form.get("username") == MANAGE_USERNAME
        password_matches = request.form.get("password") == MANAGE_PASSWORD
        if request.method == "POST" and username_matches and password_matches:
            session["manage_authenticated"] = True
            return redirect(url_for("manage"))
        return render_template("manage_login.html")

    products = load_products()
    articles = load_articles(include_drafts=True)
    edit_id = request.args.get("edit")
    article_edit_id = request.args.get("article_edit")
    editing_product = next((product for product in products if product["id"] == edit_id), None)
    editing_article = next((article for article in articles if article["id"] == article_edit_id), None)

    if request.method == "POST":
        if not request.form.get("name", "").strip():
            return redirect(url_for("manage"))

        product_id = request.form.get("product_id")
        existing = next((product for product in products if product["id"] == product_id), None)
        product = product_from_form(existing)

        if existing:
            products = [product if item["id"] == product["id"] else item for item in products]
        else:
            products.insert(0, product)

        save_products(products)
        return redirect(url_for("manage"))

    return render_template(
        "manage.html",
        products=products,
        articles=articles,
        weapon_types=WEAPON_TYPES,
        product_origins=PRODUCT_ORIGINS,
        product_periods=PRODUCT_PERIODS,
        editing_product=editing_product,
        editing_article=editing_article,
    )


@app.post("/manage/products/<product_id>/delete")
def delete_product(product_id):
    if not session.get("manage_authenticated"):
        return redirect(url_for("manage"))

    products = [product for product in load_products() if product["id"] != product_id]
    save_products(products)
    return redirect(url_for("manage"))


@app.post("/manage/articles")
def save_article():
    if not session.get("manage_authenticated"):
        return redirect(url_for("manage"))

    if not request.form.get("title", "").strip():
        return redirect(url_for("manage"))

    articles = load_articles(include_drafts=True)
    article_id = request.form.get("article_id")
    existing = next((article for article in articles if article["id"] == article_id), None)
    article = article_from_form(existing)

    if existing:
        articles = [article if item["id"] == article["id"] else item for item in articles]
    else:
        articles.insert(0, article)

    save_articles(articles)
    return redirect(url_for("manage"))


@app.post("/manage/articles/upload-image")
def upload_article_image():
    if not session.get("manage_authenticated"):
        return jsonify({"error": "unauthorized"}), 401

    image_path = save_uploaded_file(
        request.files.get("image"),
        ARTICLE_UPLOAD_DIR,
        "uploads/articles",
    )
    if not image_path:
        return jsonify({"error": "invalid image"}), 400
    return jsonify({"url": url_for("static", filename=image_path), "path": image_path})


@app.post("/manage/articles/<article_id>/delete")
def delete_article(article_id):
    if not session.get("manage_authenticated"):
        return redirect(url_for("manage"))

    articles = [article for article in load_articles(include_drafts=True) if article["id"] != article_id]
    save_articles(articles)
    return redirect(url_for("manage"))


@app.route("/manage/logout")
def manage_logout():
    session.pop("manage_authenticated", None)
    return redirect(url_for("manage"))


if __name__ == "__main__":
    app.run(debug=True)
