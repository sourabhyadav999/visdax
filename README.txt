# visdax
Visdax : High-Fidelity Vision SDK
Unified Vision Restoration and Storage for Developers.
This is Official Repo for visdax.com client.

Visdax provides a seamless way to store, restore, and serve high-fidelity vision data. Our SDKs are engineered to prioritize performance and cost-efficiency by implementing a Compulsory Local Vault (LRU Cache). This ensures that expensive vision assets are transferred over the network exactly once, drastically reducing egress costs for your host infrastructure. This is Optimized to reduce Client Egress Data to save them from Egress Cost of their Host, please use the Official Version.


Python Example:
from visdax import VisdaxClient

# Initialize the client
client = VisdaxClient(
    api_key="your_api_key",
    project="autonomous_driving",
    bucket="calibration_frames"
)

# 1. Submit high-res frames for restoration
client.submit("frame_001.png")

# 2. Retrieve restored assets (Automatic 500MB LRU Cache)
# This will only download from the server if not already in local storage
image_paths = client.load_batch(["frame_001", "frame_002"])
print(f"Assets ready at: {image_paths}")


JS Example:
import { VisdaxClient } from '@visdax/sdk';

const visdax = new VisdaxClient({
    apiKey: "your_api_key",
    project: "autonomous_driving",
    bucket: "calibration_frames"
});

// Load restored assets directly into your UI
// Returns a Map of { key: blobUrl } for immediate use in <img> tags
const assets = await visdax.loadBatch(["frame_001", "frame_002"]);

document.getElementById('my-image').src = assets["frame_001"];




Documentation:

1. The "Vault" (LRU Caching)
Both SDKs implement a 500MB Local Vault to minimize redundant data transfers.

Python: Stores assets in ~/.visdax_cache using file-system modification times to track usage.

JavaScript: Uses the Browser Cache API (visdax-vault-v1) for persistent storage that survives page refreshes.

Why use the SDK instead of direct API calls? Direct API calls bypass the local vault entirely. Using the load() or load_batch() methods triggers a "Gatekeeper" check: the server verifies if you already have the data via ETag. If you do, it returns a 304 Not Modified, preventing data egress and saving you money on cloud provider transfer fees.



2. API Reference: Python SDK
Method                                                      Description
submit(file_path)                                           Uploads a single file to the Visdax restoration engine.
"submit_batch(file_paths, n_jobs=4)"                        Parallel upload for high-volume datasets using multi-threading.
load(key)                                                   Retrieves a single restored asset. Checks local cache first.
load_batch(keys)                                            Retrieves multiple assets in a single network request for efficiency.

3. API Reference: JavaScript SDK
Method                                                      Description
submit(file)                                                Uploads a File object directly from the browser.
submitBatch(files)                                          Sequentially uploads a FileList or an array of File objects.
load(key)                                                   Returns a blobUrl for a single asset.
loadBatch(keys)                                             Returns an object mapping keys to blobUrl strings for UI rendering.


💡 Best Practices for Cost Savings
Egress Optimization
Visdax is architected to minimize Data Egress. Cloud providers (AWS, GCP, Azure) charge significantly for data leaving their networks (~$0.09/GB).

Always use load_batch: Combining requests reduces header overhead and network round-trips.

Respect the Vault: Advise your end-users not to clear browser data frequently to maintain high cache hit rates.

Developer Tip: If you see status 200 for an image you just downloaded, check if your local cache path is writable or if the browser storage quota is exceeded.

Performance
Our JavaScript SDK utilizes URL.createObjectURL(). This allows the browser to render high-fidelity images directly from memory or the local vault without the overhead of repeated base64 decoding.

🔒 Security
Your api_key is the primary credential for authorizing restorations and billing.

Backend: Never hardcode keys. Store them in environment variables (os.getenv).

Frontend: Use Domain Whitelisting in your Visdax Dashboard. This ensures your key is only functional when called from your approved website origins, preventing unauthorized usage.


