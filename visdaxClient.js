/**
 * Visdax Web SDK v1.1.0
 * B2B High-Fidelity Vision Restoration Client
 * Optimized for both Single and Batch Operations
 */
class VisdaxClient {
    constructor(config) {
        this.baseUrl = "https://api.visdax.com/api/v1";
        this.apiKey = config.apiKey;
        this.project = config.project;
        this.bucket = config.bucket;
        
        this.cacheName = 'visdax-vault-v1';
        this.maxSizeBytes = 500 * 1024 * 1024; // 500MB Hard Limit
    }

    _getHeaders() {
        return {
            "Authorization": `Bearer ${this.apiKey}`,
            "X-Visdax-Project": this.project,
            "X-Visdax-Bucket": this.bucket,
            "Content-Type": "application/json"
        };
    }

    // ==========================================
    // 1. SINGLE & BATCH SUBMISSION (UPLOAD)
    // ==========================================

    /**
     * Uploads a single file.
     * @param {File} file 
     */
    async submit(file) {
        const formData = new FormData();
        formData.append('file', file);
        
        const resp = await fetch(`${this.baseUrl}/post_file`, {
            method: 'POST',
            headers: { "Authorization": `Bearer ${this.apiKey}` },
            body: formData
        });
        
        if (!resp.ok) throw new Error(`Visdax: Upload Failed (${resp.status})`);
        return await resp.json();
    }

    /**
     * Uploads multiple files in sequence.
     * @param {FileList|File[]} files 
     */
    async submitBatch(files) {
        const results = [];
        for (const file of files) {
            try {
                const res = await this.submit(file);
                results.push(res);
            } catch (err) {
                results.push({ file: file.name, ok: false, error: err.message });
            }
        }
        return results;
    }

    // ==========================================
    // 2. SINGLE & BATCH RETRIEVAL (DOWNLOAD + LRU)
    // ==========================================

    /**
     * Loads a single asset.
     * Wraps loadBatch for consistent logic and caching.
     */
    async load(key) {
        const result = await this.loadBatch([key]);
        return result[key];
    }

    /**
     * Validates and loads high-fidelity images into the 500MB vault.
     * @param {string[]} keys - List of asset keys.
     * @returns {Object} Map of { key: blobUrl }
     */
    async loadBatch(keys) {
        const cache = await caches.open(this.cacheName);
        const etags = {};

        // 1. Check local vault for existing assets
        for (const key of keys) {
            const cached = await cache.match(key);
            if (cached) etags[key] = cached.headers.get('ETag');
        }

        // 2. Single 'Gatekeeper' revalidation ping
        const response = await fetch(`${this.baseUrl}/get_multifiles?restore=true`, {
            method: 'POST',
            headers: this._getHeaders(),
            body: JSON.stringify({ keys, etags })
        });

        if (!response.ok) throw new Error(`Visdax: API Error ${response.status}`);

        const data = await response.json();
        const finalUrls = {};

        // 3. Process results
        for (const asset of data.assets) {
            const key = asset.key;

            if (asset.status === 304) {
                // Verified active sub: Load from local cache
                const cachedResp = await cache.match(key);
                finalUrls[key] = URL.createObjectURL(await cachedResp.blob());
            } 
            else if (asset.status === 200) {
                // New/Updated content: Stream to local vault
                const blob = await (await fetch(`data:image/webp;base64,${asset.content}`)).blob();
                await this._enforceLRU(blob.size);
                
                const mockResponse = new Response(blob, {
                    headers: { 
                        'ETag': asset.etag, 
                        'Date': new Date().toUTCString(),
                        'Content-Type': 'image/webp'
                    }
                });
                
                await cache.put(key, mockResponse);
                finalUrls[key] = URL.createObjectURL(blob);
            }
        }
        return finalUrls;
    }

    async _enforceLRU(newSize) {
        const cache = await caches.open(this.cacheName);
        const keys = await cache.keys();
        let currentSize = 0;
        
        const entries = [];
        for (const request of keys) {
            const res = await cache.match(request);
            const blob = await res.blob();
            currentSize += blob.size;
            entries.push({ request, size: blob.size });
        }

        let i = 0;
        while (currentSize + newSize > this.maxSizeBytes && i < entries.length) {
            const oldest = entries[i];
            currentSize -= oldest.size;
            await cache.delete(oldest.request);
            i++;
        }
    }
}
