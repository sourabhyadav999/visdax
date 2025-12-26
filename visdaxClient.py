import os, requests, hashlib, base64, shutil, time
from pathlib import Path
from pqdm.threads import pqdm

class VisdaxClient:
    def __init__(self, api_key, project, bucket, limit_mb=500):
        self.api_key = api_key
        self.project = project
        self.bucket = bucket
        self.limit = limit_mb * 1024 * 1024
        self.cache_path = Path("~/.visdax_cache").expanduser()
        self.cache_path.mkdir(parents=True, exist_ok=True)
        self.base_url = "https://api.visdax.com/api/v1"

    def _get_headers(self):
        return {
            "Authorization": f"Bearer {self.api_key}",
            "X-Visdax-Project": self.project,
            "X-Visdax-Bucket": self.bucket
        }

    # ==========================================
    # 1. SUBMISSION (UPLOAD) FUNCTIONS
    # ==========================================

    def submit(self, file_path):
        """Single file upload to 56k-Atomic Engine."""
        with open(file_path, 'rb') as f:
            files = {'file': (os.path.basename(file_path), f)}
            resp = requests.post(f"{self.base_url}/post_file", 
                                 headers=self._get_headers(), files=files)
        return resp.json()

    def submit_batch(self, file_paths, n_jobs=4):
        """Parallel upload for large datasets."""
        return pqdm(file_paths, self.submit, n_jobs=n_jobs)

    # ==========================================
    # 2. RETRIEVAL (DOWNLOAD + LRU) FUNCTIONS
    # ==========================================

    def _enforce_lru(self, incoming_size):
        """Strictly keeps the cache folder under 500MB."""
        files = sorted(self.cache_path.glob("*.webp"), key=os.path.getmtime)
        current_size = sum(f.stat().st_size for f in files)
        while current_size + incoming_size > self.limit and files:
            oldest = files.pop(0)
            current_size -= oldest.stat().st_size
            oldest.unlink()

    def load(self, key):
        """Single asset load with 304 Validator check."""
        # Use single item as a batch of 1 to keep logic consistent
        return self.load_batch([key])[0]

    def load_batch(self, keys):
        """
        The Core ML Function: Validates a batch of ETags.
        Returns paths to high-fidelity local restored files.
        """
        etags = {k: hashlib.md5(k.encode()).hexdigest() for k in keys}
        
        # Identify which files we already have locally to send for validation
        existing_etags = {}
        for k, e in etags.items():
            if (self.cache_path / f"{e}.webp").exists():
                existing_etags[k] = e

        payload = {"keys": keys, "etags": existing_etags}
        
        # Multi-file validation call to your app.py
        resp = requests.post(
            f"{self.base_url}/get_multifiles?restore=true", 
            json=payload, 
            headers=self._get_headers()
        )
        
        if resp.status_code != 200:
            raise Exception(f"Visdax Batch Failed: {resp.status_code} - {resp.text}")

        data = resp.json()
        final_paths = []

        for asset in data.get("assets", []):
            key = asset['key']
            local_file = self.cache_path / f"{etags[key]}.webp"

            if asset['status'] == 304:
                # Cache HIT: Server says sub is active and file is valid
                os.utime(local_file, None) # Update timestamp for LRU
                final_paths.append(str(local_file))
            
            elif asset['status'] == 200:
                # Cache MISS: New restored data received
                content = base64.b64decode(asset['content'])
                self._enforce_lru(len(content))
                local_file.write_bytes(content)
                final_paths.append(str(local_file))
            
            else:
                print(f"Visdax Error: Asset {key} failed with status {asset['status']}")

        return final_paths
