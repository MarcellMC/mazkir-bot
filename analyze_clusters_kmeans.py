"""Analyze clusters using K-means to identify distinct topics."""
import numpy as np
from datetime import datetime
from sklearn.cluster import KMeans
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


def apply_kmeans_clustering(embeddings, n_clusters=8):
    """Apply K-means clustering to identify groups."""
    print(f"\nApplying K-Means clustering with {n_clusters} clusters...")

    # Use original high-dim embeddings for clustering (better results)
    clusterer = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
    labels = clusterer.fit_predict(embeddings)

    # Reduce to 2D for visualization context
    print("Reducing dimensions for visualization...")
    reducer = UMAP(
        n_neighbors=15,
        min_dist=0.1,
        n_components=2,
        metric='cosine',
        random_state=42,
        verbose=False
    )
    embedding_2d = reducer.fit_transform(embeddings)

    unique_labels = set(labels)
    print(f"✓ Created {len(unique_labels)} clusters")

    return labels, embedding_2d, clusterer


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
    max_messages = 15
    if len(cluster_messages) > max_messages:
        # Take a diverse sample across time
        step = len(cluster_messages) // max_messages
        sample = cluster_messages[::step][:max_messages]
    else:
        sample = cluster_messages

    # Prepare messages for LLM
    message_texts = [msg['text'] for msg in sample]

    prompt = f"""Analyze this cluster of {len(cluster_messages)} messages.

Messages:
{chr(10).join(f"{i+1}. {text}" for i, text in enumerate(message_texts))}

Provide:
1. Main topic/theme (3-5 words max)
2. Description (1-2 sentences)
3. Key characteristics

Be concise and specific."""

    llm = LLMService(provider="ollama")

    try:
        analysis = await llm.generate(prompt)
        return analysis
    except Exception as e:
        print(f"Error analyzing cluster {cluster_id}: {e}")
        return "Unable to analyze"


def calculate_cluster_stats(clusters):
    """Calculate statistics for each cluster."""
    stats = {}

    for label, messages in clusters.items():
        dates = [msg['date'] for msg in messages]
        texts = [msg['text'] for msg in messages]
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
    print("K-Means Cluster Analysis - Identifying Topics")
    print("=" * 70)

    # Load data
    embeddings, texts, dates = load_data()
    print(f"Loaded {len(embeddings)} messages")

    # Determine number of clusters (heuristic: ~20-30 messages per cluster)
    n_clusters = max(5, min(10, len(embeddings) // 25))
    print(f"Target: {n_clusters} clusters (~{len(embeddings)//n_clusters} messages each)")

    # Apply clustering
    labels, embedding_2d, clusterer = apply_kmeans_clustering(embeddings, n_clusters=n_clusters)

    # Group messages by cluster
    clusters = group_messages_by_cluster(labels, texts, dates)

    # Calculate statistics
    stats = calculate_cluster_stats(clusters)

    # Analyze each cluster
    print("\n" + "=" * 70)
    print("Cluster Analysis Results")
    print("=" * 70)

    cluster_analyses = {}
    cluster_topics = {}

    for cluster_id in sorted(clusters.keys(), key=lambda x: -len(clusters[x])):
        messages = clusters[cluster_id]
        cluster_stats = stats[cluster_id]

        print(f"\n{'=' * 70}")
        print(f"CLUSTER {cluster_id} - {cluster_stats['size']} messages")
        print(f"{'=' * 70}")
        print(f"Date range: {cluster_stats['date_range'][0].strftime('%Y-%m-%d')} → {cluster_stats['date_range'][1].strftime('%Y-%m-%d')}")
        print(f"Years: {dict(cluster_stats['year_distribution'])}")

        # Sample messages
        print(f"\nSample messages (showing 5 of {len(messages)}):")
        for i, msg in enumerate(messages[:5], 1):
            text_preview = msg['text'][:120] + "..." if len(msg['text']) > 120 else msg['text']
            # Clean up newlines for display
            text_preview = text_preview.replace('\n', ' ').strip()
            print(f"  {i}. {text_preview}")

        # LLM analysis
        print(f"\n🤖 Analyzing with LLM...")
        analysis = await analyze_cluster_with_llm(messages, cluster_id)
        cluster_analyses[cluster_id] = analysis

        # Extract topic (first line of analysis)
        topic_line = analysis.split('\n')[0]
        cluster_topics[cluster_id] = topic_line

        print(f"\n📊 Analysis:")
        print(analysis)

    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Total messages: {len(embeddings)}")
    print(f"Clusters identified: {len(clusters)}")
    print(f"\nTopics discovered:")
    for cluster_id in sorted(clusters.keys(), key=lambda x: -len(clusters[x])):
        topic = cluster_topics.get(cluster_id, "Unknown")
        size = len(clusters[cluster_id])
        print(f"  • Cluster {cluster_id} ({size:3d} msgs): {topic}")

    # Save detailed analysis
    print("\n" + "=" * 70)
    print("Saving detailed analysis...")

    with open('cluster_analysis_kmeans.txt', 'w', encoding='utf-8') as f:
        f.write("=" * 70 + "\n")
        f.write("Message Cluster Analysis (K-Means)\n")
        f.write("=" * 70 + "\n\n")
        f.write(f"Total messages: {len(embeddings)}\n")
        f.write(f"Number of clusters: {len(clusters)}\n\n")

        for cluster_id in sorted(clusters.keys(), key=lambda x: -len(clusters[x])):
            f.write(f"\n{'=' * 70}\n")
            f.write(f"CLUSTER {cluster_id} - {len(clusters[cluster_id])} messages\n")
            f.write(f"{'=' * 70}\n\n")
            f.write(f"Topic: {cluster_topics.get(cluster_id, 'Unknown')}\n\n")
            f.write(f"Analysis:\n{cluster_analyses[cluster_id]}\n\n")
            f.write(f"Date range: {stats[cluster_id]['date_range'][0]} to {stats[cluster_id]['date_range'][1]}\n")
            f.write(f"Year distribution: {dict(stats[cluster_id]['year_distribution'])}\n\n")
            f.write(f"All messages:\n")
            for i, msg in enumerate(clusters[cluster_id], 1):
                f.write(f"{i}. [{msg['date'].strftime('%Y-%m-%d')}] {msg['text']}\n")
            f.write("\n")

    print("✓ Saved to 'cluster_analysis_kmeans.txt'")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
