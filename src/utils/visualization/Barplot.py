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

from src.utils.text import format_number

class BarplotMode(Enum):
    SINGLE = 'single'
    MATRIX = 'matrix'
    PERCENT = 'percent'

class BarMatrixPlot:
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


class BarSinglePlot:
    def __init__(self, title):
        self.title = title

    def plot(
            self, data, xlabel='', ylabel='Valor',
            is_percentage = True, decimal_points = 1,
            x_rotation = 45, y_rotation = 0,
        ):
        sns.set_theme(style="white", context="talk")

        values = data["values"]
        labels = data["labels"]

        sorted_indices = np.argsort(values)[::-1]

        values = values[sorted_indices]
        labels = labels[sorted_indices]

        fig, ax = plt.subplots(figsize=(8, 8))
        palette = sns.color_palette(["#4c72b0"], n_colors=len(values))

        bars = ax.bar(labels, values, color=palette, edgecolor="white", linewidth=1.2)

        for bar, val in zip(bars, values):
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height(),
                f"{val:.{decimal_points}f} %" if is_percentage else f"{format_number(val)}",
                ha="center", va="bottom", fontsize=10
            )

        ax.set_ylabel(ylabel, fontsize=12)
        ax.set_xlabel(xlabel, fontsize=12)
        ax.set_ylim(0, max(values) * 1.15)
        ax.set_title(self.title, fontsize=16, fontweight="bold")

        if is_percentage:
            ax.yaxis.set_major_formatter(PercentFormatter(100))
        else:
            ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda y, _: format_number(y)))

        plt.xticks(rotation=x_rotation, ha="right")
        plt.yticks(rotation=y_rotation, ha="right")

        plt.tight_layout(h_pad=2)
        plt.show()

class PercentBarPlot:
    def __init__(self, title):
        self.title = title

    def plot(self, data, legend_labels=None, figsize=(10,6), ylabel = ""):
        sns.set_theme(style="white", context="talk")

        categories = [d["title"] for d in data]
        values_matrix = np.array([d["values"] for d in data])

        row_sums = values_matrix.sum(axis=1, keepdims=True)
        percentages = values_matrix / row_sums * 100

        n_segments = percentages.shape[1]
        palette = sns.color_palette("Set2", n_colors=n_segments)

        fig, ax = plt.subplots(figsize=figsize)

        left = np.zeros(len(categories))
        for i in range(n_segments):
            bars = ax.bar(
                categories,
                percentages[:, i],
                bottom=left,
                color=palette[i],
                edgecolor="white",
                linewidth=1.2
            )
            for bar, perc in zip(bars, percentages[:, i]):
                if perc > 3:
                    ax.text(
                        bar.get_x() + bar.get_width()/2,
                        bar.get_y() + bar.get_height()/2,
                        f"{perc:.1f}%",
                        ha="center", va="center", fontsize=9, color="black"
                    )
            left += percentages[:, i]

        if legend_labels is None:
            legend_labels = [f"Segment {i+1}" for i in range(n_segments)]

        legend_elements = [
            Patch(facecolor=palette[i], edgecolor="white", label=legend_labels[i])
            for i in range(n_segments)
        ]
        ax.legend(
            handles=legend_elements,
            loc="lower center",
            bbox_to_anchor=(0.5, 1.15),
            ncol=len(legend_labels),
            frameon=False,
            fontsize=11
        )

        ax.set_ylabel(ylabel)
        ax.set_ylim(0, 100)
        ax.set_title(self.title, fontsize=16, fontweight="bold")
        ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda y, _: f"{y:.0f}%"))

        plt.xticks(rotation=45, ha="right")
        plt.tight_layout(rect=[0, 0, 1, 0.9])
        plt.show()


class BarPlot:
    def __init__(
        self,
    ):
        self.mode : BarplotMode = BarplotMode.SINGLE
        self.plotter : BarMatrixPlot = None

    def prepare_matrix_show(
        self, title = "",
        cols : int = 3,
    ):
        self.mode : BarplotMode = BarplotMode.MATRIX
        self.plotter = BarMatrixPlot(title, cols)

    def prepare_single_show(
        self, title = ""
    ):
        self.mode : BarplotMode = BarplotMode.SINGLE
        self.plotter = BarSinglePlot(title)

    def prepare_percent_show(
        self, title = ""
    ):
        self.mode : BarplotMode = BarplotMode.PERCENT
        self.plotter = PercentBarPlot(title)

    def plot(
        self, data, **kwargs
    ):
        self.plotter.plot(data, **kwargs)
