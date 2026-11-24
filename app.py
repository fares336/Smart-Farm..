import os, csv, io, sqlite3, secrets
from datetime import datetime, timezone
from functools import wraps
from flask import Flask, render_template, request, jsonify, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash

BASE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE, "instance", "smartfarm.db")
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-this-before-deployment-" + secrets.token_hex(8))
DEVICE_TOKEN = os.environ.get("DEVICE_TOKEN", "change-device-token")

def db():
    os.makedirs(os.path.dirname(DB), exist_ok=True)
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    return con

def init_db():
    with db() as con:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, username TEXT UNIQUE, password TEXT);
        CREATE TABLE IF NOT EXISTS farms(id INTEGER PRIMARY KEY, user_id INTEGER, name TEXT, country TEXT, city TEXT);
        CREATE TABLE IF NOT EXISTS zones(id INTEGER PRIMARY KEY, farm_id INTEGER, zone_code TEXT, moisture REAL, ec REAL, soil_temp REAL, updated_at TEXT, source TEXT DEFAULT 'manual');
        CREATE TABLE IF NOT EXISTS readings(id INTEGER PRIMARY KEY, farm_id INTEGER, zone_code TEXT, moisture REAL, ec REAL, soil_temp REAL, created_at TEXT, source TEXT);
        CREATE TABLE IF NOT EXISTS pump_requests(id INTEGER PRIMARY KEY, farm_id INTEGER, zone_code TEXT, pump_type TEXT, requested_amount REAL, unit TEXT, status TEXT, created_at TEXT);
        """)
        if con.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0:
            con.execute("INSERT INTO users(username,password) VALUES(?,?)",
                        ("demo", generate_password_hash("SmartFarm123!")))
            uid = con.execute("SELECT id FROM users WHERE username='demo'").fetchone()[0]
            cur = con.execute("INSERT INTO farms(user_id,name,country,city) VALUES(?,?,?,?)",
                              (uid, "Demo Farm", "Egypt", "Tanta"))
            farm_id = cur.lastrowid
            for r in range(16):
                for c in range(16):
                    code = f"{chr(65+r)}{c+1}"
                    con.execute("INSERT INTO zones(farm_id,zone_code) VALUES(?,?)", (farm_id, code))
init_db()

def login_required(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"): return redirect(url_for("login"))
        return fn(*args, **kwargs)
    return wrapped

@app.route("/")
def home():
    if not session.get("user_id"): return redirect(url_for("login"))
    with db() as con:
        farm = con.execute("SELECT * FROM farms WHERE user_id=? ORDER BY id LIMIT 1",(session["user_id"],)).fetchone()
        zones = con.execute("SELECT * FROM zones WHERE farm_id=? ORDER BY id",(farm["id"],)).fetchall()
        recent = con.execute("SELECT * FROM readings WHERE farm_id=? ORDER BY id DESC LIMIT 8",(farm["id"],)).fetchall()
        requests_ = con.execute("SELECT * FROM pump_requests WHERE farm_id=? ORDER BY id DESC LIMIT 6",(farm["id"],)).fetchall()
    return render_template("index.html", farm=farm, zones=zones, recent=recent, requests=requests_)

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        with db() as con:
            u = con.execute("SELECT * FROM users WHERE username=?",(request.form.get("username",""),)).fetchone()
        if u and check_password_hash(u["password"], request.form.get("password","")):
            session["user_id"] = u["id"]; session["username"] = u["username"]
            return redirect(url_for("home"))
        flash("Invalid username or password.")
    return render_template("login.html")

@app.route("/register", methods=["GET","POST"])
def register():
    if request.method == "POST":
        username, password = request.form.get("username","").strip(), request.form.get("password","")
        if len(username)<3 or len(password)<8:
            flash("Username must be 3+ characters and password 8+ characters.")
        else:
            try:
                with db() as con:
                    cur = con.execute("INSERT INTO users(username,password) VALUES(?,?)",
                                      (username, generate_password_hash(password)))
                    uid = cur.lastrowid
                    fid = con.execute("INSERT INTO farms(user_id,name,country,city) VALUES(?,?,?,?)",
                                      (uid, request.form.get("farm","My Farm"), request.form.get("country",""), request.form.get("city",""))).lastrowid
                    for r in range(16):
                        for c in range(16):
                            con.execute("INSERT INTO zones(farm_id,zone_code) VALUES(?,?)",(fid,f"{chr(65+r)}{c+1}"))
                session["user_id"]=uid; session["username"]=username
                return redirect(url_for("home"))
            except sqlite3.IntegrityError:
                flash("That username is already taken.")
    return render_template("register.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/api/health")
def health():
    return jsonify(status="ok", app="Smart Farm", timestamp=datetime.now(timezone.utc).isoformat())

@app.route("/api/device/readings", methods=["POST"])
def device_readings():
    if request.headers.get("X-Device-Token") != DEVICE_TOKEN:
        return jsonify(error="Unauthorized device"), 401
    data = request.get_json(silent=True) or {}
    required = ["farm_id","zone_code","moisture","ec"]
    if any(k not in data for k in required):
        return jsonify(error="Required: farm_id, zone_code, moisture, ec"), 400
    try:
        moisture, ec = float(data["moisture"]), float(data["ec"])
        temp = float(data["soil_temp"]) if data.get("soil_temp") is not None else None
    except (TypeError, ValueError):
        return jsonify(error="Sensor values must be numeric"), 400
    stamp = datetime.now(timezone.utc).isoformat()
    with db() as con:
        zone = con.execute("SELECT id FROM zones WHERE farm_id=? AND zone_code=?",
                           (int(data["farm_id"]), str(data["zone_code"]).upper())).fetchone()
        if not zone: return jsonify(error="Unknown farm zone"), 404
        con.execute("""INSERT INTO readings(farm_id,zone_code,moisture,ec,soil_temp,created_at,source)
                       VALUES(?,?,?,?,?,?,?)""",
                    (data["farm_id"],data["zone_code"].upper(),moisture,ec,temp,stamp,"ESP32"))
        con.execute("""UPDATE zones SET moisture=?,ec=?,soil_temp=?,updated_at=?,source='ESP32'
                       WHERE farm_id=? AND zone_code=?""",
                    (moisture,ec,temp,stamp,data["farm_id"],data["zone_code"].upper()))
    return jsonify(ok=True, saved_at=stamp)

@app.route("/api/pumps/request", methods=["POST"])
@login_required
def pump_request():
    data=request.get_json(silent=True) or {}
    pump=data.get("pump_type")
    if pump not in ("water","fertilizer"):
        return jsonify(error="pump_type must be water or fertilizer"),400
    try: amount=float(data.get("amount"))
    except (TypeError,ValueError): return jsonify(error="amount must be numeric"),400
    if amount<=0: return jsonify(error="amount must be positive"),400
    with db() as con:
        farm=con.execute("SELECT id FROM farms WHERE user_id=? LIMIT 1",(session["user_id"],)).fetchone()
        zone=data.get("zone_code","A1").upper()
        exists=con.execute("SELECT id FROM zones WHERE farm_id=? AND zone_code=?",(farm["id"],zone)).fetchone()
        if not exists: return jsonify(error="Unknown zone"),404
        cur=con.execute("""INSERT INTO pump_requests(farm_id,zone_code,pump_type,requested_amount,unit,status,created_at)
                           VALUES(?,?,?,?,?,'awaiting_review',?)""",
                        (farm["id"],zone,pump,amount,data.get("unit","L"),datetime.now(timezone.utc).isoformat()))
        rid=cur.lastrowid
    return jsonify(ok=True,request_id=rid,status="awaiting_review",
                   note="This is a planning record only; it does not activate hardware.")

@app.route("/api/upload-csv", methods=["POST"])
@login_required
def upload_csv():
    f=request.files.get("file")
    if not f: return jsonify(error="Choose a CSV file"),400
    try:
        rows=list(csv.DictReader(io.StringIO(f.stream.read().decode("utf-8-sig"))))
        count=0
        with db() as con:
            farm=con.execute("SELECT id FROM farms WHERE user_id=? LIMIT 1",(session["user_id"],)).fetchone()
            for row in rows:
                zone=row.get("zone_code","").upper()
                if not con.execute("SELECT id FROM zones WHERE farm_id=? AND zone_code=?",(farm["id"],zone)).fetchone(): continue
                moisture=float(row["moisture"]); ec=float(row["ec"])
                temp=float(row["soil_temp"]) if row.get("soil_temp") else None
                stamp=datetime.now(timezone.utc).isoformat()
                con.execute("INSERT INTO readings(farm_id,zone_code,moisture,ec,soil_temp,created_at,source) VALUES(?,?,?,?,?,?,?)",
                            (farm["id"],zone,moisture,ec,temp,stamp,"CSV"))
                con.execute("UPDATE zones SET moisture=?,ec=?,soil_temp=?,updated_at=?,source='CSV' WHERE farm_id=? AND zone_code=?",
                            (moisture,ec,temp,stamp,farm["id"],zone))
                count+=1
        return jsonify(ok=True, imported=count)
    except Exception as e:
        return jsonify(error="CSV must include zone_code, moisture, ec; optional soil_temp."),400

@app.route("/api/zones")
@login_required
def api_zones():
    with db() as con:
        farm=con.execute("SELECT id FROM farms WHERE user_id=? LIMIT 1",(session["user_id"],)).fetchone()
        rows=con.execute("SELECT * FROM zones WHERE farm_id=? ORDER BY zone_code",(farm["id"],)).fetchall()
    return jsonify([dict(r) for r in rows])

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT",5000)), debug=False)
