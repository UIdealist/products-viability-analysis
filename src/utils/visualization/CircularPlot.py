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
from src.utils.visualization.Barplot import COLD_COLOR_PALETTE as BARPLOT_COLD_COLOR_PALETTE

COLD_COLOR_PALETTE = [
    '#687B8B',
    '#ADE1F5',
    '#4F79BD',
    '#4A9B9B',
    '#4A8B4A',
    '#6B4C93',
    '#8B6FA8',
    '#6BB3B3',
    '#6BA86B',
    '#3A5A8A',
    '#4A2C5F',
    '#2F6B6B',
    '#2F5A2F',
    '#5A8BC4',
    '#7A5FA3',
    '#5AABAB',
    '#5A9B5A',
]

def brighten_color(hex_color, factor=0.3):
    r = int(hex_color[1:3], 16)
    g = int(hex_color[3:5], 16)
    b = int(hex_color[5:7], 16)
    r = min(255, int(r + (255 - r) * factor))
    g = min(255, int(g + (255 - g) * factor))
    b = min(255, int(b + (255 - b) * factor))
    return f"#{r:02x}{g:02x}{b:02x}"
plt.rcParams['font.family'] = 'Times New Roman'
plt.rcParams['axes.labelsize'] = 12
plt.rcParams['axes.titlesize'] = 14
plt.rcParams['xtick.labelsize'] = 10
plt.rcParams['ytick.labelsize'] = 10
plt.rcParams['legend.fontsize'] = 10
plt.rcParams['figure.titlesize'] = 16

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
        plt.rcParams["font.family"] = "Times New Roman"
        
        n_categories = len(data[0]["values"]) if data else 0
        if n_categories <= 2:
            palette = [brighten_color(BARPLOT_COLD_COLOR_PALETTE[i]) for i in range(n_categories)]
        else:
            palette = [brighten_color(COLD_COLOR_PALETTE[i % len(COLD_COLOR_PALETTE)]) for i in range(n_categories)]

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
        plt.rcParams["font.family"] = "Times New Roman"
        
        n_categories = len(data)
        if n_categories <= 2:
            palette = [brighten_color(BARPLOT_COLD_COLOR_PALETTE[i]) for i in range(n_categories)]
        else:
            palette = [brighten_color(COLD_COLOR_PALETTE[i % len(COLD_COLOR_PALETTE)]) for i in range(n_categories)]

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
