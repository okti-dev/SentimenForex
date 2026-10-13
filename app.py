"""
Sentimen Forex
==============
Aplikasi desktop Windows dengan dua tab:

1. "Widget Myfxbook"  - widget Community Outlook resmi Myfxbook (tanpa login),
   tata letaknya responsif mengikuti ukuran jendela.
2. "Urut Sentimen"    - tabel Community Trend (Shorts vs Longs) yang diurutkan dari
   persentase terbesar. Long dan Short diperlakukan sama: yang dipakai adalah sisi
   mana pun yang persentasenya lebih besar. Data dari API resmi Myfxbook
   (butuh akun Myfxbook gratis; password tidak pernah disimpan).

Widget Myfxbook ditampilkan di dalam iframe milik Myfxbook, sehingga isinya tidak
bisa diurutkan ulang oleh aplikasi. Karena itu pengurutan memakai tab kedua.
"""

import json
import os
import tempfile
import webbrowser
from datetime import datetime
from pathlib import Path

import requests

APP_TITLE = "Sentimen Forex"
APP_VERSION = "1.1.0"
API_BASE = "https://www.myfxbook.com/api"
WIDGET_REFRESH_MINUTES = 5
MIN_AUTO_MINUTES = 10  # batas bawah auto-refresh tab data (hemat kuota API)

CONFIG_DIR = os.path.join(os.path.expanduser("~"), ".sentimen_forex")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")


# --------------------------------------------------------------------------
# Konfigurasi: hanya email yang boleh disimpan, password tidak pernah ditulis
# --------------------------------------------------------------------------
def load_config():
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def save_config(data):
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f)
    except OSError:
        pass


# --------------------------------------------------------------------------
# API Myfxbook (dipanggil dari JavaScript lewat jembatan pywebview)
# Atribut berawalan "_" sengaja privat agar tidak diekspos ke JavaScript.
# --------------------------------------------------------------------------
class MyfxbookError(Exception):
    pass


def to_float(value):
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def to_int(value):
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def parse_symbols(payload):
    """Ubah respons get-community-outlook menjadi daftar baris untuk tampilan."""
    rows = []
    for s in payload.get("symbols", []):
        long_pct = to_float(s.get("longPercentage"))
        short_pct = to_float(s.get("shortPercentage"))
        if long_pct > short_pct:
            dominant = "long"
        elif short_pct > long_pct:
            dominant = "short"
        else:
            dominant = "even"
        rows.append(
            {
                "symbol": str(s.get("name", "?")),
                "long_pct": long_pct,
                "short_pct": short_pct,
                "top_pct": max(long_pct, short_pct),
                "dominant": dominant,
                "long_vol": to_float(s.get("longVolume")),
                "short_vol": to_float(s.get("shortVolume")),
                "long_pos": to_int(s.get("longPositions")),
                "short_pos": to_int(s.get("shortPositions")),
            }
        )
    return rows


class Api:
    def __init__(self):
        self._http = requests.Session()
        self._http.headers.update({"User-Agent": f"{APP_TITLE}/{APP_VERSION}"})
        self._session_id = None
        self._email = ""
        self._password = ""  # hanya di memori, dipakai bila sesi kedaluwarsa

    def _get(self, endpoint, params):
        try:
            resp = self._http.get(f"{API_BASE}/{endpoint}", params=params, timeout=20)
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as exc:
            raise MyfxbookError(f"Gagal terhubung ke Myfxbook: {exc}") from exc
        except ValueError as exc:
            raise MyfxbookError("Respons Myfxbook tidak valid.") from exc
        if data.get("error"):
            raise MyfxbookError(data.get("message") or "Myfxbook mengembalikan error.")
        return data

    def _login(self):
        data = self._get("login.json", {"email": self._email, "password": self._password})
        self._session_id = data.get("session")
        if not self._session_id:
            raise MyfxbookError("Login gagal: session tidak diterima.")

    # ---- metode publik yang dipanggil dari JavaScript ----
    def saved_email(self):
        return load_config().get("email", "")

    def login(self, email, password, remember):
        self._email = (email or "").strip()
        self._password = password or ""
        try:
            self._login()
        except MyfxbookError as exc:
            self._password = ""
            return {"ok": False, "error": str(exc)}
        save_config({"email": self._email} if remember else {})
        return {"ok": True}

    def outlook(self):
        try:
            try:
                data = self._get("get-community-outlook.json", {"session": self._session_id})
            except MyfxbookError:
                if not (self._email and self._password):
                    raise
                self._login()  # sesi mungkin kedaluwarsa
                data = self._get("get-community-outlook.json", {"session": self._session_id})
        except MyfxbookError as exc:
            return {"ok": False, "error": str(exc)}
        return {
            "ok": True,
            "rows": parse_symbols(data),
            "updated": datetime.now().strftime("%d-%m-%Y %H:%M:%S"),
        }

    def logout(self):
        if self._session_id:
            try:
                self._get("logout.json", {"session": self._session_id})
            except MyfxbookError:
                pass
        self._session_id = None
        self._password = ""


# --------------------------------------------------------------------------
# Halaman (HTML + CSS + JS) yang ditampilkan di jendela aplikasi
# --------------------------------------------------------------------------
PAGE_HTML = """<!doctype html>
<html lang="id">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Sentimen Forex</title>
<style>
  :root {
    --bg: #f4f6f8; --card: #ffffff; --ink: #1f2933; --muted: #6b7785;
    --head: #0f2a43; --line: #e3e8ee; --long: #2e9e5b; --short: #d64545; --accent: #1d6fb8;
  }
  * { box-sizing: border-box; }
  html, body { height: 100%; }
  body { margin: 0; font-family: "Segoe UI", Arial, sans-serif; background: var(--bg);
         color: var(--ink); display: flex; flex-direction: column; min-height: 100vh; }
  header { display: flex; flex-wrap: wrap; gap: 6px 16px; justify-content: space-between;
           align-items: center; padding: 12px clamp(12px, 3vw, 24px);
           background: var(--head); color: #fff; }
  header h1 { margin: 0; font-size: clamp(17px, 2.4vw, 22px); }
  #clock { font-size: 12px; opacity: .8; }
  nav { display: flex; gap: 4px; padding: 10px clamp(12px, 3vw, 24px) 0; flex-wrap: wrap; }
  .tab { border: 1px solid var(--line); border-bottom: none; background: #e9eef3; color: var(--ink);
         padding: 8px 16px; border-radius: 8px 8px 0 0; cursor: pointer; font: inherit; font-size: 14px; }
  .tab.active { background: var(--card); font-weight: 600; color: var(--accent); }
  main { flex: 1; width: 100%; max-width: 1280px; margin: 0 auto;
         padding: 0 clamp(12px, 3vw, 24px) 12px; }
  .panel { background: var(--card); border: 1px solid var(--line); border-radius: 0 8px 8px 8px;
           padding: clamp(8px, 1.6vw, 16px); }
  .hidden { display: none !important; }

  /* Tab 1: widget Myfxbook, iframe dibuat selebar dan setinggi area yang tersedia */
  #widgetBox { width: 100%; overflow: hidden; }
  #widgetBox iframe { width: 100% !important; height: calc(100vh - 215px) !important;
                      min-height: 395px; border: 0; display: block; }

  /* Tab 2: tabel sentimen terurut */
  .bar-tools { display: flex; flex-wrap: wrap; gap: 8px 12px; align-items: center; margin-bottom: 10px; }
  .bar-tools input[type=text], .bar-tools input[type=password], .bar-tools input[type=number],
  .bar-tools select { padding: 6px 8px; border: 1px solid #c8d1db; border-radius: 6px; font: inherit; font-size: 14px; }
  .bar-tools input[type=number] { width: 64px; }
  .grow { flex: 1 1 220px; min-width: 0; }
  button.btn { padding: 7px 14px; border: 0; border-radius: 6px; background: var(--accent);
               color: #fff; font: inherit; font-size: 14px; cursor: pointer; }
  button.btn.alt { background: #e9eef3; color: var(--ink); }
  button.btn:disabled { opacity: .55; cursor: default; }
  .note { font-size: 12px; color: var(--muted); margin: 4px 0 10px; }
  .status { font-size: 12px; color: var(--muted); margin-top: 10px; }
  #list { display: flex; flex-direction: column; }
  .row { display: grid; align-items: center; gap: 4px 12px; padding: 8px 4px;
         border-bottom: 1px solid var(--line);
         grid-template-columns: 30px 88px 1fr 130px;
         grid-template-areas: "rank sym bar tag" ". meta meta meta"; }
  .rank { grid-area: rank; color: var(--muted); font-size: 12px; text-align: right; }
  .sym { grid-area: sym; font-weight: 600; }
  .bar { grid-area: bar; display: flex; height: 22px; border-radius: 4px; overflow: hidden; background: #e9eef3; }
  .seg { display: flex; align-items: center; justify-content: center; color: #fff;
         font-size: 12px; font-weight: 600; white-space: nowrap; overflow: hidden; }
  .seg.long { background: var(--long); }
  .seg.short { background: var(--short); }
  .tag { grid-area: tag; font-size: 13px; font-weight: 600; text-align: right; }
  .tag.long { color: var(--long); } .tag.short { color: var(--short); } .tag.even { color: var(--muted); }
  .meta { grid-area: meta; font-size: 12px; color: var(--muted); }
  .legend { display: flex; gap: 14px; font-size: 12px; color: var(--muted); margin-bottom: 6px; }
  .dot { display: inline-block; width: 10px; height: 10px; border-radius: 2px; margin-right: 4px; vertical-align: -1px; }
  footer { text-align: center; font-size: 11px; color: var(--muted); padding: 6px 0 14px; }

  @media (max-width: 640px) {
    .row { grid-template-columns: 26px 1fr auto;
           grid-template-areas: "rank sym tag" "bar bar bar" "meta meta meta"; }
    #widgetBox iframe { height: calc(100vh - 240px) !important; }
  }
</style>
</head>
<body>
<header>
  <h1>Sentimen Forex</h1>
  <span id="clock"></span>
</header>

<nav>
  <button class="tab active" data-panel="panelWidget">Widget Myfxbook</button>
  <button class="tab" data-panel="panelSorted">Urut Sentimen</button>
</nav>

<main>
  <section class="panel" id="panelWidget">
    <div id="widgetBox">
<!-- myfxbook.com outlook widget - Start -->
<div>
    <script class="powered" type="text/javascript"
            src="https://widgets.mfbcdn.net/scripts/fxOutlook.js?type=1&symbols=,2,3,4,5,6,7,8,9,10,11,12,13,14,17,20,24,25,26,27,28,29,46,47,48,49,51,103,107"></script>
</div>
<div style="font-size: 10px">
<a href="https://www.myfxbook.com" title="" class="myfxbookLink" target="_self" rel="noopener">
            Powered by Myfxbook.com</a>
    </div>

<script type="text/javascript">showOutlookWidget()</script>
<!-- myfxbook.com outlook widget - End -->
    </div>
  </section>

  <section class="panel hidden" id="panelSorted">
    <div id="loginBox">
      <p class="note">Tab ini mengurutkan Community Trend (Shorts vs Longs) dari persentase terbesar.
        Long dan Short diperlakukan sama. Masuk dengan akun Myfxbook Anda (password tidak disimpan).</p>
      <div class="bar-tools">
        <input type="text" id="email" class="grow" placeholder="Email Myfxbook" autocomplete="username">
        <input type="password" id="pass" class="grow" placeholder="Password" autocomplete="current-password">
        <label><input type="checkbox" id="remember"> Ingat email</label>
        <button class="btn" id="loginBtn">Login &amp; Ambil Data</button>
      </div>
    </div>

    <div id="toolbar" class="hidden">
      <div class="bar-tools">
        <input type="text" id="search" class="grow" placeholder="Cari pair, mis. EURUSD">
        <select id="sortMode">
          <option value="top">Persentase terbesar (Long/Short disamakan)</option>
          <option value="name">Nama pair A-Z</option>
        </select>
        <button class="btn" id="refreshBtn">Refresh</button>
        <label><input type="checkbox" id="auto"> Auto tiap
          <input type="number" id="mins" min="__MIN_AUTO__" max="240" value="15"> menit</label>
      </div>
      <div class="legend">
        <span><span class="dot" style="background:var(--long)"></span>Long</span>
        <span><span class="dot" style="background:var(--short)"></span>Short</span>
      </div>
      <div id="list"></div>
    </div>
    <div class="status" id="status"></div>
  </section>
</main>
<footer>Data sentimen trader retail dari Myfxbook. Bukan saran trading.</footer>

<script>
(function () {
  var WIDGET_REFRESH_MS = __WIDGET_REFRESH_MS__;
  var MIN_AUTO = __MIN_AUTO__;
  var rows = [];
  var busy = false;
  var autoTimer = null;

  function $(id) { return document.getElementById(id); }
  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text !== undefined) e.textContent = text;
    return e;
  }
  function setStatus(t) { $("status").textContent = t; }
  function setBusy(v) {
    busy = v;
    $("loginBtn").disabled = v;
    $("refreshBtn").disabled = v;
  }
  function fmtPct(v) { return Math.round(v) + "%"; }
  function fmtNum(v) { return v.toLocaleString("id-ID", { maximumFractionDigits: 2 }); }

  $("clock").textContent = "Dimuat: " + new Date().toLocaleString("id-ID");

  // Tab
  var tabs = document.querySelectorAll(".tab");
  tabs.forEach(function (btn) {
    btn.addEventListener("click", function () {
      tabs.forEach(function (b) { b.classList.toggle("active", b === btn); });
      document.querySelectorAll(".panel").forEach(function (p) {
        p.classList.toggle("hidden", p.id !== btn.dataset.panel);
      });
    });
  });

  // Muat ulang iframe widget secara berkala
  setInterval(function () {
    var f = document.querySelector("#widgetBox iframe");
    if (f) { f.src = f.src; }
  }, WIDGET_REFRESH_MS);

  // Urutkan: persentase terbesar (max Long/Short) menurun, seri diurutkan nama
  function sortRows(list, mode) {
    var copy = list.slice();
    if (mode === "name") {
      copy.sort(function (a, b) { return a.symbol.localeCompare(b.symbol); });
    } else {
      copy.sort(function (a, b) {
        return (b.top_pct - a.top_pct) || a.symbol.localeCompare(b.symbol);
      });
    }
    return copy;
  }

  function render() {
    var q = $("search").value.trim().toUpperCase();
    var list = rows.filter(function (r) { return r.symbol.toUpperCase().indexOf(q) !== -1; });
    list = sortRows(list, $("sortMode").value);
    var box = $("list");
    box.replaceChildren();
    list.forEach(function (r, i) {
      var row = el("div", "row");
      row.appendChild(el("div", "rank", String(i + 1)));
      row.appendChild(el("div", "sym", r.symbol));

      var bar = el("div", "bar");
      var l = el("span", "seg long", r.long_pct >= 14 ? "Long " + fmtPct(r.long_pct) : "");
      l.style.width = r.long_pct + "%";
      var s = el("span", "seg short", r.short_pct >= 14 ? "Short " + fmtPct(r.short_pct) : "");
      s.style.width = r.short_pct + "%";
      bar.appendChild(l);
      bar.appendChild(s);
      row.appendChild(bar);

      var label = r.dominant === "long" ? "Long " + fmtPct(r.long_pct)
                : r.dominant === "short" ? "Short " + fmtPct(r.short_pct)
                : "Seimbang 50%";
      row.appendChild(el("div", "tag " + r.dominant, label));

      row.appendChild(el("div", "meta",
        "Volume L/S: " + fmtNum(r.long_vol) + " / " + fmtNum(r.short_vol) +
        " lot  |  Posisi L/S: " + fmtNum(r.long_pos) + " / " + fmtNum(r.short_pos)));
      box.appendChild(row);
    });
  }

  async function loadData() {
    if (busy) return;
    setBusy(true);
    setStatus("Mengambil data sentimen...");
    try {
      var res = await window.pywebview.api.outlook();
      if (!res.ok) { setStatus("Error: " + res.error); return; }
      rows = res.rows;
      render();
      setStatus("Diperbarui " + res.updated + " - " + rows.length + " pair.");
    } catch (e) {
      setStatus("Error: " + e);
    } finally {
      setBusy(false);
    }
  }

  async function doLogin() {
    if (!window.pywebview) {
      setStatus("Fitur ini hanya tersedia di aplikasi desktop (jendela WebView2).");
      return;
    }
    var email = $("email").value.trim();
    var pass = $("pass").value;
    if (!email || !pass) { setStatus("Isi email dan password Myfxbook."); return; }
    setBusy(true);
    setStatus("Login ke Myfxbook...");
    try {
      var res = await window.pywebview.api.login(email, pass, $("remember").checked);
      if (!res.ok) { setStatus("Error: " + res.error); return; }
      $("pass").value = "";
      $("loginBox").classList.add("hidden");
      $("toolbar").classList.remove("hidden");
    } catch (e) {
      setStatus("Error: " + e);
      return;
    } finally {
      setBusy(false);
    }
    loadData();
  }

  $("loginBtn").addEventListener("click", doLogin);
  $("pass").addEventListener("keydown", function (e) { if (e.key === "Enter") doLogin(); });
  $("refreshBtn").addEventListener("click", loadData);
  $("search").addEventListener("input", render);
  $("sortMode").addEventListener("change", render);
  $("auto").addEventListener("change", function () {
    clearInterval(autoTimer);
    autoTimer = null;
    if ($("auto").checked) {
      var m = Math.max(MIN_AUTO, parseInt($("mins").value, 10) || MIN_AUTO);
      $("mins").value = m;
      autoTimer = setInterval(loadData, m * 60000);
    }
  });

  window.addEventListener("pywebviewready", async function () {
    try {
      var email = await window.pywebview.api.saved_email();
      if (email) { $("email").value = email; $("remember").checked = true; }
    } catch (e) { /* abaikan */ }
  });
})();
</script>
</body>
</html>
"""


def build_page():
    return (
        PAGE_HTML.replace("__WIDGET_REFRESH_MS__", str(WIDGET_REFRESH_MINUTES * 60 * 1000))
        .replace("__MIN_AUTO__", str(MIN_AUTO_MINUTES))
    )


def write_page():
    folder = tempfile.mkdtemp(prefix="sentimen_forex_")
    path = os.path.join(folder, "index.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(build_page())
    return path


def main():
    page = write_page()
    api = Api()
    try:
        import webview

        window = webview.create_window(
            APP_TITLE, page, js_api=api, width=1000, height=760, min_size=(360, 480)
        )
        window.events.closed += api.logout
        webview.start(http_server=True)
    except Exception:  # noqa: BLE001
        # Cadangan: bila WebView2 tidak tersedia, buka di browser bawaan
        # (tab "Urut Sentimen" tidak berfungsi di mode ini).
        webbrowser.open(Path(page).as_uri())


if __name__ == "__main__":
    main()
