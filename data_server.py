"""
数据代理服务器 + 静态文件服务。

用途：
  - 静态文件（shipping_schedule.html 等）→ 来自本地
  - 数据文件（fleet_schedule.json / ports.csv 等）→ 读写 P 盘共享目录
  - 航行距离（/distance）→ 调用 searoute 计算

启动：
  python data_server.py
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

    # ==================== 船舶数据解析 ====================
    def parse_vessel_text(self, text):
        """解析粘贴的船舶数据文本，返回船舶参数和油耗数据"""
        lines = text.strip().split('\n')
        result = {
            'particular': {},
            'fuel': [],
            'success': True,
            'warnings': []
        }

        # 字段映射（不区分大小写）
        field_map = {
            'vessel_name': ['vessel name', 'ship name', 'name', 'shipname'],
            'call_sign': ['call sign', 'callsign', '呼号'],
            'imo': ['imo'],
            'flag': ['flag', '旗籍'],
            'year_built': ['year built', 'built'],
            'teu': ['teu', 'capacity'],
            'homogeneous': ['homogeneous', 'homo'],
            'grt': ['grt'],
            'nrt': ['nrt'],
            'scantling_draft': ['scantling draft', 'draft'],
            'dwt': ['dwt', 'deadweight'],
            'loa': ['loa', 'length'],
            'breadth': ['breadth', 'beam'],
            'depth': ['depth'],
            'reefer_plugs': ['reefer plug', 'reefer'],
            'class': ['class'],
        }

        def clean_num(s):
            """提取数值"""
            if not s:
                return ''
            # 取第一个数字/小数/负号
            m = re.search(r'-?\d+\.?\d*', s)
            return m.group(0) if m else ''

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # 尝试提取键值对
            parts = None
            for sep in [':', '\t', '=', ' - ']:
                if sep in line and len(line.split(sep, 1)) == 2:
                    parts = line.split(sep, 1)
                    break

            if not parts or len(parts) != 2:
                continue

            key = parts[0].strip().lower()
            value = parts[1].strip()

            if not value:
                continue

            # 匹配 Particular 字段
            for field, aliases in field_map.items():
                if any(alias in key for alias in aliases):
                    if field in ['teu', 'homogeneous', 'grt', 'nrt', 'dwt', 'loa', 'breadth', 'depth', 'reefer_plugs', 'year_built', 'scantling_draft']:
                        result['particular'][field] = clean_num(value)
                    else:
                        result['particular'][field] = value
                    break

            # 尝试解析油耗行
            line_lower = line.lower()
            if any(p in line_lower for p in ['kn', 'kt', 'speed', 'lsfo', 'mgo', 'hsfo', 'me ', 'aux']):
                # 提取速度
                speed_match = re.search(r'(\d{2})\s*(?:kn|kt|knot)', line_lower)
                if speed_match:
                    speed = int(speed_match.group(1))
                    fuel_row = {'speed': speed, 'lsfo': '', 'hsfo': '', 'mgo': '', 'port_lsfo': '', 'port_mgo': ''}

                    # 提取 LSFO
                    lsfo_match = re.search(r'lsfo[:\s]*(\d+\.?\d*)', line_lower)
                    if lsfo_match:
                        fuel_row['lsfo'] = lsfo_match.group(1)

                    # 提取 HSFO
                    hsfo_match = re.search(r'hsfo[:\s]*(\d+\.?\d*)', line_lower)
                    if hsfo_match:
                        fuel_row['hsfo'] = hsfo_match.group(1)

                    # 提取 MGO（主辅机合计）
                    mgo_match = re.search(r'mgo[:\s]*(\d+\.?\d*)', line_lower)
                    aux_match = re.search(r'aux[:\s]*(\d+\.?\d*)', line_lower)
                    me_match = re.search(r'me\s*(\d+\.?\d*)', line_lower)

                    mgo_total = 0
                    if mgo_match:
                        mgo_total += float(mgo_match.group(1))
                    if aux_match:
                        mgo_total += float(aux_match.group(1))
                    elif me_match and not lsfo_match:
                        # 可能是 ME 油耗
                        me_val = float(me_match.group(1))
                        mgo_total += me_val
                        if not lsfo_match:
                            fuel_row['lsfo'] = me_match.group(1)

                    if mgo_total > 0:
                        fuel_row['mgo'] = str(mgo_total)

                    # 提取 Port Stay
                    port_match = re.search(r'port[:\s]*(\d+\.?\d*)', line_lower)
                    if port_match:
                        fuel_row['port_lsfo'] = port_match.group(1)
                        fuel_row['port_mgo'] = port_match.group(1)

                    result['fuel'].append(fuel_row)

        # 清理 particular 数据
        if 'imo' in result['particular']:
            result['particular']['imo'] = clean_num(result['particular']['imo'])

        # 按速度排序
        result['fuel'] = sorted(result['fuel'], key=lambda x: x.get('speed', 0), reverse=True)

        # 如果没有解析到数据
        if not result['particular'] and not result['fuel']:
            result['success'] = False
            result['warnings'].append('无法识别船舶数据，请检查格式')

        return result

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")

        # ==================== /parse ====================
        if path == "/parse":
            content_length = int(self.headers.get("Content-Length", 0))
            content = self.rfile.read(content_length).decode("utf-8", errors="replace")
            try:
                data = json.loads(content)
                text = data.get('text', '')
                if not text.strip():
                    return self.send_json({'success': False, 'error': '请输入船舶数据文本'}, 400)
                result = self.parse_vessel_text(text)
                return self.send_json(result, 200 if result['success'] else 400)
            except Exception as e:
                return self.send_json({'success': False, 'error': str(e)}, 500)

        # ==================== /save-vessel ====================
        if path == "/save-vessel":
            content_length = int(self.headers.get("Content-Length", 0))
            content = self.rfile.read(content_length).decode("utf-8", errors="replace")
            try:
                data = json.loads(content)
                return self._save_vessel_data(data)
            except Exception as e:
                return self.send_json({'success': False, 'error': str(e)}, 500)

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

    def _save_vessel_data(self, data):
        """保存船舶数据到 vessels.csv, particular.csv, bestmodel.csv"""
        try:
            vessel_code = data.get('vessel_code', '').strip().upper()
            vessel_name = data.get('vessel_name', '').strip()
            fuel_data = data.get('fuel_data', [])
            particular = data.get('particular', {})
            bestmodel = data.get('bestmodel', {})

            errors = []
            saved = []

            # 1. 保存 vessels.csv（油耗数据）
            if fuel_data:
                vessels_path = os.path.join(LOCAL_DATA_DIR, 'vessels.csv')
                rows = []
                existing_idx = -1

                if os.path.isfile(vessels_path):
                    with open(vessels_path, 'r', encoding='utf-8') as f:
                        reader = csv.reader(f)
                        rows = list(reader)
                        for i, row in enumerate(rows):
                            if row and row[0].upper() == vessel_code:
                                existing_idx = i
                                break

                # 如果已存在，删除旧数据行
                if existing_idx >= 0:
                    # 删除所有该船的数据行
                    rows = [r for i, r in enumerate(rows) if not (i == existing_idx or (i > 0 and rows[i][0].upper() == vessel_code))]

                # 添加表头（如果不存在）
                if not rows:
                    rows.append(['vessel_code', 'vessel_name', 'speed', 'lsfo', 'hsfo', 'mgo', 'port_lsfo', 'port_mgo', 'wait_time', 'remark'])

                # 添加船名行
                rows.append([vessel_code, vessel_name] + [''] * 8)

                # 添加油耗数据
                for fd in fuel_data:
                    rows.append([
                        vessel_code,
                        vessel_name,
                        str(fd.get('speed', '')),
                        str(fd.get('lsfo', '')),
                        str(fd.get('hsfo', '')),
                        str(fd.get('mgo', '')),
                        str(fd.get('port_lsfo', '')),
                        str(fd.get('port_mgo', '')),
                        '', ''
                    ])

                with open(vessels_path, 'w', encoding='utf-8', newline='') as f:
                    csv.writer(f).writerows(rows)
                saved.append('vessels.csv')

            # 2. 保存 cul_ship_particular.csv
            if particular:
                part_path = os.path.join(LOCAL_DATA_DIR, 'cul_ship_particular.csv')
                rows = []
                headers = ['Vessel Name', 'Call Sign', 'IMO', 'Flag', 'Year Built',
                           'TEU', 'Homogeneous', 'GRT', 'NRT', 'Scantling Draft',
                           'DWT', 'LOA', 'Breadth', 'Depth', 'Reefer Plugs', 'Class']

                if os.path.isfile(part_path):
                    with open(part_path, 'r', encoding='utf-8') as f:
                        reader = csv.reader(f)
                        rows = list(reader)
                        if not rows:
                            rows = [headers]

                        # 确保有足够的行
                        while len(rows) < len(headers):
                            rows.append([''] * len(rows[0]) if rows else headers)

                        # 查找或添加船舶列
                        vessel_col = -1
                        for i, name in enumerate(rows[0]):
                            if name and vessel_name.lower() in name.lower():
                                vessel_col = i
                                break

                        if vessel_col < 0:
                            # 添加新列
                            vessel_col = len(rows[0])
                            for row in rows:
                                row.append('')
                else:
                    rows = [headers]
                    for _ in range(len(headers) - 1):
                        rows.append([''] * len(headers))
                    vessel_col = 0

                # 字段映射
                field_to_row = {
                    'vessel_name': 0, 'call_sign': 1, 'imo': 2, 'flag': 3,
                    'year_built': 4, 'teu': 5, 'homogeneous': 6, 'grt': 7,
                    'nrt': 8, 'scantling_draft': 9, 'dwt': 10, 'loa': 11,
                    'breadth': 12, 'depth': 13, 'reefer_plugs': 14, 'class': 15
                }

                rows[0][vessel_col] = vessel_name
                for field, value in particular.items():
                    if field in field_to_row:
                        rows[field_to_row[field]][vessel_col] = str(value)

                with open(part_path, 'w', encoding='utf-8', newline='') as f:
                    csv.writer(f).writerows(rows)
                saved.append('cul_ship_particular.csv')

            # 3. 保存 cul_vessel_bestmodel.csv
            if bestmodel and bestmodel.get('lane'):
                bm_path = os.path.join(LOCAL_DATA_DIR, 'cul_vessel_bestmodel.csv')
                rows = []
                headers = ['Vessel Name', 'Service Lane', 'Max Cargo Weight (Ton)', 'Max TEU',
                           'Min 20\' required (only for footpad)', 'Max TEU2',
                           'Min 20\' required (without slot loss)', 'Suggested BSA', 'Remark']

                if os.path.isfile(bm_path):
                    with open(bm_path, 'r', encoding='utf-8') as f:
                        reader = csv.reader(f)
                        rows = list(reader)
                        if not rows:
                            rows = [headers]
                else:
                    rows = [headers]

                # 查找或添加
                bm_row_idx = -1
                for i, row in enumerate(rows):
                    if row and vessel_name.lower() in row[0].lower() and bestmodel.get('lane', '').upper() in row[1].upper():
                        bm_row_idx = i
                        break

                new_row = [
                    vessel_name,
                    bestmodel.get('lane', '').upper(),
                    bestmodel.get('max_cargo', ''),
                    bestmodel.get('max_teu', ''),
                    '',
                    '',
                    '',
                    bestmodel.get('bsa', ''),
                    bestmodel.get('remark', '')
                ]

                if bm_row_idx >= 0:
                    rows[bm_row_idx] = new_row
                else:
                    rows.append(new_row)

                with open(bm_path, 'w', encoding='utf-8', newline='') as f:
                    csv.writer(f).writerows(rows)
                saved.append('cul_vessel_bestmodel.csv')

            return self.send_json({'success': True, 'saved': saved})

        except Exception as e:
            return self.send_json({'success': False, 'error': str(e)}, 500)

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
