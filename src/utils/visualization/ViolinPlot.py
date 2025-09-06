import math
import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter
import numpy as np
import pandas as pd
from wordcloud import WordCloud
import seaborn as sns
from enum import Enum
from dataclasses import dataclass
from pyspark.sql import DataFrame
from matplotlib.patches import Patch

class ViolinPlotMode(Enum):
    SINGLE = 'single'
    MATRIX = 'matrix'

class ViolinMatrixPlot:
    def __init__(self, title, cols: int = 3):
        self.title = title
        self.cols = cols

    def plot(
            self, data, ylabel : str = "",
            is_percentage = True, decimal_points = 1,
            cols_size = 10, rows_size = 5,
        ):
        n = len(data)
        cols = min(self.cols, n)
        rows = math.ceil(n / cols)

        fig, axes = plt.subplots(rows, cols, figsize=(cols_size*cols, rows_size*rows))
        axes = axes.flatten() if n > 1 else [axes]

        sns.set_theme(style="white", context="talk")
        palette = sns.color_palette(["#4c72b0"])

        for i, d in enumerate(data):
            values = d["values"]
            labels = d["labels"]
            subtitle = d["title"]

            ax = axes[i]

            bars = ax.barh(
                labels, values,
                color=palette, edgecolor="white", linewidth=1.2
            )

            ax.set_ylabel(ylabel, fontsize=2)
            ax.set_xticklabels([])
            ax.set_title(subtitle, fontsize=13, fontweight="bold")

            for bar, val in zip(bars, values):
                ax.text(
                    bar.get_x() + bar.get_width() / 2,
                    bar.get_y() + bar.get_height() / 4,
                    f"{val:.{decimal_points}f} %" if is_percentage else f"{float(val):,.{decimal_points}f}",
                    ha="center", va="bottom", fontsize=10, color="white"
                )

        for j in range(i+1, len(axes)):
            axes[j].axis("off")

        fig.suptitle(self.title, fontsize=16, fontweight="bold", y=1.02)
        plt.xticks(rotation=45, ha="right")
        plt.tight_layout(h_pad=2)
        plt.show()

class ViolinSinglePlot:
    def __init__(self, title):
        self.title = title

    def plot(self, data, ylabel='Valor', xlabel="", samples = 500):
        sns.set_theme(style="white", context="talk")
        mean, std, vmin, vmax = data["mean"], data["std"], data["min"], data["max"]
        data_points = np.random.normal(mean, std if std > 0 else 0.1, samples)
        data_points = np.clip(data_points, vmin, vmax)
        sns.violinplot(
            x=[xlabel] * len(data_points),
            y=data_points,
            palette="Set2",
            width=0.6,
            fliersize=4,
            linewidth=1.5,
            boxprops=dict(alpha=0.7),
        )
        sns.despine(left=False, bottom=True)

        plt.title(self.title, fontsize=16, fontweight="bold")
        plt.ylabel(ylabel)
        plt.tight_layout()
        plt.show()

class BoxPlot:
    def __init__(
        self,
    ):
        self.mode : ViolinPlotMode = ViolinPlotMode.SINGLE
        self.plotter : ViolinMatrixPlot = None

    def prepare_matrix_show(
        self, title = "",
    ):
        self.mode : ViolinPlotMode = ViolinPlotMode.MATRIX
        self.plotter = ViolinSinglePlot(title)

    def prepare_single_show(
        self, title = ""
    ):
        self.mode : ViolinPlotMode = ViolinPlotMode.SINGLE
        self.plotter = ViolinSinglePlot(title)

    def plot(
        self, data, **kwargs
    ):
        self.plotter.plot(data, **kwargs)
