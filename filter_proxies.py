import json
import urllib.request
import urllib.error

proxies_raw = """
46.161.6.165:8080
78.47.219.204:3128
134.209.29.120:8080
161.35.70.249:80
134.209.29.120:80
52.188.28.218:3128
209.97.150.167:3128
62.60.151.128:80
68.235.35.171:3128
209.97.150.167:80
159.203.61.169:8080
209.97.150.167:8080
195.158.8.123:3128
208.87.243.199:7878
144.76.42.215:8118
216.229.112.25:8080
159.203.61.169:80
103.3.246.71:3128
138.68.60.8:80
139.59.1.14:80
8.243.68.11:8080
41.223.119.156:3128
34.96.238.40:8080
59.6.25.118:3128
129.150.39.251:8000
162.240.154.26:3128
35.152.252.253:8080
144.125.164.158:8081
47.81.14.7:3129
144.125.164.222:8080
175.99.220.171:80
8.219.97.248:80
144.125.164.158:8080
164.68.110.241:8091
144.125.164.222:8081
140.238.184.182:3128
139.59.1.14:3128
8.212.160.196:8080
164.68.110.241:9992
173.212.246.157:3128
47.236.130.95:3128
103.147.246.18:8080
128.199.202.122:80
200.24.159.230:8080
128.199.202.122:8080
103.166.158.251:1111
59.153.16.214:1120
43.224.118.155:1121
89.43.132.247:8080
182.253.62.190:8080
193.95.53.131:8077
203.196.8.6:3128
103.245.110.198:1452
45.180.140.241:8080
212.2.254.246:3128
103.220.206.110:8585
103.157.79.145:1080
45.87.140.155:8080
164.138.205.119:8080
137.59.51.243:1120
38.210.179.77:999
27.147.163.188:40544
194.87.77.22:80
20.27.219.85:8080
49.254.245.70:15648
115.144.173.67:15648
"""

proxy_list = [p.strip() for p in proxies_raw.strip().split("\n") if p.strip()]
ips = [p.split(":")[0] for p in proxy_list]

chunk_size = 100
fr_proxies = []

for i in range(0, len(ips), chunk_size):
    chunk = ips[i : i + chunk_size]
    try:
        req = urllib.request.Request("http://ip-api.com/batch", data=json.dumps(chunk).encode("utf-8"))
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode("utf-8"))

            for idx, result in enumerate(data):
                if result.get("countryCode") == "FR":
                    full_proxy = proxy_list[i + idx]
                    fr_proxies.append(full_proxy)
                    print(f"Found FR proxy: {full_proxy}")
    except Exception as e:
        print(f"Error querying batch: {e}")

print(f"Total FR proxies found: {len(fr_proxies)}")

if len(fr_proxies) > 0:
    for p in fr_proxies:
        print(f"PROXY:{p}")
else:
    print("No French proxies found. Printing first 10 generic ones as backup:")
    for p in proxy_list[:10]:
        print(f"PROXY:{p}")
