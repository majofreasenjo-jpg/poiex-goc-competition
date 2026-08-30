# Firestore Adapter Contract — Local Evidence Only

Status: `LOCAL_ADAPTER_CONTRACT_IMPLEMENTED / REAL_FIRESTORE_NOT_EXECUTED`

The deterministic control plane now depends on a `RuntimeStore` protocol rather than
`MemoryStore` directly. Two implementations exist:

- `MemoryStore`: deterministic local regression adapter.
- `FirestoreStore`: Google Cloud Firestore adapter with lazy credentialed client creation.

The Firestore adapter persists AgentRecord, AuthorityLease, EvidenceItem,
MaterialTarget, ExecutionReceipt and SyntheticActionResult using explicit schema
conversion. Sets are serialized as sorted arrays; EvidenceSourceType is stored by
value; datetimes remain datetime values; MaterialTarget hashes are recomputed and
verified on read; synthetic action hashes are recomputed during replay.

Local contract tests inject a fake Firestore client that exposes the same public
`collection().document().set()/get()` surface used by the official Python client.
These tests prove adapter semantics without network or credentials. They do not prove
Google Cloud deployment, IAM, Firestore database creation, security rules, latency,
consistency under real concurrency or contest compliance.

Truth ceiling:

`LOCAL_ADAPTER_CONTRACT_PASS != FIRESTORE_DEPLOYMENT_EVIDENCE`
`FAKE_CLIENT != FIRESTORE`
`SCHEMA_ROUNDTRIP != CLOUD_HARD_GATE`
