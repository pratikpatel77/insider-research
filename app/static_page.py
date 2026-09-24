"""Turn the live app's page into a standalone page for GitHub Pages.

The same page and script the local app uses, but with the scan result embedded in the file and
the "Scan again" button hidden (a static page can't scan)."""
import json

from ui import PAGE

SHIM = """<script>
const __D=__DATA__;
const __fetch=window.fetch.bind(window);
window.fetch=(u,o)=>{
 if(u==='/api/status')return Promise.resolve(new Response(JSON.stringify({running:false,msg:'Ready',pct:100,error:null,has_result:true})));
 if(u==='/api/result')return Promise.resolve(new Response(JSON.stringify(__D)));
 return __fetch(u,o)};
</script>
"""


def build(payload):
    data = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")
    page = PAGE
    for old, new in [
        ('<title>Insider Buy Screener</title>', '<title>Insider Buy Screener</title>\n<meta name="robots" content="noindex">'),
        ('href="/api/excel"', 'href="watchlist.xlsx" download'),
        ('</style>', '#run{display:none}</style>'),
        ('<script>\nconst $=', SHIM.replace("__DATA__", data) + '<script>\nconst $='),
    ]:
        if old not in page:
            raise RuntimeError(f"ui.py changed: could not find {old[:40]!r} to patch for the static page")
        page = page.replace(old, new, 1)
    return page
