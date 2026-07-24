import urllib.request, urllib.parse, json

tests = [
    ("empty", ""),
    ("special", "test <script>alert(1)</script> | pipe"),
    ("long", "a" * 1000),
    ("normal", "what is the weather today"),
    ("unicode", "caf\u00e9 r\u00e9sum\u00e9"),
    ("multiline", "hello\nworld\ntest"),
]

for name, q in tests:
    try:
        params = urllib.parse.urlencode({"q": q, "format": "json", "language": "en"})
        url = f"http://localhost:8080/search?{params}"
        req = urllib.request.Request(url, headers={"User-Agent": "Cozmo/1.0"})
        resp = urllib.request.urlopen(req, timeout=10)
        data = json.loads(resp.read())
        print(f"{name}: OK ({len(data.get('results',[]))} results)")
    except Exception as e:
        print(f"{name}: {e}")