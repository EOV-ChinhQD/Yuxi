from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

import nltk
from nltk.tokenize import sent_tokenize
from sklearn.cluster import AgglomerativeClustering
from sklearn.metrics import silhouette_score

_punkt_checked = False


def _ensure_punkt_tab() -> None:
    """Check the NLTK punkt_tab resource when using the clause ability for the first time, and give an actionable error if it is missing."""
    global _punkt_checked
    if _punkt_checked:
        return

    try:
        nltk.data.find("tokenizers/punkt_tab")
    except LookupError as e:
        raise RuntimeError("Thiếu tài nguyên NLTK punkt_tab. Vui lòng chạy: python -m nltk.downloader punkt_tab trước") from e

    _punkt_checked = True


def split_sentences_chinese(text: str) -> list[str]:
    """
    Use regular surface expressions to split Chinese text points into sentences.

    logic:
    - Matches Chinese periods, exclamation points, and question marks (.!?) as separation points.
    - Use forward/Reverse pre-lookup handles quotes: Make sure that if punctuation is followed by a quote (”’"), the quotation mark will be retained at the end of the current sentence instead of being split into the next sentence.
    - Returns a list of non-empty sentences with spaces removed from both ends.
    """
    pattern = r'(?<=[。！？][”’"])|(?<=[。！？])(?![”’"])'
    sentences = re.split(pattern, text)
    return [s.strip() for s in sentences if s.strip()]


def split_mixed_sentences(text: str) -> list[str]:
    """
    Processing English mixed text ofpoint sentence logic, supports different ofpoint sentence strategies according to physical paragraph point.

    This function uses the “divide and conquer” strategy to handle complex mixed text:
    1. **physical chunking**: First split the original text by newline characters (`\\n+`) into physical chunks, ensuring structure is not destroyed.
    2. **Language detection and distribution**：
       - **English/mixed path**: If the paragraph contains English letters (`[A-Za-z]`), it is regarded as English mixed text.
         Call NLTK of `sent_tokenize` for processing. NLTK can better handle complex situations such as English abbreviations and periods.
       - **Chinese path**: If the paragraph does not contain letters, it is regarded as pure Chinese text and is called `split_sentences_chinese`。
         This method accurately matches Chinese punctuation and subsequent quotation marks through regular expressions.
       - **Cover-up plan**: If the above method does not produce results, use a simple of regular surface expression to force point cuts according to Chinese punctuation.
    3. **Cleaning and filtering**: Summarize all clauses, remove blank characters at both ends, and filter out empty character strings.

    Args:
        text: The original character string to be pointed at.

    Returns:
        List[str]: Split sentence list.
    """
    _ensure_punkt_tab()

    chunks = re.split(r"(\n+)", text)
    sentences = []

    for ch in chunks:
        if not ch.strip():
            continue
        if re.search(r"[A-Za-z]", ch):
            parts = sent_tokenize(ch)
            sentences.extend([p.strip() for p in parts if p.strip()])
        else:
            sents = split_sentences_chinese(ch)
            if sents:
                sentences.extend([s.strip() for s in sents if s.strip()])
            else:
                parts = re.split(r"(?<=[。！？])", ch)
                sentences.extend([p.strip() for p in parts if p.strip()])
    return sentences


def find_best_num_clusters(embeddings: Any, min_clusters: int = 2, max_clusters: int = 10) -> int:
    """
    Use silhouette coefficient to select the optimal number of clusters. Let the semantics of each individual point segment be focused and the boundaries between point segments clear.

    logic:
    - Iterate over the number of possible clusters (from min_clusters to max_clusters).
    - For each number of clusters, use `AgglomerativeClustering` Perform clustering.
    - Calculate Silhouette Score.
    - The number of clusters with the highest silhouette coefficient is selected as the optimal number of clusters.
    - If the number of clusters is 1 or less, 1 is returned directly.

    Args:
        embeddings: ofvector number data to be clustered (all sentences of embedding vector column surface).
        min_clusters: The lower limit of the optimal number of clusters for searchof, default is 2.
        max_clusters: The upper limit of the number of optimal clusters for searchof, default is 10.

    Returns:
        int: The number of clusters with the best silhouette coefficient performance.
    """
    if len(embeddings) <= min_clusters:
        return len(embeddings)

    best_score = -1
    best_k = min_clusters

    limit_k = min(max_clusters, len(embeddings))
    for k in range(min_clusters, limit_k + 1):
        labels = AgglomerativeClustering(n_clusters=k, metric="cosine", linkage="average").fit_predict(embeddings)
        if len(set(labels)) <= 1:
            continue
        score = silhouette_score(embeddings, labels, metric="cosine")
        if score > best_score:
            best_score = score
            best_k = k

    return best_k


def semantic_chunking_with_auto_clusters(
    text: str,
    embed_fn: Callable[[list[str]], Any] | None,
    token_count_fn: Callable[[str], int],
    max_chunk_size: int = 512,
) -> list[str]:
    """
    Perform semantic point cutting on the incoming of text, and the optimal number of of aggregations will be automatically selected during the process.

    logic:
    - First distribute the sentences in the text by language, English/Mixed text uses NLTK's sent_tokenize, and Chinese text uses split_sentences_chinese.
    - Embedding vectorization is performed on each sentence.
    - Determine the optimal number of clusters (based on silhouette coefficient).
    - After clustering the sentences, traverse them in the order of the original text: when the clustering label changes or reaches the upper limit of length, it is divided into continuous blocks.
    - If the embedding model is missing, it will fall back to the original segmentation method.
    """
    sentences = split_mixed_sentences(text)
    if len(sentences) < 2:
        return [text.strip()]

    # Count the number of tokens for each sentence
    sentence_token_counts = [token_count_fn(s) for s in sentences]
    total_tokens = sum(sentence_token_counts)

    # If no vectorization function is provided, or the whole is not too long, simply merge/return directly.
    if embed_fn is None or total_tokens <= max_chunk_size:
        chunks = []
        current_chunk = ""
        current_chunk_tokens = 0
        for s, cnt in zip(sentences, sentence_token_counts):
            if current_chunk_tokens + cnt > max_chunk_size and current_chunk:
                chunks.append(current_chunk.strip())
                current_chunk = s
                current_chunk_tokens = cnt
            else:
                current_chunk += s
                current_chunk_tokens += cnt
        if current_chunk:
            chunks.append(current_chunk.strip())
        return chunks

    # Vectorize each sentence to get their embedding vectors
    embeddings = embed_fn(sentences)

    # Determine the appropriate number of aggregations: If it is too long, round up according to the upper limit to avoid cutting an extra piece when dividing.
    best_k = (total_tokens + max_chunk_size - 1) // max_chunk_size
    best_k = min(best_k, len(sentences))

    # Cluster sentences according to the specified number of clusters, similarity judgment method, and linkage method.
    # labels is a list of cluster labels for each sentence (such as [0,0,1,2,2]). Subsequently, continuous blocks will be divided at the label changes in the order of the original text.
    labels = AgglomerativeClustering(n_clusters=best_k, metric="cosine", linkage="average").fit_predict(embeddings)

    chunks = []
    current_chunk = ""
    current_chunk_tokens = 0
    current_label = labels[0]

    for sentence, label, token_count in zip(sentences, labels, sentence_token_counts):
        if label != current_label or current_chunk_tokens + token_count > max_chunk_size:
            if current_chunk.strip():
                chunks.append(current_chunk.strip())
            current_chunk = sentence
            current_chunk_tokens = token_count
            current_label = label
        else:
            current_chunk += sentence
            current_chunk_tokens += token_count

    if current_chunk.strip():
        chunks.append(current_chunk.strip())

    return chunks
