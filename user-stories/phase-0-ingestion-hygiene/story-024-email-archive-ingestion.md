# Story 024: Email Archive Ingestion (The Lethe)

**As a** user with large email archives
**I want** my emails cleaned, clustered, and stored in The Lethe (archive DB)
**So that** I can search emails by topic without polluting the core knowledge clustering

## 🎯 Architectural Note

**This story ingests emails into The Lethe collection (NOT The Muses).**

**Why**: Emails are reference/archive material, not core curated knowledge. The Lethe is designed for large-scale storage and retrieval, while The Muses (Story 000) is for clustering and pattern detection on your Obsidian vault.

**See [SYSTEM_ARCHITECTURE.md](../SYSTEM_ARCHITECTURE.md) for complete system architecture.**

## Acceptance Criteria
- [ ] Ingest emails from mbox, Thunderbird, or pre-cleaned TSV
- [ ] Clean emails: remove HTML, tracking codes, signatures, URLs
- [ ] Embed email bodies using Ollama (qwen3-embedding:0.6b)
- [ ] Cluster emails by semantic content (not sender/company)
- [ ] Label clusters with TF-IDF keywords (multilingual: EN/DE/NO)
- [ ] Classify clusters by TYPE (newsletters, tracking, invoices, personal)
- [ ] Store in Weaviate collection "The Lethe" (archive)
- [ ] Export curated emails to Obsidian as markdown notes
- [ ] Performance: 19k emails in <12 hours on Pi 5

## Technical Notes

### Architecture (Adapted from email-hygiene-pipeline)

```python
class EmailIngestor:
    """
    Based on email-hygiene-pipeline cleaner
    """
    def __init__(self, source_path: str, weaviate_client: Client):
        self.source_path = source_path  # TSV or email directory
        self.client = weaviate_client
        self.collection_name = "TheLethe"  # Mnemosyne archive

    def ingest_emails(self):
        # 1. Load from TSV (pre-cleaned) or raw mbox
        emails = self.load_emails(self.source_path)

        # 2. For each email
        for email in emails:
            # 3. Clean content
            cleaned = self.clean_email(email)

            # Skip low-quality emails
            if not self.quality_check(cleaned):
                continue

            # 4. Embed via Ollama
            embedding = self.get_embedding(cleaned.body)

            # 5. Store in Weaviate
            self.store_email({
                "subject": cleaned.subject,
                "body": cleaned.body,
                "sender": cleaned.sender,
                "date": cleaned.date,
                "vector": embedding
            })

        # 6. Cluster emails
        clusters = self.cluster_emails()

        # 7. Label clusters with TF-IDF
        for cluster in clusters:
            keywords = self.extract_keywords(cluster)
            cluster.keywords = keywords

        # 8. Classify clusters with LLM
        for cluster in clusters:
            classification = self.classify_cluster(cluster)
            cluster.type = classification  # newsletter, tracking, etc.

        # 9. Export KEEP clusters to Obsidian
        self.export_to_obsidian(clusters)
```

### Email Cleaning Pipeline

```python
def clean_email(email: Email) -> CleanedEmail:
    """
    Aggressive cleaning for semantic quality
    """
    body = email.body

    # 1. Parse HTML with BeautifulSoup
    if '<html>' in body.lower():
        soup = BeautifulSoup(body, 'html.parser')
        body = soup.get_text()

    # 2. Remove URLs
    body = re.sub(r'https?://[^\s]+', '', body)
    body = re.sub(r'www\.[^\s]+', '', body)

    # 3. Remove email addresses
    body = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '', body)

    # 4. Remove tracking codes
    body = re.sub(r'\?utm_[^\s]+', '', body)

    # 5. Remove HTML entities
    body = re.sub(r'&nbsp;|&#160;|&amp;', ' ', body)

    # 6. Remove email signatures (heuristic: after "---" or "Best regards")
    signature_patterns = [
        r'\n---\n.*',
        r'\nBest regards,.*',
        r'\nSent from my.*'
    ]
    for pattern in signature_patterns:
        body = re.sub(pattern, '', body, flags=re.DOTALL)

    # 7. Normalize whitespace
    body = re.sub(r'\s+', ' ', body).strip()

    return CleanedEmail(
        subject=email.subject,
        body=body,
        sender=email.sender,
        date=email.date
    )
```

### Quality Filters

```python
def quality_check(email: CleanedEmail) -> bool:
    """
    Based on email-hygiene metrics:
    - 74% of emails pass quality check
    - Rejects: encoding errors, too short, too long
    """
    body = email.body

    # Reject encoding errors (mojibake detection)
    if contains_mojibake(body):
        return False

    # Reject too short (likely just tracking pixels)
    if len(body) < 50:
        return False

    # Truncate too long (keep first 8000 chars for embedding)
    if len(body) > 8000:
        email.body = body[:8000]

    # Median body length should be ~822 chars (optimal)
    return True

def contains_mojibake(text: str) -> bool:
    """Detect encoding errors"""
    mojibake_patterns = [
        r'Ã¼|Ã¶|Ã¤',  # Broken German umlauts
        r'\ufffd',     # Unicode replacement character
        r'â€™|â€œ'   # Broken smart quotes
    ]
    return any(re.search(p, text) for p in mojibake_patterns)
```

### Clustering Strategy

```python
from sklearn.cluster import MiniBatchKMeans
from sklearn.decomposition import PCA

def cluster_emails(embeddings: List[List[float]], n_emails: int) -> List[Cluster]:
    """
    Based on email-hygiene clustering:
    - Target: ~1 cluster per 50 emails
    - 19k emails → ~400 clusters
    - Mean similarity: 0.6171
    """
    n_clusters = max(10, n_emails // 50)

    # PCA for dimensionality reduction (optional speedup)
    pca = PCA(n_components=128)
    reduced_embeddings = pca.fit_transform(embeddings)

    # MiniBatchKMeans for large datasets
    kmeans = MiniBatchKMeans(
        n_clusters=n_clusters,
        batch_size=1000,
        random_state=42
    )
    labels = kmeans.fit_predict(reduced_embeddings)

    # Group emails by cluster
    clusters = defaultdict(list)
    for idx, label in enumerate(labels):
        clusters[label].append(idx)

    return clusters
```

### TF-IDF Labeling (Multilingual)

```python
from sklearn.feature_extraction.text import TfidfVectorizer

# Comprehensive stop words (EN/DE/NO)
STOP_WORDS = [
    # German
    'ist', 'im', 'haben', 'ihre', 'ihrer', 'zur', 'zum', 'werden', 'sind',
    'dass', 'alle', 'diese', 'über', 'nach', 'noch', 'auch', 'bei',
    # English
    'is', 'are', 'was', 'been', 'has', 'had', 'were', 'please', 'ok',
    'more', 'less', 'very', 'much', 'such', 'just', 'than', 'only',
    # Norwegian/Danish
    'det', 'jeg', 'vi', 'har', 'til', 'hei', 'og', 'med', 'denne', 'fra',
    # Email junk
    'http', 'https', 'www', 'com', 'org', 'net', 'html', 'click',
    'recipient', 'unsubscribe', 'privacy', 'policy',
    # Company terms
    'inc', 'gmbh', 'sarl', 'ltd', 'ag', 'aps', 'as'
]

def extract_keywords(cluster: Cluster, top_n: int = 5) -> List[str]:
    """
    Extract top N keywords per cluster using TF-IDF
    """
    vectorizer = TfidfVectorizer(
        max_features=100,
        stop_words=STOP_WORDS,
        ngram_range=(1, 2),  # Unigrams and bigrams
        min_df=2  # Keyword must appear in at least 2 docs
    )

    cluster_texts = [email.body for email in cluster.emails]
    tfidf_matrix = vectorizer.fit_transform(cluster_texts)

    # Get top keywords
    feature_names = vectorizer.get_feature_names_out()
    scores = tfidf_matrix.sum(axis=0).A1
    top_indices = scores.argsort()[-top_n:][::-1]

    return [feature_names[i] for i in top_indices]
```

### LLM Classification

```python
def classify_cluster(cluster: Cluster) -> str:
    """
    Use Qwen3 to classify cluster by TYPE (not company)
    """
    sample_emails = cluster.emails[:5]  # Top 5 representative emails
    sample_text = "\n\n---\n\n".join([e.body[:300] for e in sample_emails])

    prompt = f"""
Classify this email cluster by TYPE (not sender):

Types:
- newsletter: Regular updates, announcements
- tracking: Shipping, delivery confirmations
- invoice: Bills, receipts, payment confirmations
- personal: Direct correspondence
- notification: System alerts, social media
- marketing: Promotional content
- other: Anything else

Sample emails:
{sample_text}

Return ONLY the type name.
"""

    response = ollama_client.generate(
        model="qwen3:0.6b",
        prompt=prompt,
        options={"temperature": 0.1}  # Deterministic
    )

    return response['response'].strip().lower()
```

### Export to Obsidian

```python
def export_to_obsidian(clusters: List[Cluster], output_dir: str):
    """
    Export curated emails as markdown notes
    Only exports clusters marked as KEEP
    """
    for cluster in clusters:
        if cluster.classification not in ['personal', 'newsletter']:
            continue  # Skip tracking/marketing

        # Create note per cluster
        note_path = f"{output_dir}/{cluster.id}-{slugify(cluster.keywords[0])}.md"

        content = f"""---
type: email-cluster
classification: {cluster.classification}
keywords: {', '.join(cluster.keywords)}
email_count: {len(cluster.emails)}
date_range: {cluster.date_range}
---

# {cluster.keywords[0].title()} Emails

**Classification**: {cluster.classification}
**Keywords**: {', '.join(cluster.keywords)}
**Emails**: {len(cluster.emails)}

## Representative Emails

"""

        # Add top 3 emails
        for email in cluster.emails[:3]:
            content += f"""
### {email.subject}
**From**: {email.sender}
**Date**: {email.date}

{email.body[:500]}...

---
"""

        write_file(note_path, content)
```

### Weaviate Schema (The Lethe)

```python
schema = {
    "class": "TheLethe",
    "description": "Email archive with semantic embeddings",
    "vectorizer": "none",
    "properties": [
        {"name": "subject", "dataType": ["text"]},
        {"name": "body", "dataType": ["text"]},
        {"name": "sender", "dataType": ["text"]},
        {"name": "date", "dataType": ["date"]},
        {"name": "clusterId", "dataType": ["int"]},
        {"name": "clusterKeywords", "dataType": ["text[]"]},
        {"name": "classification", "dataType": ["text"]},
        {"name": "ingestedAt", "dataType": ["date"]}
    ]
}
```

### Performance Metrics (From email-hygiene)

- **Pre-cleaning**: ~1 hour for 26k emails → 19k clean (74% quality)
- **Embedding**: 1-2 sec/email → 10-12 hours for 19k emails
- **Clustering**: Minutes for 19k emails
- **TF-IDF**: Seconds
- **LLM classification**: 5-10 sec/cluster → 30-60 min for 400 clusters

**Total pipeline**: ~12-15 hours for 19k emails on Pi 5

### Dependencies
- Ollama with qwen3-embedding:0.6b and qwen3:0.6b
- Weaviate (The Lethe collection)
- Python: BeautifulSoup4, scikit-learn, email, mailbox
- Pre-cleaned TSV or raw email directory

## Affected Components
- **Aletheia**: Email cleaning and ingestion
- **Alexandria**: The Lethe (email archive storage)
- **Obsidian Vault**: Export destination for curated emails

## Priority
**Medium** - Important for users with large email archives, not blocking MVP

## Estimate
13 story points (8-10 days)

## Linear Labels
`phase-0`, `ingestion`, `email`, `aletheia`, `alexandria`

## Related Stories
- Story 000: Obsidian Vault Ingestion (similar embedding pipeline)
- Story 002: Structured Metadata Synthesis (can analyze email clusters)
- Story 010: Autonomous Pattern Detection (can find patterns in emails)

## References
- Implementation: `email-hygiene-pipeline/cleaner/main.py`
- Cleaning logic: `email-hygiene-pipeline/README.md:63-80`
- Clustering strategy: MiniBatchKMeans, ~1 cluster per 50 emails
- Performance baseline: 19k emails in 10-12 hours
