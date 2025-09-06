import math
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from wordcloud import WordCloud
import seaborn as sns
from enum import Enum
from dataclasses import dataclass
from pyspark.sql import DataFrame
from matplotlib.patches import Patch

class WordCloudPlotMode(Enum):
    SINGLE = 'single'
    MATRIX = 'matrix'

class WordCloudMatrixPlot:
    def __init__(self, title):
        self.title = title

    def plot(
            self, data,
            cols: int = 3,
            individual_width: int = 600,
            individual_height: int = 400,
            cols_size: int = 6,
            rows_size: int = 5
        ):
        categories = data["category"].unique()
        cols = min(cols, len(categories))
        rows = -(-len(categories) // cols)

        fig, axes = plt.subplots(rows, cols, figsize=(cols_size*cols, rows_size*rows))
        axes = axes.flatten()

        for i, cat in enumerate(categories):
            subset = data[data["category"] == cat]
            freqs = dict(zip(subset["word"], subset["count"]))

            wc = WordCloud(
                width=individual_width,
                height=individual_height,
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

class WordCloudSinglePlot:
    def __init__(self, title):
        self.title = title

    def plot(self, data, legend_labels=None, n_col=2, pie_labels=None):
        sns.set_theme(style="white", context="talk")
        palette = sns.color_palette("Set2", n_colors=len(data))

        fig, ax = plt.subplots(figsize=(8, 8))

        if not pie_labels:
            pie_labels = legend_labels

        wedges, texts = ax.pie(
            data,
            colors=palette,
            startangle=90,
            counterclock=False,
            wedgeprops={'linewidth': 1.2, 'edgecolor': 'white'}
        )

        centre_circle = plt.Circle((0, 0), 0.70, fc="white")
        ax.add_artist(centre_circle)

        ax.set_aspect('equal')
        ax.axis("off")

        if legend_labels is None:
            legend_labels = [f"Segment {i+1}" for i in range(len(data[0]["values"]))]

        legend_elements = [
            Patch(facecolor=palette[i], edgecolor="white", label=legend_labels[i])
            for i in range(len(legend_labels))
        ]

        fig.legend(
            handles=legend_elements,
            loc="upper center",
            bbox_to_anchor=(0.5, 0.96),
            ncol=n_col,
            frameon=False,
            fontsize=11
        )
        plt.tight_layout(rect=[0, 0, 1, 0.9])
        plt.suptitle(self.title, fontsize=16, fontweight="bold", y=1.02)
        plt.show()

class WordCloudPlot:
    def __init__(
        self,
    ):
        self.mode : WordCloudPlotMode = WordCloudPlotMode.SINGLE
        self.plotter : WordCloudSinglePlot = None

    def prepare_matrix_show(
        self, title = "",
    ):
        self.mode : WordCloudPlotMode = WordCloudPlotMode.MATRIX
        self.plotter = WordCloudMatrixPlot(title)

    def prepare_single_show(
        self, title = "",
    ):
        self.mode : WordCloudPlotMode = WordCloudPlotMode.SINGLE
        self.plotter = WordCloudSinglePlot(title)

    def plot(
        self, data, **kwargs
    ):
        self.plotter.plot(data, **kwargs)
