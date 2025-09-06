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

class CircularPlotMode(Enum):
    SINGLE = 'single'
    MATRIX = 'matrix'

class CircularMatrixPlot:
    def __init__(self, title, cols: int = 3):
        self.title = title
        self.cols = cols

    def plot(self, data, legend_labels = None):
        n = len(data)
        cols = min(self.cols, n)
        rows = math.ceil(n / cols)

        fig, axes = plt.subplots(rows, cols, figsize=(3*cols, 3*rows))
        axes = axes.flatten() if n > 1 else [axes]

        sns.set_theme(style="white", context="talk")
        palette = sns.color_palette("Set2", n_colors=n)

        for i, d in enumerate(data):
            values = d["values"]
            category = d["label"]
            subtitle = d["title"]

            ax = axes[i]

            wedges, texts = ax.pie(
                values,
                colors=palette,
                startangle=90,
                counterclock=False,
                wedgeprops={'linewidth': 1.2, 'edgecolor': 'white'}
            )

            centre_circle = plt.Circle((0, 0), 0.70, fc="white")
            ax.add_artist(centre_circle)

            ax.set_title(subtitle, fontsize=12)

            ax.set_aspect('equal')

        for j in range(i+1, len(axes)):
            axes[j].axis("off")

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
            ncol=len(legend_labels),
            frameon=False,
            fontsize=11
        )
        plt.tight_layout(rect=[0, 0, 1, 0.9])
        plt.suptitle(self.title, fontsize=16, fontweight="bold", y=1.02)
        plt.show()

class CircularSinglePlot:
    def __init__(self, title):
        self.title = title

    def plot(
            self, data, legend_labels=None, n_col=2, pie_labels=None,
            suptitle_y = 0.98,
            legend_x = 0.5, legend_y = 0.96,
            col_size = 8, rows_size = 8,
            plot_rect = None,
            legend_loc = "upper center"
        ):
        sns.set_theme(style="white", context="talk")
        palette = sns.color_palette("Set2", n_colors=len(data))

        fig, ax = plt.subplots(figsize=(col_size, rows_size))

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
            loc=legend_loc,
            bbox_to_anchor=(legend_x, legend_y),
            ncol=n_col,
            frameon=False,
            fontsize=11
        )
        plt.tight_layout(rect = plot_rect)
        plt.suptitle(self.title, fontsize=16, fontweight="bold", y=suptitle_y)
        plt.show()

class CircularPlot:
    def __init__(
        self,
    ):
        self.mode : CircularPlotMode = CircularPlotMode.SINGLE
        self.plotter : CircularMatrixPlot = None

    def prepare_matrix_show(
        self, title = "",
        cols : int = 3,
    ):
        self.mode : CircularPlotMode = CircularPlotMode.MATRIX
        self.plotter = CircularMatrixPlot(title, cols)

    def prepare_single_show(
        self, title = "",
    ):
        self.mode : CircularPlotMode = CircularPlotMode.MATRIX
        self.plotter = CircularSinglePlot(title)

    def plot(
        self, data, **kwargs
    ):
        self.plotter.plot(data, **kwargs)
