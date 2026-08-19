import urllib.request
from urllib.error import HTTPError

boundary = "----BYC7"
fn = "tmp/test-word-contract.docx"
with open(fn, "rb") as f:
    data = f.read()

body = (
    ("--%s\r\n" % boundary).encode()
    + b'Content-Disposition: form-data; name="file"; filename="t.docx"\r\n'
    + b"Content-Type: application/octet-stream\r\n\r\n"
    + data
    + ("\r\n--%s--\r\n" % boundary).encode()
)

req = urllib.request.Request(
    "http://127.0.0.1:8765/api/word2pdf",
    data=body,
    headers={"Content-Type": "multipart/form-data; boundary=BYC7"},
)
try:
    print("OK:", urllib.request.urlopen(req, timeout=180).read().decode())
except HTTPError as e:
    print("HTTP", e.code, e.read().decode())
