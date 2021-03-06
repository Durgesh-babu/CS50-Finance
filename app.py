import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True


# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    portifolio = db.execute("SELECT * FROM portifolio WHERE user_id = ?",session["user_id"])
    rows = db.execute("SELECT cash FROM users WHERE id = ?",session["user_id"])
    cash = rows[0]["cash"]
    total = cash
    for stock in portifolio:
        total += stock["price"]
        rows = lookup(stock["symbol"])
        stock["price"] = rows["price"]
    return render_template("index.html",portifolio=portifolio,cash=cash,total=total)



@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "POST":
        shares = float(request.form.get("shares"))
        symbol = request.form.get("symbol")
        if shares < 0:
            return apology("Invalid number of shares")
        if not symbol:
            return apology("Invalid symbol")
        rows = db.execute("SELECT cash FROM users WHERE id = ?",session["user_id"])
        cash = rows[0]["cash"]
        symbol = symbol.upper()
        stock = lookup(symbol)
        if stock == None:
            return apology("Symbol does not exist")

        price = float(stock["price"])
        total = price * shares
        
        # Checking if the user can buy the stock
        if total <= cash:
            cash = cash - total
            db.execute("UPDATE users SET cash = ? WHERE id = ?",cash,session["user_id"])
            try:
                db.execute("INSERT INTO portifolio (user_id, name, symbol, shares, price, total) VALUES (?,?,?,?,?,?)",session["user_id"],stock["name"],symbol,shares,price,total)
            except:
                rows = db.execute("SELECT * FROM portifolio WHERE user_id = ? AND symbol = ?",session["user_id"],symbol)
                db.execute("UPDATE portifolio SET shares = ?, price = ?, total = ? WHERE symbol = ? AND user_id = ?",rows[0]["shares"] + shares,price, rows[0]["total"] + total,symbol,session["user_id"])
        else:
            return apology("Sorry not enough cash")
        db.execute("INSERT INTO history (user_id, symbol, shares, price) VALUES (?,?,?,?)",session["user_id"],symbol,shares,price)
        return redirect("/")
    else:
        return render_template("buy.html")



@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    history = db.execute("SELECT * FROM history WHERE user_id = ?",session["user_id"])
    for stock in history:
        rows = lookup(stock["symbol"])
        stock["price"] = rows["price"]
    return render_template("history.html",history=history)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    if request.method == "POST":
        symbol = request.form.get("symbol")
        if not symbol:
            return apology("Please privide a symbol")
        symbol = symbol.upper()
        stock = lookup(symbol)
        if stock == None:
            return apology("Such symbol does not exist")
        return render_template("quoted.html",name = stock["name"],symbol=stock["symbol"],price=stock["price"])

    else:
        return render_template('quote.html')


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")

        if not username:
            return apology("Please provide username")

        if not password:
            return apology("Please provide password")

        if password != confirmation:
            return apology("Passwords dont match")

        hash = generate_password_hash(password)

        try:
            user_id = db.execute("INSERT INTO users(username,hash) VALUES(?,?)",username,hash)
        except:
            return apology("User already exists")

        session["user_id"] = user_id
        
        return redirect("/")
    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    if request.method == "POST":
        shares = float(request.form.get("shares"))
        symbol = request.form.get("symbol")
        try:
            rows = db.execute("SELECT * FROM portifolio WHERE user_id = ? AND symbol = ?",session["user_id"],symbol)
        except:
            return apology("Invalid symbol")
        if shares < 0 or shares > rows[0]["shares"]:
            return apology("Invalid number of shares")
        
        user = db.execute("SELECT cash FROM users WHERE id = ?",session["user_id"])
        cash = user[0]["cash"]

        stock = lookup(symbol)
        price = float(stock["price"])
        total = price * shares
        
        cash = cash + total
        db.execute("UPDATE users SET cash = ? WHERE id = ?",cash,session["user_id"])
        db.execute("UPDATE portifolio SET shares = ?, price = ?, total = ? WHERE user_id = ? AND symbol = ?",rows[0]["shares"]-shares,price,total,session["user_id"],symbol)
        
        db.execute("INSERT INTO history (user_id, symbol, shares, price) VALUES (?,?,?,?)",session["user_id"],symbol,-shares,price)
        return redirect("/")
    else:
        return render_template("sell.html")


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
