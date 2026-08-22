# Marioflix - film-app med eget kodlås och auto-uppdatering. (v5)
# Koderna ligger pa Render-servern (marioflix-codes.onrender.com) + koder.txt som backup.
# Uppdateringar hämtas från GitHub: mariomardoo-dev/Marioflix
import base64
import json
import os
import subprocess
import sys
import threading
import urllib.parse
import urllib.request

import webview

URL = "https://cinejoy.to/"
BASE = os.path.dirname(os.path.abspath(__file__))
ICON = os.path.join(BASE, "marioflix.ico")
CODES_FILE = os.path.join(BASE, "koder.txt")
CODES_SERVER = "https://marioflix-codes.onrender.com/check?code="

VERSION = 5
# GitHub API = alltid farskt (ingen cache). Publikt repo funkar utan nyckel.
UPDATE_URL = "https://api.github.com/repos/mariomardoo-dev/Marioflix/contents/"

CLEANUP_JS = r"""
(function () {
  function clean() {
    // 1. Gom Cinejoy logotypbilder (logomark + wordmark)
    document.querySelectorAll('img[src*="/brand/"], img[src*="cinejoy"]').forEach(function (img) {
      img.style.display = 'none';
    });

    // 2. Gom lankar som pekar pa cinejoy.to (t.ex. kontaktlanken)
    document.querySelectorAll('a[href*="cinejoy"]').forEach(function (a) {
      a.style.display = 'none';
    });

    // 2.5 Byt namn pa undertext-fonten "Cinejoy" till "Mario special"
    document.querySelectorAll('button.segment-btn, button[class*="segment"]').forEach(function (el) {
      if ((el.textContent || '').trim() === 'Cinejoy') {
        el.textContent = 'Mario special';
      }
    });

    // 3. Gom text-bara element som innehaller "cinejoy" (fottext, vattenmarkeringar osv.)
    document.querySelectorAll('p, span, div, a, h1, h2, h3, li').forEach(function (el) {
      if (el.children.length === 0 && /cinejoy/i.test(el.textContent || '')) {
        el.style.display = 'none';
      }
    });

    // 4. Byt ut loggan i toppmenyn mot "Marioflix"
    document.querySelectorAll('a').forEach(function (a) {
      if (a.querySelector('img[src*="/brand/"]')) {
        a.querySelectorAll('img').forEach(function (img) { img.style.display = 'none'; });
        if (!a.querySelector('.mf-brand')) {
          var span = document.createElement('span');
          span.className = 'mf-brand';
          span.textContent = 'Marioflix';
          span.style.cssText = 'font-size:22px;font-weight:700;color:#ffffff;letter-spacing:0.5px;white-space:nowrap;';
          a.appendChild(span);
        }
      }
    });

    // 5. Andra flik-/fonster-titeln
    if (/cinejoy/i.test(document.title)) {
      document.title = 'Marioflix';
    }

    // 6. Ta bort Discord-lankar
    document.querySelectorAll('a[href*="discord"], a[href*="discord.gg"]').forEach(function (a) {
      a.style.display = 'none';
    });

    // 7. Ta bort Cinejoys eget login (Log in / Sign In / Sign out / Login) var den an finns
    document.querySelectorAll('button, a').forEach(function (el) {
      var t = (el.textContent || '').trim();
      if (/^(log\s*in|sign\s*in|sign\s*out|sign\s*up|login|create\s+account)$/i.test(t)) {
        el.style.display = 'none';
      }
    });

    // 8. Ta bort "Manage" (konto) ur kugghjulsmenyerna - men BEHALL "Settings"!
    //    (Settings leder till inställningssidan med undertexter osv.)
    document.querySelectorAll('button, a').forEach(function (el) {
      var t = (el.textContent || '').trim();
      if (t === 'Manage') {
        var inMenu = el.closest('div.profile-portal-menu, div.mobile-profile-menu');
        var menuLike = /px-4 py-2\.5|px-4 py-3/.test(el.className);
        if (inMenu || menuLike) {
          el.style.display = 'none';
        }
      }
    });

    // 9. Ta bort "Not signed in" / "Create an account..."-texterna
    document.querySelectorAll('p, span, div, h1, h2, h3, li').forEach(function (el) {
      var t = (el.textContent || '').trim();
      if (el.children.length === 0 && /not signed in|create an account|sync your data/i.test(t)) {
        el.style.display = 'none';
      }
    });
  }

  clean();

  // Hall koll pa nytt innehall (spelaren, nya filmer osv.) - men inte for ofta
  var scheduled = false;
  function schedule() {
    if (scheduled) return;
    scheduled = true;
    setTimeout(function () { scheduled = false; clean(); }, 200);
  }
  new MutationObserver(schedule).observe(document.documentElement, { childList: true, subtree: true });
})();
"""

LOGIN_HTML = """<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>Marioflix</title>
<style>
  body { margin:0; font-family:'Segoe UI',Arial,sans-serif; background:#121218; color:#fff;
         display:flex; align-items:center; justify-content:center; height:100vh; }
  .box { text-align:center; }
  h1 { font-size:34px; margin:0 0 6px; letter-spacing:.5px; }
  .play { color:#e52020; }
  p.sub { color:#888; margin:0 0 26px; font-size:14px; }
  input { background:#1e1e28; border:1px solid #333; color:#fff; font-size:18px; padding:12px 16px;
          border-radius:10px; width:240px; text-align:center; outline:none; box-sizing:border-box; }
  input:focus { border-color:#e52020; }
  button { margin-top:14px; background:#e52020; color:#fff; border:0; font-size:16px; font-weight:600;
           padding:12px 32px; border-radius:999px; cursor:pointer; }
  button:hover { background:#ff2b2b; }
  .err { color:#ff6b6b; font-size:13px; min-height:18px; margin-top:12px; }
  .upd { color:#888; font-size:12px; min-height:16px; margin-top:8px; }
</style>
</head>
<body>
  <div class="box">
    <h1><span class="play">Mario</span>flix</h1>
    <p class="sub">Ange din kod för att komma in</p>
    <input id="code" type="password" placeholder="Kod" autofocus>
    <br>
    <button id="btn">Logga in</button>
    <div class="err" id="err"></div>
    <div class="upd" id="upd"></div>
  </div>
  <script>
    function tryLogin() {
      var code = document.getElementById('code').value.trim();
      if (!code) return;
      document.getElementById('err').textContent = 'Kollar...';
      pywebview.api.check_code(code).then(function (ok) {
        if (ok) {
          document.getElementById('err').style.color = '#6bff8b';
          document.getElementById('err').textContent = 'Rätt kod! Öppnar filmerna...';
        } else {
          document.getElementById('err').style.color = '#ff6b6b';
          document.getElementById('err').textContent = 'Fel kod, försök igen.';
        }
      });
    }
    document.getElementById('btn').addEventListener('click', tryLogin);
    document.getElementById('code').addEventListener('keydown', function (e) {
      if (e.key === 'Enter') tryLogin();
    });
  </script>
</body>
</html>
"""


def load_codes():
    """Las alla koder fran koder.txt (en per rad, rader med # ignorerade)."""
    if not os.path.exists(CODES_FILE):
        with open(CODES_FILE, "w", encoding="utf-8") as f:
            f.write("# Marioflix-koder - en kod per rad. Andra hur du vill!\n")
            f.write("# Rad som borjar med # raknas inte som kod.\n")
            f.write("MARI0123\n")
    with open(CODES_FILE, "r", encoding="utf-8") as f:
        return {line.strip().lower() for line in f if line.strip() and not line.strip().startswith("#")}


class Api:
    def __init__(self):
        self.logged_in = False
        self.current_code = None

    def check_code(self, code):
        c = code.strip().lower()
        # 1) Server-koderna (Render) - anda koderna galls overallt
        try:
            with urllib.request.urlopen(CODES_SERVER + urllib.parse.quote(c), timeout=60) as r:
                ok = bool(json.loads(r.read().decode()).get("ok", False))
            if ok:
                self.logged_in = True
                self.current_code = code.strip()
            return ok
        except Exception:
            pass
        # 2) Fallback: lokal koder.txt om servern inte svarar
        ok = c in load_codes()
        if ok:
            self.logged_in = True
            self.current_code = code.strip()
        return ok

    def logout(self):
        self.logged_in = False
        self.current_code = None
        return True


def signout_menu_js(code):
    """Lagger en 'Sign out'-knapp i kugghjulsmenyn (desktop- eller mobilmenyn)."""
    import json

    safe = json.dumps(code)
    return """(function () {
  var CODE = %s;
  function addItem() {
    var menu = document.querySelector('div.profile-portal-menu') || document.querySelector('div.mobile-profile-menu');
    if (!menu || menu.querySelector('#mf-signout-item')) return;
    var btn = document.createElement('button');
    btn.id = 'mf-signout-item';
    btn.type = 'button';
    btn.textContent = 'Sign out \\u00b7 ' + CODE;
    btn.className = 'flex items-center gap-3 px-4 py-2.5 text-sm text-white/90 hover:bg-white/10 transition-colors text-left w-full';
    btn.style.cssText = 'color:#ff6b6b;background:none;border:0;font:inherit;text-align:left;cursor:pointer;';
    btn.addEventListener('click', function () { pywebview.api.logout(); });
    menu.appendChild(btn);
  }
  addItem();
  var scheduled = false;
  function schedule() {
    if (scheduled) return;
    scheduled = true;
    setTimeout(function () { scheduled = false; addItem(); }, 250);
  }
  new MutationObserver(schedule).observe(document.documentElement, { childList: true, subtree: true });
})();""" % safe


def on_loaded(api):
    try:
        w = webview.windows[0]
        # Injicera stadaren bara nar filmsidan laddas (inte pa inloggningssidan)
        cur = w.get_current_url() or ""
        if cur.startswith("https://cinejoy.to"):
            w.evaluate_js(CLEANUP_JS)
            if api.logged_in:
                w.evaluate_js(signout_menu_js(api.current_code or "MARIO123"))
    except Exception as e:
        print("JS injection failed:", e)


def fetch_gh(filename):
    """Hamta en fil fran GitHub-repot via API (ingen cache). Returnerar text."""
    url = UPDATE_URL + filename
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Marioflix", "Accept": "application/vnd.github+json"},
    )
    with urllib.request.urlopen(req, timeout=15) as r:
        data = json.loads(r.read().decode("utf-8"))
    return base64.b64decode(data["content"]).decode("utf-8")


def run_updater(window):
    """Kollar efter uppdateringar pa GitHub. Finns ny version -> ladda ner, byt fil, starta om."""
    def set_status(txt, color="#888"):
        try:
            window.evaluate_js(
                "var e = document.getElementById('upd'); if (e) { e.textContent = %s; e.style.color = %s; }"
                % (json.dumps(txt), json.dumps(color))
            )
        except Exception:
            pass

    try:
        remote = int(fetch_gh("version.txt").strip())
    except Exception:
        set_status("")
        return

    if remote <= VERSION:
        set_status("")
        return

    set_status("Ny version finns! Uppdaterar...", "#ffb347")
    try:
        new_code = fetch_gh("marioflix.py")
        compile(new_code, "marioflix_new.py", "exec")  # validera att det ar riktig python
        script = os.path.join(BASE, "marioflix.py")
        new_path = os.path.join(BASE, "marioflix_new.py")
        with open(new_path, "w", encoding="utf-8") as f:
            f.write(new_code)
        os.replace(new_path, script)
        set_status("Uppdaterad! Startar om...", "#6bff8b")
        subprocess.Popen([sys.executable, script])
        os._exit(0)
    except Exception:
        set_status("Uppdateringen misslyckades - startar andå", "#ff6b6b")


def watch_login(window, api):
    """Vaktar inloggningen: ratt kod -> filmsidan, sign out -> tillbaka till kodrutan."""
    import time

    was_in = False
    while True:
        if api.logged_in and not was_in:
            was_in = True
            window.load_url(URL)
        elif not api.logged_in and was_in:
            was_in = False
            window.load_html(LOGIN_HTML)
        time.sleep(0.3)


if __name__ == "__main__":
    webview.settings["ALLOW_DOWNLOADS"] = True
    api = Api()
    window = webview.create_window(
        "Marioflix",
        html=LOGIN_HTML,
        width=1366,
        height=900,
        min_size=(1000, 700),
        background_color="#121218",
        js_api=api,
    )
    window.events.loaded += lambda: on_loaded(api)
    threading.Thread(target=watch_login, args=(window, api), daemon=True).start()
    threading.Thread(target=run_updater, args=(window,), daemon=True).start()
    webview.start(icon=ICON, private_mode=False)
