import math
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from wordcloud import WordCloud
import seaborn as sns

def plot_percentage_matrix_focus_category(
        data,
        title, target_index = 0, label_index = 1,
        target_color = "#4CAF50", others_color = "#E0E0E0"
    ):
    n = len(data)
    cols = min(3, n)
    rows = math.ceil(n / cols)

    fig, axes = plt.subplots(rows, cols, figsize=(3*cols, 3*rows))
    axes = axes.flatten() if n > 1 else [axes]

    for i, d in enumerate(data):
        target = d[target_index]
        category = d[label_index]

        total = sum([
            d[i] for i in range(len(d))
                if i != label_index
        ])
        ax = axes[i]

        pct = target / total if total > 0 else 0

        ax.pie(
            [pct, 1 - pct],
            colors=[target_color, others_color],
            startangle=90,
            counterclock=False,
            wedgeprops={'linewidth': 1, 'edgecolor': 'white'}
        )

        ax.set_title(f"{category} ({pct*100:.1f}%)", fontsize=12)

        ax.set_aspect('equal')

    for j in range(i+1, len(axes)):
        axes[j].axis("off")

    fig.suptitle(title, fontsize=16, fontweight="bold", y=1.02)
    plt.tight_layout()
    plt.show()

def plot_percentage_categories(
        data,
        title,
        target_index=0,
        label_index=1
    ):

    wedges, texts, autotexts = plt.pie(
        x=data[:, target_index],
        labels=None,
        startangle=90,
        counterclock=False,
        wedgeprops={'linewidth': 1, 'edgecolor': 'white'},
        autopct='%1.1f%%'
    )

    plt.legend(
        wedges,
        data[:, label_index],
        title="Categories",
        loc="center left",
        bbox_to_anchor=(1, 0, 0.5, 1)
    )

    plt.axis('equal')

    plt.suptitle(title, fontsize=16, fontweight="bold", y=1.02)
    plt.tight_layout()
    plt.show()

def plot_percentage_categories_bar(data, title, target_index=0, label_index=1, top = 10):
    sorted_indices = np.argsort(data[:, target_index].astype(float))[::-1]
    top_indices = sorted_indices[:top]
    top_data = data[top_indices]

    values = top_data[:, target_index].astype(float)
    labels = top_data[:, label_index]

    total = np.sum(values)
    percentages = values / total * 100

    fig, ax = plt.subplots(figsize=(8,6))
    bars = ax.bar(labels, percentages, color='skyblue', edgecolor='black')

    for bar, pct in zip(bars, percentages):
        height = bar.get_height()
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            height + 1,
            f'{pct:.1f}%',
            ha='center',
            va='bottom',
            fontsize=10
        )

    ax.set_title(title, fontsize=16, fontweight='bold')
    ax.set_ylabel('Percentage (%)')
    ax.set_ylim(0, max(percentages) * 1.15)
    plt.xticks(rotation=45, ha='right')
    plt.tight_layout()
    plt.show()

def plot_percentage_categories_bar_by_group(data, title):
    df = pd.DataFrame(data, columns=["category", "key", "count"])
    df["count"] = df["count"].astype(int)

    categories = df["category"].unique()
    n = len(categories)
    cols = min(3, n)
    rows = math.ceil(n / cols)

    fig, axes = plt.subplots(rows, cols, figsize=(6*cols, 4*rows))
    axes = axes.flatten() if n > 1 else [axes]

    for i, cat in enumerate(categories):
        subdf = df[df["category"] == cat]
        ax = axes[i]
        ax.barh(subdf["key"], subdf["count"])
        ax.set_title(cat, fontsize=12)
        ax.set_xlabel("Cantidad")
        ax.set_ylabel("Campo")
        ax.invert_yaxis()

    for j in range(i+1, len(axes)):
        axes[j].axis("off")

    fig.suptitle(title, fontsize=16, fontweight="bold", y=1.02)
    plt.tight_layout()
    plt.show()

def plot_absolute_categories_bar(data, title, target_index=0, label_index=1):
    sorted_indices = np.argsort(data[:, target_index].astype(float))[::-1]
    top_indices = sorted_indices[:10]
    top_data = data[top_indices]

    values = top_data[:, target_index].astype(float)
    labels = top_data[:, label_index]

    total = np.sum(values)
    percentages = values / total * 100

    fig, ax = plt.subplots(figsize=(8,6))
    bars = ax.bar(labels, values, color='skyblue', edgecolor='black')

    for bar, pct in zip(bars, percentages):
        height = bar.get_height()
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            height + 1,
            f'{pct:.1f}%',
            ha='center',
            va='bottom',
            fontsize=10
        )

    ax.set_title(title, fontsize=16, fontweight='bold')
    ax.set_ylabel('Percentage (%)')
    ax.set_ylim(0, max(percentages) * 1.15)
    plt.xticks(rotation=45, ha='right')
    plt.tight_layout()
    plt.show()

def display_histogram(
        data,
        title,
        bins = 10,
        target_index=0
    ):

    plt.hist(data[:, target_index], bins=bins, edgecolor='black')

    plt.suptitle(title, fontsize=16, fontweight="bold", y=1.02)
    plt.tight_layout()
    plt.show()

def plot_boxplots_by_category(data, title,samples=500):
    df = pd.DataFrame(data, columns=["category", "min", "max", "mean", "std"])
    df = df.dropna(subset=["category"])

    categories = df["category"].unique()
    n = len(categories)
    cols = min(3, n)
    rows = math.ceil(n / cols)

    fig, axes = plt.subplots(rows, cols, figsize=(6*cols, 4*rows))
    axes = axes.flatten() if n > 1 else [axes]

    for i, cat in enumerate(categories):
        row = df[df["category"] == cat].iloc[0]
        mean, std, vmin, vmax = row["mean"], row["std"], row["min"], row["max"]
        data_points = np.random.normal(mean, std if std > 0 else 0.1, samples)
        data_points = np.clip(data_points, vmin, vmax)

        ax = axes[i]
        ax.boxplot(data_points, vert=True, patch_artist=True)
        ax.set_title(cat, fontsize=11)
        ax.set_ylabel("Value")

    for j in range(i+1, len(axes)):
        axes[j].axis("off")

    fig.suptitle(title, fontsize=16, fontweight="bold", y=1.02)
    plt.tight_layout()
    plt.show()

def plot_boxplots_by_category(data, title,samples=500):
    df = pd.DataFrame(data, columns=["category", "min", "max", "mean", "std"])
    df = df.dropna(subset=["category"])

    categories = df["category"].unique()
    n = len(categories)
    cols = min(3, n)
    rows = math.ceil(n / cols)

    fig, axes = plt.subplots(rows, cols, figsize=(6*cols, 4*rows))
    axes = axes.flatten() if n > 1 else [axes]

    for i, cat in enumerate(categories):
        row = df[df["category"] == cat].iloc[0]
        mean, std, vmin, vmax = row["mean"], row["std"], row["min"], row["max"]
        data_points = np.random.normal(mean, std if std > 0 else 0.1, samples)
        data_points = np.clip(data_points, vmin, vmax)

        ax = axes[i]
        ax.boxplot(data_points, vert=True, patch_artist=True)
        ax.set_title(cat, fontsize=11)
        ax.set_ylabel("Value")

    for j in range(i+1, len(axes)):
        axes[j].axis("off")

    fig.suptitle(title, fontsize=16, fontweight="bold", y=1.02)
    plt.tight_layout()
    plt.show()

def plot_boxplot(data, title, samples=500):
    df = pd.DataFrame(data, columns=["min", "max", "mean", "std"])
    df = df.dropna()

    row = df.iloc[0]
    mean, std, vmin, vmax = row["mean"], row["std"], row["min"], row["max"]
    data_points = np.random.normal(mean, std if std > 0 else 0.1, samples)
    data_points = np.clip(data_points, vmin, vmax)

    plt.figure(figsize=(6, 4))
    plt.boxplot(data_points, vert=True, patch_artist=True)
    plt.title(title, fontsize=16, fontweight="bold")
    plt.ylabel("Value")
    plt.tight_layout()
    plt.show()

def plot_wordclouds(pdf):
    categories = pdf["main_category"].unique()
    cols = min(3, len(categories))
    rows = -(-len(categories) // cols)

    fig, axes = plt.subplots(rows, cols, figsize=(6*cols, 5*rows))
    axes = axes.flatten()

    for i, cat in enumerate(categories):
        subset = pdf[pdf["main_category"] == cat]
        freqs = dict(zip(subset["expanded_words"], subset["count"]))

        wc = WordCloud(
            width=600,
            height=400,
            background_color="white",
            colormap="viridis"
        ).generate_from_frequencies(freqs)

        axes[i].imshow(wc, interpolation="bilinear")
        axes[i].set_title(cat, fontsize=14, fontweight="bold")
        axes[i].axis("off")

    for j in range(i+1, len(axes)):
        axes[j].axis("off")

    plt.tight_layout()
    plt.show()

def plot_histograms(pdf, bins=30):
    categories = pdf["main_category"].unique()
    n = len(categories)
    cols = min(3, n)
    rows = math.ceil(n / cols)

    fig, axes = plt.subplots(rows, cols, figsize=(6*cols, 4*rows))
    axes = axes.flatten()

    for i, cat in enumerate(categories):
        subset = pdf[pdf["main_category"] == cat]

        sns.histplot(
            data=subset,
            x="word_count",
            bins=bins,
            ax=axes[i],
            color="skyblue",
            edgecolor="black"
        )
        axes[i].set_title(cat, fontsize=12, fontweight="bold")
        axes[i].set_xlabel("Word Count")
        axes[i].set_ylabel("Frequency")

    for j in range(i+1, len(axes)):
        axes[j].axis("off")

    fig.suptitle("Histogram of Word Counts per Category", fontsize=16, fontweight="bold")
    plt.tight_layout()
    plt.show()