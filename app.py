"""
Sentimen Forex
==============
Aplikasi desktop Windows yang menampilkan widget Community Outlook
resmi dari Myfxbook dalam satu jendela. Tidak perlu login.

Widget dimuat dari server Myfxbook (widgets.mfbcdn.net), sehingga
komputer harus terhubung ke internet.
"""

import os
import tempfile
import threading
import time
import webbrowser
from pathlib import Path

APP_TITLE = "Sentimen Forex"
REFRESH_MINUTES = 5  # muat ulang widget otomatis tiap N menit

PAGE_HTML = """<!doctype html>
<html lang="id">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Sentimen Forex</title>
<style>
  body { margin: 0; font-family: "Segoe UI", Arial, sans-serif; background: #f4f6f8; color: #1f2933; }
  header { display: flex; justify-content: space-between; align-items: center;
           padding: 14px 20px; background: #0f2a43; color: #fff; }
  header h1 { margin: 0; font-size: 20px; }
  #clock { font-size: 12px; opacity: .8; }
  main { display: flex; justify-content: center; padding: 16px 20px; }
  .card { background: #fff; border-radius: 8px; padding: 12px;
          box-shadow: 0 1px 4px rgba(0, 0, 0, .15); }
  footer { text-align: center; font-size: 11px; color: #6b7785; padding: 8px 0 16px; }
</style>
</head>
<body>
<header>
  <h1>Sentimen Forex</h1>
  <span id="clock"></span>
</header>
<main>
  <div class="card">
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
</main>
<footer>Data sentimen trader retail dari Myfxbook. Bukan saran trading.</footer>
<script>
  document.getElementById("clock").textContent =
    "Dimuat: " + new Date().toLocaleString("id-ID");
</script>
</body>
</html>
"""


def write_page():
    folder = tempfile.mkdtemp(prefix="sentimen_forex_")
    path = os.path.join(folder, "index.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(PAGE_HTML)
    return path


def auto_reload(window):
    while True:
        time.sleep(REFRESH_MINUTES * 60)
        try:
            window.evaluate_js("location.reload()")
        except Exception:  # noqa: BLE001
            pass


def main():
    page = write_page()
    try:
        import webview

        window = webview.create_window(
            APP_TITLE, page, width=900, height=720, min_size=(600, 500)
        )
        threading.Thread(target=auto_reload, args=(window,), daemon=True).start()
        webview.start(http_server=True)
    except Exception:  # noqa: BLE001
        # Cadangan: bila WebView2 tidak tersedia, buka di browser bawaan.
        webbrowser.open(Path(page).as_uri())


if __name__ == "__main__":
    main()
