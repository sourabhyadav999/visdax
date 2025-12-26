import os, requests, hashlib, base64, shutil
from pathlib import Path

class VisdaxClient:
    def __init__(self, api_key, project, bucket, limit_mb=500):
        self.api_key = api_key
        self.project = project
        self.bucket = bucket
        self.limit = limit_mb * 1024 * 1024
        self.cache_path = Path("~/.visdax_cache").expanduser()
        self.cache_path.mkdir(parents=True, exist_ok=True)
        self.base_url = "https://api.visdax.ai/api/v1"

    def _get_headers(self):
        return {
            "Authorization": f"Bearer {self.api_key}",
            "X-Visdax-Project": self.project,
            "X-Visdax-Bucket": self.bucket
        }

    def _enforce_lru(self, incoming_size):
        files = sorted(self.cache_path.glob("*.webp"), key=os.path.getmtime)
        current_size = sum(f.stat().st_size for f in files)
        while current_size + incoming_size > self.limit and files:
            oldest = files.pop(0)
            current_size -= oldest.stat().st_size
            oldest.unlink()

    def load(self, key):
        """Single Asset Load with 304 Revalidation."""
        etag = hashlib.md5(key.encode()).hexdigest()
        local_file = self.cache_path / f"{etag}.webp"
        
        headers = self._get_headers()
        if local_file.exists(): headers["If-None-Match"] = etag

        resp = requests.get(f"{self.base_url}/get_file?key={key}&restore=true", headers=headers, stream=True)
        
        if resp.status_code == 304:
            os.utime(local_file, None)
            return str(local_file)
        
        if resp.status_code == 200:
            self._enforce_lru(int(resp.headers.get('Content-Length', 0)))
            with open(local_file, "wb") as f: shutil.copyfileobj(resp.raw, f)
            return str(local_file)
        
        raise Exception(f"Visdax Auth Error: {resp.status_code}")

    def load_batch(self, keys):
        """Batch Asset Load with Parallel Revalidation."""
        etags = {k: hashlib.md5(k.encode()).hexdigest() for k in keys}
        payload = {"keys": keys, "etags": {k: v for k, v in etags.items() if (self.cache_path / f"{v}.webp").exists()}}

        resp = requests.post(f"{self.base_url}/get_multifiles?restore=true", json=payload, headers=self._get_headers())
        data = resp.json()
        
        paths = []
        for asset in data.get("assets", []):
            local_file = self.cache_path / f"{etags[asset['key']]}.webp"
            if asset['status'] == 304:
                os.utime(local_file, None)
            elif asset['status'] == 200:
                content = base64.b64decode(asset['content'])
                self._enforce_lru(len(content))
                local_file.write_bytes(content)
            paths.append(str(local_file))
        return paths
