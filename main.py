import requests
import time
import random
import string
import warnings
import threading
import webbrowser
import re
from datetime import datetime, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import unquote

warnings.filterwarnings("ignore")

API_BASE = "https://api.venumzmail.xyz"
API_KEY = "vz-49b3c659-0cba-461d-ac5f-b5951c3ae388"
DOMAIN = "analgex.com"
PORT = 9999
EMAIL_TTL = 300

emails_store = {}
current_email = None
seen_ids = set()
email_created_at = None


def gen_email():
    username = ''.join(random.choices(string.ascii_lowercase + string.digits, k=random.randint(10, 16)))
    payload = {"count": 1, "username": username, "domain": DOMAIN, "type": "public"}
    s = requests.Session()
    s.verify = False
    s.headers.update({"Content-Type": "application/json", "x-api-key": API_KEY})
    resp = s.post(f"{API_BASE}/create", json=payload, timeout=30)
    if resp.status_code in [200, 201]:
        data = resp.json()
        if data.get("inboxes"):
            return data["inboxes"][0].get("email")
    return f"{username}@{DOMAIN}"


def check_inbox(email):
    s = requests.Session()
    s.verify = False
    s.headers.update({"x-api-key": API_KEY})
    resp = s.get(f"{API_BASE}/inbox/{email}", timeout=30)
    if resp.status_code == 200:
        return resp.json().get("messages", [])
    return []


def is_expired():
    return email_created_at and (time.time() - email_created_at) > EMAIL_TTL


def fmt_date(raw):
    if not raw:
        return ""
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        local = dt.astimezone()
        tz = local.strftime("%z")
        hours = int(tz[:3])
        offset = f"UTC{hours:+d}"
        return local.strftime(f"%m/%d/%Y %I:%M %p {offset}")
    except Exception:
        return raw


MATRIX_JS = """
<script>
var c = document.getElementById('matrix');
if(c){
var ctx = c.getContext('2d');
c.width = window.innerWidth;
c.height = window.innerHeight;
var chars = '01アイウエオカキクケコ{}[]<>/\\\\|=+-*&^%$#@!';
var word = 'CANNABIS';
var fontSize = 14;
var cols = Math.floor(c.width / fontSize);
var drops = [];
var wordCols = [];
var wordAngles = [];
for(var i=0;i<cols;i++) drops[i]=Math.random()*-100;
function pickWordCols(){
  wordCols=[];
  wordAngles=[];
  var count=Math.floor(cols/2.5)+4;
  for(var i=0;i<count;i++){
    var col=Math.floor(Math.random()*cols);
    if(wordCols.indexOf(col)===-1){
      wordCols.push(col);
      wordAngles.push((Math.random()-0.5)*30);
    }
  }
}
pickWordCols();
setInterval(function(){if(Math.random()>0.9)pickWordCols();},2000);
function draw(){
  ctx.fillStyle='rgba(10,10,10,0.08)';
  ctx.fillRect(0,0,c.width,c.height);
  ctx.font=fontSize+'px Consolas';
  for(var i=0;i<cols;i++){
    var pos=wordCols.indexOf(i);
    var isWord=pos!==-1;
    var ch;
    if(isWord){
      var letterIdx=Math.floor(drops[i]*0.5)%word.length;
      ch=word[letterIdx];
      var angle=(Math.sin(drops[i]*0.3+i)*18)*Math.PI/180;
      ctx.save();
      ctx.translate(i*fontSize+fontSize/2,drops[i]*fontSize);
      ctx.rotate(angle);
      ctx.fillStyle='#00ff9d';
      ctx.fillText(ch,-fontSize/2,0);
      ctx.restore();
    }else{
      ch=chars[Math.floor(Math.random()*chars.length)];
      ctx.fillStyle='#00ff9d33';
      ctx.fillText(ch,i*fontSize,drops[i]*fontSize);
    }
    if(drops[i]*fontSize>c.height&&Math.random()>0.975){drops[i]=0;if(isWord)pickWordCols();}
    drops[i]++;
  }
}
setInterval(draw,80);
window.addEventListener('resize',function(){c.width=window.innerWidth;c.height=window.innerHeight;cols=Math.floor(c.width/fontSize);drops=[];for(var i=0;i<cols;i++)drops[i]=Math.random()*-100;pickWordCols();});
}
</script>"""


def strip_email_tags(html):
    html = re.sub(r'<!DOCTYPE[^>]*>', '', html, flags=re.IGNORECASE)
    html = re.sub(r'</?html[^>]*>', '', html, flags=re.IGNORECASE)
    html = re.sub(r'<head[\s\S]*?</head>', '', html, flags=re.IGNORECASE)
    html = re.sub(r'<style[\s\S]*?</style>', '', html, flags=re.IGNORECASE)
    html = re.sub(r'<body[^>]*>', '', html, flags=re.IGNORECASE)
    html = re.sub(r'</body>', '', html, flags=re.IGNORECASE)
    html = re.sub(r'\s+style="[^"]*background[^"]*"', '', html, flags=re.IGNORECASE)
    html = re.sub(r"\s+style='[^']*background[^']*'", '', html, flags=re.IGNORECASE)
    return html.strip()


def build_expired_page():
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta http-equiv="refresh" content="30">
<title>tempmail</title>
<style>
  * {{ margin:0; padding:0; box-sizing:border-box }}
  body {{ background:#0a0a0a; color:#c0c0c0; font-family:Consolas,monospace; min-height:100vh; display:flex; align-items:center; justify-content:center }}
  .grid-bg {{ position:fixed; inset:0; background-image:linear-gradient(rgba(0,255,157,0.03) 1px,transparent 1px),linear-gradient(90deg,rgba(0,255,157,0.03) 1px,transparent 1px); background-size:40px 40px; pointer-events:none }}
  .scanline {{ position:fixed; inset:0; background:repeating-linear-gradient(0deg,transparent,transparent 2px,rgba(0,0,0,0.15) 2px,rgba(0,0,0,0.15) 4px); pointer-events:none }}
  .content {{ position:relative; z-index:2; max-width:500px; width:100%; margin:0 auto; padding:60px 30px; text-align:center }}
  .expired {{ background:#0d0d0d; border:1px solid #1a1a1a; padding:40px; position:relative; overflow:hidden }}
  .expired::before {{ content:''; position:absolute; top:0; left:0; width:3px; height:100%; background:#ff3333 }}
  .expired h2 {{ color:#ff3333; font-size:18px; font-weight:normal; margin-bottom:12px; letter-spacing:2px }}
  .expired p {{ color:#666; font-size:12px; line-height:1.8 }}
  .btn {{ display:inline-block; margin-top:20px; background:#0d0d0d; border:1px solid #00ff9d; color:#00ff9d; padding:10px 24px; font-family:Consolas,monospace; font-size:12px; cursor:pointer; text-decoration:none; transition:all 0.3s }}
  .btn:hover {{ background:#00ff9d11 }}
  .footer {{ margin-top:40px; padding-top:20px; border-top:1px solid #1a1a1a; color:#333; font-size:10px; text-align:center }}
</style>
</head>
<body>
  <div class="grid-bg"></div>
  <div class="scanline"></div>
  <div class="content">
    <div class="expired">
      <h2>inbox expired</h2>
      <p>this email address is no longer valid.<br>the inbox expired after 5 minutes.</p>
      <a href="/new" class="btn">generate new inbox</a>
    </div>
    <div class="footer">powered by cannabis intelligence</div>
  </div>
  <canvas id="matrix" style="position:fixed;inset:0;z-index:0;opacity:0.12;pointer-events:none;"></canvas>
  {MATRIX_JS}
</body>
</html>"""


def build_index_page():
    remaining = max(0, EMAIL_TTL - int(time.time() - email_created_at)) if email_created_at else 0
    mins = remaining // 60
    secs = remaining % 60
    cards = ""
    for mid, msg in reversed(list(emails_store.items())):
        sender = msg.get("sender", "?")
        subject = msg.get("subject", "(no subject)")
        date = fmt_date(msg.get("received_at", ""))
        cards += f"""
        <a href="/email/{mid}" class="email-card">
            <div class="email-sender">{sender}</div>
            <div class="email-subject">{subject}</div>
            <div class="email-meta">{date}</div>
        </a>"""
    if not cards:
        cards = '<div class="empty">waiting for mail...</div>'
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta http-equiv="refresh" content="5">
<title>tempmail</title>
<style>
  * {{ margin:0; padding:0; box-sizing:border-box }}
  body {{ background:#0a0a0a; color:#c0c0c0; font-family:Consolas,monospace; min-height:100vh; display:flex; align-items:center; justify-content:center }}
  .grid-bg {{ position:fixed; inset:0; background-image:linear-gradient(rgba(0,255,157,0.03) 1px,transparent 1px),linear-gradient(90deg,rgba(0,255,157,0.03) 1px,transparent 1px); background-size:40px 40px; pointer-events:none }}
  .scanline {{ position:fixed; inset:0; background:repeating-linear-gradient(0deg,transparent,transparent 2px,rgba(0,0,0,0.15) 2px,rgba(0,0,0,0.15) 4px); pointer-events:none }}
  .content {{ position:relative; z-index:2; max-width:700px; width:100%; margin:0 auto; padding:60px 30px }}
  .header {{ margin-bottom:40px; border-left:3px solid #00ff9d; padding-left:20px }}
  .header h1 {{ font-size:28px; color:#00ff9d; font-weight:normal; letter-spacing:4px }}
  .header .sub {{ color:#444; font-size:11px; margin-top:8px; letter-spacing:1px }}
  .terminal {{ background:#0d0d0d; border:1px solid #1a1a1a; padding:20px; margin-bottom:20px }}
  .terminal-header {{ color:#333; font-size:10px; margin-bottom:15px; padding-bottom:10px; border-bottom:1px solid #1a1a1a }}
  .terminal-line {{ margin-bottom:6px; font-size:13px; line-height:1.6 }}
  .terminal-line .prompt {{ color:#00ff9d }}
  .terminal-line .cmd {{ color:#e0ffe0 }}
  .email-copy {{ display:flex; gap:8px; margin-bottom:16px }}
  .email-addr {{ flex:1; background:#0d0d0d; border:1px solid #1a1a1a; color:#e0ffe0; padding:10px 14px; font-family:Consolas,monospace; font-size:13px; outline:none; user-select:all }}
  .btn {{ background:#0d0d0d; border:1px solid #00ff9d; color:#00ff9d; padding:10px 16px; font-family:Consolas,monospace; font-size:11px; cursor:pointer; transition:all 0.3s }}
  .btn:hover {{ background:#00ff9d11 }}
  .timer {{ background:#0d0d0d; border:1px solid #1a1a1a; padding:10px 16px; margin-bottom:20px; font-size:11px; color:#444; display:flex; justify-content:space-between; align-items:center }}
  .timer .time {{ color:#00ff9d; font-size:16px }}
  .timer.warn .time {{ color:#ff3333 }}
  .email-card {{ display:block; background:#0d0d0d; border:1px solid #1a1a1a; padding:24px; margin-bottom:12px; text-decoration:none; transition:all 0.3s; position:relative; overflow:hidden }}
  .email-card::before {{ content:''; position:absolute; top:0; left:0; width:3px; height:100%; background:#00ff9d; transform:scaleY(0); transition:transform 0.3s }}
  .email-card:hover {{ border-color:#00ff9d }}
  .email-card:hover::before {{ transform:scaleY(1) }}
  .email-sender {{ color:#00ff9d; font-size:14px; margin-bottom:6px }}
  .email-subject {{ color:#888; font-size:12px; margin-bottom:8px }}
  .email-meta {{ color:#444; font-size:10px }}
  .empty {{ color:#333; font-size:12px; text-align:center; padding:20px }}
  .footer {{ margin-top:40px; padding-top:20px; border-top:1px solid #1a1a1a; color:#333; font-size:10px; text-align:center }}
</style>
</head>
<body>
  <div class="grid-bg"></div>
  <div class="scanline"></div>
  <div class="content">
    <div class="header">
      <h1>tempmail</h1>
      <div class="sub">disposable inbox</div>
    </div>

    <div class="timer" id="timer">
      <span>expires in</span>
      <span class="time" id="countdown">{mins:02d}:{secs:02d}</span>
    </div>

    <div class="terminal">
      <div class="terminal-header">terminal ~ /tmp/mail</div>
      <div class="terminal-line"><span class="prompt">$</span><span class="cmd"> cat inbox.json</span></div>
      <div class="email-copy">
        <input class="email-addr" id="email-addr" value="{current_email}" readonly>
        <button class="btn" onclick="navigator.clipboard.writeText(document.getElementById('email-addr').value);this.textContent='copied!'">copy</button>
        <button class="btn" onclick="window.location='/new'">new</button>
      </div>
      <div class="terminal-line"><span class="prompt">$</span><span class="cmd"> ls ./messages</span></div>
    </div>

    {cards}

    <div class="footer">powered by cannabis intelligence</div>
  </div>
  <canvas id="matrix" style="position:fixed;inset:0;z-index:0;opacity:0.12;pointer-events:none;"></canvas>
  {MATRIX_JS}
  <script>
  var total={remaining};
  function tick(){{
    if(total<=0){{window.location.reload();return}}
    total--;
    var m=Math.floor(total/60);
    var s=total%60;
    var el=document.getElementById('countdown');
    var wrap=document.getElementById('timer');
    el.textContent=(m<10?'0':'')+m+':'+(s<10?'0':'')+s;
    if(total<=60)wrap.className='timer warn';
    setTimeout(tick,1000);
  }}
  tick();
  </script>
</body>
</html>"""


def build_email_page(msg):
    body_html = msg.get("body_html", "")
    body_text = msg.get("body", "")
    sender = msg.get("sender", "?")
    subject = msg.get("subject", "(no subject)")
    date = fmt_date(msg.get("received_at", ""))
    raw_content = body_html if body_html.strip() else f"<pre style='white-space:pre-wrap;font-family:inherit'>{body_text}</pre>"
    raw_content = strip_email_tags(raw_content)
    inject = """<style>
.body-inner html,.body-inner body,.body-inner table,.body-inner td,.body-inner div,.body-inner p,.body-inner a,.body-inner h1,.body-inner h2,.body-inner h3,.body-inner h4,.body-inner h5,.body-inner h6,.body-inner span,.body-inner pre,.body-inner code,.body-inner section,.body-inner header,.body-inner footer,.body-inner main,.body-inner article,.body-inner aside{background-color:#0d0d0d!important;color:#c0c0c0!important}
.body-inner body{font-family:Consolas,monospace!important}
.body-inner a{color:#00ff9d!important}
.body-inner img{max-width:100%;height:auto;filter:brightness(.8)contrast(1.1)}
.body-inner th{background:#1a1a1a!important;color:#00ff9d!important}
.body-inner td{border-color:#1a1a1a!important}
.body-inner pre,.body-inner code{background:#1a1a1a!important;color:#e0ffe0!important}
</style>"""
    content = inject + raw_content
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{subject}</title>
<style>
  * {{ margin:0; padding:0; box-sizing:border-box }}
  body {{ background:#0a0a0a; color:#c0c0c0; font-family:Consolas,monospace; min-height:100vh; display:flex; align-items:center; justify-content:center }}
  .grid-bg {{ position:fixed; inset:0; background-image:linear-gradient(rgba(0,255,157,0.03) 1px,transparent 1px),linear-gradient(90deg,rgba(0,255,157,0.03) 1px,transparent 1px); background-size:40px 40px; pointer-events:none }}
  .scanline {{ position:fixed; inset:0; background:repeating-linear-gradient(0deg,transparent,transparent 2px,rgba(0,0,0,0.15) 2px,rgba(0,0,0,0.15) 4px); pointer-events:none }}
  .content {{ position:relative; z-index:2; max-width:900px; margin:0 auto; padding:40px 30px }}
  .nav {{ margin-bottom:24px }}
  .nav a {{ color:#00ff9d; text-decoration:none; font-size:12px; border:1px solid #1a1a1a; padding:6px 14px; background:#0d0d0d; transition:all 0.3s }}
  .nav a:hover {{ border-color:#00ff9d }}
  .terminal {{ background:#0d0d0d; border:1px solid #1a1a1a; padding:20px; margin-bottom:20px }}
  .terminal-header {{ color:#333; font-size:10px; margin-bottom:15px; padding-bottom:10px; border-bottom:1px solid #1a1a1a }}
  .terminal-line {{ margin-bottom:6px; font-size:13px; line-height:1.6 }}
  .terminal-line .prompt {{ color:#00ff9d }}
  .terminal-line .val {{ color:#c0c0c0 }}
  .body-wrap {{ border:1px solid #1a1a1a; overflow:hidden; position:relative }}
  .body-wrap::before {{ content:''; position:absolute; top:0; left:0; width:3px; height:100%; background:#00ff9d; z-index:1 }}
  .body-inner {{ padding:24px 24px 24px 28px; background:#0d0d0d; color:#c0c0c0 }}
  .footer {{ margin-top:40px; padding-top:20px; border-top:1px solid #1a1a1a; color:#333; font-size:10px; text-align:center }}
</style>
</head>
<body>
  <div class="grid-bg"></div>
  <div class="scanline"></div>
  <div class="content">
    <div class="nav">
      <a href="/">&larr; inbox</a>
    </div>

    <div class="terminal">
      <div class="terminal-header">terminal ~ /tmp/mail</div>
      <div class="terminal-line"><span class="prompt">$</span><span class="cmd"> cat message.json</span></div>
      <div class="terminal-line"><span class="prompt">from:</span> <span class="val">{sender}</span></div>
      <div class="terminal-line"><span class="prompt">subject:</span> <span class="val">{subject}</span></div>
      <div class="terminal-line"><span class="prompt">date:</span> <span class="val">{date}</span></div>
    </div>

    <div class="body-wrap">
      <div class="body-inner">{content}</div>
    </div>

    <div class="footer">powered by cannabis intelligence</div>
  </div>
  <canvas id="matrix" style="position:fixed;inset:0;z-index:0;opacity:0.12;pointer-events:none;"></canvas>
  {MATRIX_JS}
</body>
</html>"""


class MailHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def do_GET(self):
        global current_email, email_created_at
        path = unquote(self.path)
        if path == "/new":
            current_email = gen_email()
            email_created_at = time.time()
            emails_store.clear()
            seen_ids.clear()
            self.send_response(302)
            self.send_header("Location", "/")
            self.end_headers()
        elif path == "/" or path == "":
            if is_expired():
                self.respond(200, build_expired_page(), "text/html")
            else:
                self.respond(200, build_index_page(), "text/html")
        elif path.startswith("/email/"):
            if is_expired():
                self.respond(200, build_expired_page(), "text/html")
            else:
                mid = path.split("/email/", 1)[1]
                if mid in emails_store:
                    self.respond(200, build_email_page(emails_store[mid]), "text/html")
                else:
                    self.respond(404, "not found", "text/plain")
        else:
            self.respond(404, "not found", "text/plain")

    def respond(self, code, body, ctype):
        self.send_response(code)
        self.send_header("Content-Type", f"{ctype}; charset=utf-8")
        self.end_headers()
        self.wfile.write(body.encode("utf-8"))


def start_server():
    server = HTTPServer(("0.0.0.0", PORT), MailHandler)
    server.serve_forever()


current_email = gen_email()
email_created_at = time.time()

server_thread = threading.Thread(target=start_server, daemon=True)
server_thread.start()

print(f"server started on: 0.0.0.0:{PORT}")
print("powered by cannabis intelligence")

webbrowser.open(f"http://127.0.0.1:{PORT}")

try:
    while True:
        if not is_expired():
            msgs = check_inbox(current_email)
            for m in msgs:
                mid = m.get("id") or m.get("message_id") or m.get("subject", "") + m.get("sender", "")
                if mid not in seen_ids:
                    seen_ids.add(mid)
                    emails_store[str(len(emails_store))] = m
        time.sleep(5)
except KeyboardInterrupt:
    pass
