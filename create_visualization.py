"""Create interactive 2D visualization of message embeddings."""
import numpy as np
import plotly.graph_objects as go
from datetime import datetime
from umap import UMAP
from sklearn.manifold import TSNE
import plotly.express as px


def load_data():
    """Load embeddings data from file."""
    print("Loading embeddings data...")
    data = np.load('embeddings_data.npz', allow_pickle=True)

    embeddings = data['embeddings']
    texts = data['texts']
    dates = [datetime.fromisoformat(d) for d in data['dates']]

    print(f"Loaded {len(embeddings)} embeddings")
    return embeddings, texts, dates


def apply_umap(embeddings, n_neighbors=15, min_dist=0.1):
    """Apply UMAP dimensionality reduction."""
    print(f"\nApplying UMAP (n_neighbors={n_neighbors}, min_dist={min_dist})...")
    print("This may take a minute...")

    reducer = UMAP(
        n_neighbors=n_neighbors,
        min_dist=min_dist,
        n_components=2,
        metric='cosine',
        random_state=42,
        verbose=True
    )

    embedding_2d = reducer.fit_transform(embeddings)
    print(f"✓ Reduced to 2D: {embedding_2d.shape}")

    return embedding_2d


def apply_tsne(embeddings, perplexity=30):
    """Apply t-SNE dimensionality reduction."""
    print(f"\nApplying t-SNE (perplexity={perplexity})...")
    print("This may take a few minutes...")

    tsne = TSNE(
        n_components=2,
        perplexity=perplexity,
        random_state=42,
        verbose=1
    )

    embedding_2d = tsne.fit_transform(embeddings)
    print(f"✓ Reduced to 2D: {embedding_2d.shape}")

    return embedding_2d


def assign_colors_by_year(dates):
    """Assign colors based on year."""
    years = [d.year for d in dates]
    unique_years = sorted(set(years))

    # Create color mapping
    colors = px.colors.qualitative.Set3
    if len(unique_years) > len(colors):
        colors = px.colors.sample_colorscale("Viridis", len(unique_years))

    year_to_color = {year: colors[i % len(colors)] for i, year in enumerate(unique_years)}
    point_colors = [year_to_color[year] for year in years]

    return point_colors, years, unique_years, year_to_color


def create_interactive_plot(embedding_2d, texts, dates, method='UMAP'):
    """Create interactive Plotly visualization."""
    print(f"\nCreating interactive {method} visualization...")

    # Assign colors by year
    point_colors, years, unique_years, year_to_color = assign_colors_by_year(dates)

    # Truncate long texts for hover
    hover_texts = [
        f"<b>{text[:200]}</b><br>"
        f"Date: {date.strftime('%Y-%m-%d %H:%M')}<br>"
        f"Year: {date.year}"
        for text, date in zip(texts, dates)
    ]

    # Create scatter plot
    fig = go.Figure()

    # Add trace for each year
    for year in unique_years:
        mask = np.array(years) == year
        fig.add_trace(go.Scatter(
            x=embedding_2d[mask, 0],
            y=embedding_2d[mask, 1],
            mode='markers',
            name=str(year),
            marker=dict(
                size=8,
                color=year_to_color[year],
                line=dict(width=0.5, color='white'),
                opacity=0.7
            ),
            text=[hover_texts[i] for i, m in enumerate(mask) if m],
            hovertemplate='%{text}<extra></extra>',
        ))

    # Update layout
    fig.update_layout(
        title=dict(
            text=f'{method} Visualization of Message Embeddings<br>'
                 f'<sub>{len(texts)} messages from {min(dates).year} to {max(dates).year}</sub>',
            x=0.5,
            xanchor='center'
        ),
        xaxis_title=f'{method} Dimension 1',
        yaxis_title=f'{method} Dimension 2',
        hovermode='closest',
        width=1200,
        height=800,
        template='plotly_white',
        showlegend=True,
        legend=dict(
            title='Year',
            yanchor="top",
            y=0.99,
            xanchor="left",
            x=0.01
        )
    )

    return fig


def main():
    """Main function."""
    print("=" * 60)
    print("Message Embeddings Visualization")
    print("=" * 60)

    # Load data
    embeddings, texts, dates = load_data()

    # Apply UMAP (faster and often better for high-dim data)
    embedding_2d_umap = apply_umap(embeddings)

    # Create visualization
    fig_umap = create_interactive_plot(embedding_2d_umap, texts, dates, method='UMAP')

    # Save as HTML
    output_file = 'message_embeddings_visualization.html'
    print(f"\nSaving visualization to '{output_file}'...")
    fig_umap.write_html(output_file)

    print("\n" + "=" * 60)
    print(f"✓ Visualization complete!")
    print(f"✓ Open '{output_file}' in your browser to explore")
    print("=" * 60)
    print("\nVisualization features:")
    print("  • Hover over points to see message text and date")
    print("  • Click legend items to show/hide years")
    print("  • Zoom and pan to explore clusters")
    print("  • Points close together = semantically similar messages")

    # Optional: Also create t-SNE visualization
    print("\n" + "=" * 60)
    print("Would you like to also create a t-SNE visualization?")
    print("(UMAP is usually better, but t-SNE can reveal different patterns)")
    print("Note: t-SNE is slower and may take 2-5 minutes")
    print("=" * 60)


if __name__ == "__main__":
    main()
