"""Analyze clusters in the message embeddings to identify topics."""
import numpy as np
from datetime import datetime
from sklearn.cluster import DBSCAN, KMeans
from collections import Counter
import asyncio

from umap import UMAP
from src.services.llm_service import LLMService


def load_data():
    """Load embeddings and 2D projections."""
    print("Loading data...")
    data = np.load('embeddings_data.npz', allow_pickle=True)

    embeddings = data['embeddings']
    texts = data['texts']
    dates = [datetime.fromisoformat(d) for d in data['dates']]

    return embeddings, texts, dates


def apply_clustering(embeddings, method='dbscan', eps=0.5, min_samples=3):
    """Apply clustering algorithm to identify groups."""
    print(f"\nApplying {method.upper()} clustering...")

    # First reduce to 2D with UMAP for clustering
    print("Reducing dimensions for clustering...")
    reducer = UMAP(
        n_neighbors=15,
        min_dist=0.1,
        n_components=2,
        metric='cosine',
        random_state=42,
        verbose=False
    )
    embedding_2d = reducer.fit_transform(embeddings)

    if method == 'dbscan':
        clusterer = DBSCAN(eps=eps, min_samples=min_samples)
        labels = clusterer.fit_predict(embedding_2d)
    elif method == 'kmeans':
        # Determine optimal number of clusters (heuristic)
        n_clusters = min(10, max(3, len(embeddings) // 20))
        clusterer = KMeans(n_clusters=n_clusters, random_state=42)
        labels = clusterer.fit_predict(embedding_2d)
    else:
        raise ValueError(f"Unknown method: {method}")

    # Count clusters
    unique_labels = set(labels)
    n_clusters = len(unique_labels) - (1 if -1 in labels else 0)
    n_noise = list(labels).count(-1) if -1 in labels else 0

    print(f"✓ Found {n_clusters} clusters")
    if n_noise > 0:
        print(f"  ({n_noise} noise points)")

    return labels, embedding_2d


def group_messages_by_cluster(labels, texts, dates):
    """Group messages by their cluster labels."""
    clusters = {}

    for label, text, date in zip(labels, texts, dates):
        if label not in clusters:
            clusters[label] = []
        clusters[label].append({
            'text': text,
            'date': date
        })

    # Sort clusters by size (descending)
    sorted_clusters = dict(sorted(
        clusters.items(),
        key=lambda x: len(x[1]),
        reverse=True
    ))

    return sorted_clusters


async def analyze_cluster_with_llm(cluster_messages, cluster_id):
    """Use LLM to analyze what a cluster represents."""
    # Sample messages if too many
    max_messages = 20
    if len(cluster_messages) > max_messages:
        # Take a diverse sample (first, middle, last messages)
        step = len(cluster_messages) // max_messages
        sample = cluster_messages[::step][:max_messages]
    else:
        sample = cluster_messages

    # Prepare messages for LLM
    message_texts = [msg['text'] for msg in sample]

    prompt = f"""Analyze this cluster of {len(cluster_messages)} messages and identify:

1. Main topic/theme (in 2-4 words)
2. Brief description (1-2 sentences)
3. Key patterns or common elements

Messages:
{chr(10).join(f"- {text}" for text in message_texts[:15])}

Provide a concise analysis."""

    llm = LLMService(provider="ollama")

    try:
        analysis = await llm.generate(prompt)
        return analysis
    except Exception as e:
        print(f"Error analyzing cluster {cluster_id}: {e}")
        return "Unable to analyze this cluster"


def calculate_cluster_stats(clusters):
    """Calculate statistics for each cluster."""
    stats = {}

    for label, messages in clusters.items():
        dates = [msg['date'] for msg in messages]
        texts = [msg['text'] for msg in messages]

        # Calculate text length stats
        text_lengths = [len(text) for text in texts]

        stats[label] = {
            'size': len(messages),
            'date_range': (min(dates), max(dates)),
            'avg_text_length': np.mean(text_lengths),
            'year_distribution': Counter([d.year for d in dates])
        }

    return stats


async def main():
    """Main analysis function."""
    print("=" * 70)
    print("Cluster Analysis - Identifying Topics in Your Messages")
    print("=" * 70)

    # Load data
    embeddings, texts, dates = load_data()
    print(f"Loaded {len(embeddings)} messages")

    # Apply clustering
    labels, embedding_2d = apply_clustering(embeddings, method='dbscan', eps=0.8, min_samples=4)

    # Group messages by cluster
    clusters = group_messages_by_cluster(labels, texts, dates)

    # Calculate statistics
    stats = calculate_cluster_stats(clusters)

    # Analyze each cluster
    print("\n" + "=" * 70)
    print("Cluster Analysis Results")
    print("=" * 70)

    cluster_analyses = {}

    for label in sorted(clusters.keys(), key=lambda x: (x == -1, -len(clusters[x]))):
        if label == -1:
            cluster_name = "Noise/Outliers"
            print(f"\n{'=' * 70}")
            print(f"Cluster: {cluster_name}")
            print(f"Size: {stats[label]['size']} messages")
            print(f"These are isolated messages that don't fit into clear topics")
            continue

        cluster_name = f"Cluster {label}"
        messages = clusters[label]
        cluster_stats = stats[label]

        print(f"\n{'=' * 70}")
        print(f"{cluster_name} ({cluster_stats['size']} messages)")
        print(f"{'=' * 70}")
        print(f"Date range: {cluster_stats['date_range'][0].strftime('%Y-%m-%d')} to {cluster_stats['date_range'][1].strftime('%Y-%m-%d')}")
        print(f"Year distribution: {dict(cluster_stats['year_distribution'])}")
        print(f"Avg message length: {cluster_stats['avg_text_length']:.0f} characters")

        # Sample messages
        print(f"\nSample messages:")
        for i, msg in enumerate(messages[:5], 1):
            text_preview = msg['text'][:100] + "..." if len(msg['text']) > 100 else msg['text']
            print(f"  {i}. {text_preview}")

        # LLM analysis
        print(f"\nAnalyzing topic with LLM...")
        analysis = await analyze_cluster_with_llm(messages, label)
        cluster_analyses[label] = analysis

        print(f"\nTopic Analysis:")
        print(f"{analysis}")

    # Summary
    print("\n" + "=" * 70)
    print("Summary")
    print("=" * 70)
    print(f"Total messages: {len(embeddings)}")
    print(f"Identified clusters: {len([k for k in clusters.keys() if k != -1])}")

    if -1 in clusters:
        print(f"Outlier messages: {len(clusters[-1])}")

    print("\nCluster sizes:")
    for label in sorted(clusters.keys(), key=lambda x: (x == -1, -len(clusters[x]))):
        if label == -1:
            print(f"  Outliers: {len(clusters[label])} messages")
        else:
            print(f"  Cluster {label}: {len(clusters[label])} messages")

    # Save analysis
    print("\n" + "=" * 70)
    print("Saving detailed analysis to 'cluster_analysis.txt'...")

    with open('cluster_analysis.txt', 'w') as f:
        f.write("=" * 70 + "\n")
        f.write("Message Cluster Analysis\n")
        f.write("=" * 70 + "\n\n")

        for label in sorted(clusters.keys(), key=lambda x: (x == -1, -len(clusters[x]))):
            if label == -1:
                continue

            f.write(f"\nCluster {label} ({len(clusters[label])} messages)\n")
            f.write("-" * 70 + "\n")
            f.write(f"\nTopic Analysis:\n{cluster_analyses[label]}\n")
            f.write(f"\nAll messages in this cluster:\n")
            for i, msg in enumerate(clusters[label], 1):
                f.write(f"{i}. [{msg['date'].strftime('%Y-%m-%d')}] {msg['text']}\n")
            f.write("\n" + "=" * 70 + "\n")

    print("✓ Detailed analysis saved to 'cluster_analysis.txt'")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
