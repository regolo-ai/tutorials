# Corporate Security Rules and Coding Standards - AI & ML Pipeline

## SEC-01: Model & Input Vector Sanitization
* **Rule**: Never trust input data fed directly into LLMs, models, or vector stores. Unsanitized data can lead to prompt injection or denial of service.
* **Remediation**: Implement strict input schema validation (e.g., using `Pydantic`) and size/token limitations.

## SEC-02: Model Secrets & Inference Credentials
* **Rule**: Do not hardcode inference endpoints, HuggingFace hubs, or model provider API keys.
* **Remediation**: Use runtime environment variables to inject API keys, and keep separate non-production models for local testing.

## COD-01: Efficient Compute & Data Streaming (Memory Overflows)
* **Rule**: Do not load massive datasets or un-chunked embedding vectors entirely into CPU memory at once, which will cause container/server OOM (Out Of Memory) crashes.
* **Remediation**: Stream data from the database/S3 in batches, or use generators (`yield`) to execute calculations iteratively.

## COD-02: Floating Point & NaN Robustness
* **Rule**: Never assume calculation outputs are valid without catching `NaN` (Not-a-Number), division-by-zero, or infinite outputs.
* **Remediation**: Assert vector lengths and numerical boundaries before passing embeddings to vector stores or using Cosine Similarity calculations.
