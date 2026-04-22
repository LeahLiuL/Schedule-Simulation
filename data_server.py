"""
数据代理服务器 + 静态文件服务。

用途：
  - 静态文件（shipping_schedule.html 等）→ 来自 GitHub 目录或本地
  - 数据文件（fleet_schedule.json / ports.csv 等）→ 读写 P 盘共享目录
  - 航行距离（/distance）→ 调用 searoute 计算

启动：
  python data_server.py

环境变量：
  LOCAL_DATA_DIR   → P盘数据目录（默认：P:\04 上海操作中心\04 本部门共享\ClawReport\shipping_data）
  STATIC_DIR       → 静态文件目录（默认：当前目录）
  PORT             → 端口（默认：8899）
"""
import os
import json
import base64
import html
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

# ==================== 配置 ====================
PORT = int(os.environ.get("PORT", "8899"))
STATIC_DIR = os.environ.get("STATIC_DIR", os.path.dirname(os.path.abspath(__file__)))
LOCAL_DATA_DIR = os.environ.get(
    "LOCAL_DATA_DIR",
    r"P:\04 上海操作中心\04 本部门共享\ClawReport\shipping_data"
)

print(f"Static dir: {STATIC_DIR}")
print(f"Data dir:   {LOCAL_DATA_DIR}")

# ==================== searoute 距离计算 ====================
try:
    import searoute
    HAS_SEAROUTE = True
except ImportError:
    HAS_SEAROUTE = False
    print("  searoute not installed - distance calculation disabled")

# 常用港口坐标（port_code → (lat, lon)）
PORT_COORDS = {
    "AEAUH": (24.47, 54.37), "AEDUB": (25.25, 55.28), "AEKLF": (25.53, 56.35),
    "CNTAO": (36.07, 120.38), "CNSHA": (31.23, 121.47), "CNNGB": (29.87, 121.55),
    "CNXMN": (24.45, 118.08), "SGSIN": (1.27, 103.85), "MYPKG": (3.00, 101.40),
    "INMUN": (22.47, 69.71), "PKKHI": (24.85, 66.98), "OMSOH": (24.35, 56.73),
    "KHPNH": (11.56, 104.92), "THBKK": (13.68, 100.50), "VNSGN": (10.76, 106.66),
    "JPTYO": (35.43, 139.65), "JPOSA": (34.67, 135.23), "KRPUS": (35.10, 129.04),
    "HKHKG": (22.30, 114.17), "TWKHH": (22.60, 120.30), "USLAX": (33.74, -118.27),
    "USNYC": (40.71, -74.01), "NLRTM": (51.92, 4.50), "DEHAM": (53.55, 9.99),
    "GBLON": (51.51, -0.13), "AEJEA": (25.02, 55.03),
}

def calc_distance(from_code, to_code):
    """计算两个港口之间的航行距离"""
    if from_code == to_code:
        return 0
    c1 = PORT_COORDS.get(from_code)
    c2 = PORT_COORDS.get(to_code)
    if not c1 or not c2:
        return None
    if not HAS_SEAROUTE:
        return None
    try:
        route = searoute.searoute((c1[1], c1[0]), (c2[1], c2[0]), units="naut")
        return round(route["properties"]["length"])
    except Exception:
        return None

# ==================== HTTP Handler ====================
class DataProxyHandler(SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        print(f"  [{self.log_date_time_string()}] {args[0]}")

    def send_json(self, data, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))

    def send_text(self, content, content_type="text/plain; charset=utf-8"):
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(content.encode("utf-8") if isinstance(content, str) else content)

    def read_data_file(self, filename):
        """从 LOCAL_DATA_DIR 读取文件"""
        safe_path = os.path.normpath(os.path.join(LOCAL_DATA_DIR, filename))
        if not safe_path.startswith(os.path.normpath(LOCAL_DATA_DIR)):
            return None, 403, "Forbidden"
        if not os.path.isfile(safe_path):
            return None, 404, f"File not found: {filename}"
        try:
            with open(safe_path, "r", encoding="utf-8") as f:
                return f.read(), 200, None
        except Exception as e:
            return None, 500, str(e)

    def write_data_file(self, filename, content):
        """写入文件到 LOCAL_DATA_DIR"""
        safe_path = os.path.normpath(os.path.join(LOCAL_DATA_DIR, filename))
        if not safe_path.startswith(os.path.normpath(LOCAL_DATA_DIR)):
            return None, 403, "Forbidden"
        try:
            os.makedirs(os.path.dirname(safe_path), exist_ok=True)
            with open(safe_path, "w", encoding="utf-8") as f:
                f.write(content)
            return {"status": "ok", "saved": filename, "path": safe_path}, 200, None
        except Exception as e:
            return None, 500, str(e)

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")

        # ==================== /distance ====================
        if path == "/distance":
            params = parse_qs(parsed.query)
            from_code = (params.get("from", [""])[0] or "").strip().upper()
            to_code   = (params.get("to",   [""])[0] or "").strip().upper()
            if not from_code or not to_code:
                return self.send_json({"error": "Missing 'from' or 'to' parameter"}, 400)
            dist = calc_distance(from_code, to_code)
            if dist is None:
                return self.send_json({
                    "error": f"Cannot calculate distance for {from_code} → {to_code}",
                    "from": from_code, "to": to_code
                }, 404)
            return self.send_json({
                "from": from_code, "to": to_code,
                "distance_nm": dist, "method": "searoute"
            })

        # ==================== /health ====================
        if path == "/health":
            return self.send_json({"status": "ok", "searoute": HAS_SEAROUTE})

        # ==================== /data/<filename> ====================
        if path.startswith("/data/"):
            filename = path[6:]  # 去掉 /data/
            content, status, err = self.read_data_file(filename)
            if err:
                return self.send_json({"error": err}, status)
            return self.send_text(content)

        # ==================== 静态文件 ====================
        # 去掉前缀 /data/
        return SimpleHTTPRequestHandler.do_GET(self)

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")

        # ==================== /data/<filename> ====================
        if path.startswith("/data/"):
            filename = path[6:]
            content_length = int(self.headers.get("Content-Length", 0))
            content = self.rfile.read(content_length).decode("utf-8", errors="replace")
            result, status, err = self.write_data_file(filename, content)
            if err:
                return self.send_json({"error": err}, status)
            return self.send_json(result, status)

        self.send_response(405)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"error": "Method Not Allowed"}).encode())

    def end_headers(self):
        # 允许跨域（CORS）
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        SimpleHTTPRequestHandler.end_headers(self)

    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()


if __name__ == "__main__":
    import socket
    # Get local IP
    hostname = socket.gethostname()
    local_ip = socket.gethostbyname(hostname)
    server = HTTPServer(("0.0.0.0", PORT), DataProxyHandler)
    print(f"\n========================================")
    print(f"  Shipping Schedule Server")
    print(f"========================================")
    print(f"  Local:   http://localhost:{PORT}/shipping_schedule.html")
    print(f"  Network: http://{local_ip}:{PORT}/shipping_schedule.html")
    print(f"  Data dir: {LOCAL_DATA_DIR}")
    print(f"========================================")
    print(f"  Other computers: open above 'Network' URL")
    print(f"  Ctrl+C to stop\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped")
