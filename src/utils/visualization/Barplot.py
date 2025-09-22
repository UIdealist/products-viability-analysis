import math
import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter, FuncFormatter
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
            color: str = "#4c72b0",
            x_font_size: int = 12,
            y_font_size: int = 12,
            title_font_size: int = 16,
            subtitle_font_size: int = 13,
            label_font_size: int = 10,
            label_density: float = 1.0,
            rotate_labels: bool = True,
            label_rotation: int = 60,
            rotate_x_labels: bool = False,
            x_label_rotation: int = 45,
            label_fontweight: str = "normal",
        ):
        n = len(data)
        cols = min(self.cols, n)
        rows = math.ceil(n / cols)

        fig, axes = plt.subplots(rows, cols, figsize=(cols_size*cols, rows_size*rows))
        axes = axes.flatten() if n > 1 else [axes]

        sns.set_theme(style="white", context="talk")

        base_colors = ["#4c72b0", "#55a3ff", "#2c5aa0", "#1e3d72", "#0f1f3a"]
        bar_color = base_colors[0] if color == "#4c72b0" else color

        for i, d in enumerate(data):
            values = d["values"]
            labels = d["labels"]
            subtitle = d["title"]

            ax = axes[i]

            bars = ax.barh(
                labels, values,
                color=bar_color, edgecolor="white", linewidth=1.2, alpha=0.9
            )

            ax.set_ylabel(ylabel, fontsize=y_font_size, fontweight="bold")
            ax.set_xticklabels([])
            ax.set_title(subtitle, fontsize=subtitle_font_size, fontweight="bold")


            total_bars = len([v for v in values if v > 0])
            labels_to_show = max(1, int(total_bars * label_density))
            bar_indices = [(i, val) for i, val in enumerate(values) if val > 0]
            bar_indices.sort(key=lambda x: x[1], reverse=True)
            selected_indices = set([i for i, _ in bar_indices[:labels_to_show]])

            label_positions = []
            min_label_spacing = max(values) * 0.05 if len(values) > 0 else 1

            for j, (bar, val) in enumerate(zip(bars, values)):
                if val > 0 and j in selected_indices:
                    display_value = 100*val/len(values) if is_percentage else val
                    if is_percentage:
                        display_text = f"{display_value:.{decimal_points}f}%"
                    else:
                        display_text = f"{format_number(display_value)}"

                    x_pos = bar.get_x() + bar.get_width() / 2
                    y_pos = bar.get_y() + bar.get_height() / 2

                    can_place_label = True
                    for existing_x, existing_y in label_positions:
                        if abs(x_pos - existing_x) < bar.get_width() * 0.8:
                            if abs(y_pos - existing_y) < min_label_spacing:
                                can_place_label = False
                                break
                    if can_place_label:

                        if rotate_labels:
                            ha = "center"
                            va = "center"
                        else:
                            ha = "center"
                            va = "center"
                        ax.text(
                            x_pos,
                            y_pos,
                            display_text,
                            ha=ha,
                            va=va,
                            fontsize=label_font_size,
                            fontweight=label_fontweight,
                            color="white",
                            rotation=label_rotation if rotate_labels else 0
                        )
                        label_positions.append((x_pos, y_pos))


            ax.grid(True, alpha=0.3, linestyle='-', linewidth=0.5)
            ax.spines['top'].set_visible(False)
            ax.spines['right'].set_visible(False)
            ax.spines['left'].set_linewidth(0.8)
            ax.spines['bottom'].set_linewidth(0.8)

            ax.tick_params(axis='both', labelsize=min(x_font_size, y_font_size))

        for j in range(i+1, len(axes)):
            axes[j].axis("off")

        fig.suptitle(self.title, fontsize=title_font_size, fontweight="bold", y=1.02)
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
            color: str = "#4c72b0",
            figsize=(8,6),
            x_font_size: int = 12,
            y_font_size: int = 12,
            title_font_size: int = 16,
            label_font_size: int = 10,
            label_density: float = 1.0,
            rotate_labels: bool = True,
            label_rotation: int = 60,
            rotate_x_labels: bool = False,
            x_label_rotation: int = 45,
            label_fontweight: str = "normal",
            show_x_labels: bool = True,
            x_label_density: float = 1.0,
            bar_width: float = 1.0,
            use_exponential_labels: bool = False,
        ):
        sns.set_theme(style="white", context="talk")

        values = data["values"]
        labels = data["labels"]

        fig, ax = plt.subplots(figsize=figsize)


        base_colors = ["#4c72b0", "#55a3ff", "#2c5aa0", "#1e3d72", "#0f1f3a"]

        bar_color = base_colors[0] if color == "#4c72b0" else color


        bars = ax.bar(labels, values, color=bar_color, edgecolor="white", linewidth=1.2, alpha=0.9, width=bar_width)


        total_bars = len([v for v in values if v > 0])
        labels_to_show = max(1, int(total_bars * label_density))
        bar_indices = [(i, val) for i, val in enumerate(values) if val > 0]
        bar_indices.sort(key=lambda x: x[1], reverse=True)
        selected_indices = set([i for i, _ in bar_indices[:labels_to_show]])

        label_positions = []
        min_label_spacing = max(values) * 0.05 if len(values) > 0 else 1

        for i, (bar, val) in enumerate(zip(bars, values)):
            if val > 0 and i in selected_indices:
                display_value = 100*val/len(values) if is_percentage else val
                if is_percentage:
                    display_text = f"{display_value:.{decimal_points}f}%"
                else:
                    display_text = f"{format_number(display_value)}"

                x_pos = bar.get_x() + bar.get_width() / 2
                y_pos = bar.get_height() + max(values) * 0.01

                can_place_label = True
                for existing_x, existing_y in label_positions:
                    if abs(x_pos - existing_x) < bar.get_width() * 0.8:
                        if abs(y_pos - existing_y) < min_label_spacing:
                            can_place_label = False
                            break
                if can_place_label:

                    if rotate_labels:
                        ha = "center"
                        va = "bottom"

                        y_pos_rotated = y_pos + max(values) * 0.02
                    else:
                        ha = "center"
                        va = "bottom"
                        y_pos_rotated = y_pos
                    ax.text(
                        x_pos,
                        y_pos_rotated,
                        display_text,
                        ha=ha,
                        va=va,
                        fontsize=label_font_size,
                        fontweight=label_fontweight,
                        color="black",
                        rotation=label_rotation if rotate_labels else 0
                    )
                    label_positions.append((x_pos, y_pos))

        ax.set_ylabel(ylabel, fontsize=y_font_size, fontweight="bold")
        ax.set_xlabel(xlabel, fontsize=x_font_size, fontweight="bold")
        ax.set_ylim(0, max(values) * 1.1)
        ax.set_title(self.title, fontsize=title_font_size, fontweight="bold", pad=20)


        ax.grid(True, alpha=0.3, linestyle='-', linewidth=0.5)
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['left'].set_linewidth(0.8)
        ax.spines['bottom'].set_linewidth(0.8)


        if is_percentage:
            ax.yaxis.set_major_formatter(PercentFormatter(100))
        else:
            ax.yaxis.set_major_formatter(FuncFormatter(
                lambda val, _: format_number(val) if abs(val) >= 1000 else f"{val:.{decimal_points}f}"
            ))


        ax.yaxis.set_tick_params(labelsize=y_font_size)
        ax.xaxis.set_tick_params(labelsize=x_font_size)


        if show_x_labels:

            total_labels = len(labels)
            labels_to_show_count = max(1, int(total_labels * x_label_density))
            if labels_to_show_count < total_labels:

                step = max(1, total_labels / labels_to_show_count)
                selected_indices = [int(i * step) for i in range(labels_to_show_count)]

                selected_indices = [min(i, total_labels - 1) for i in selected_indices]
                selected_labels = [labels[i] for i in selected_indices]
            else:
                selected_labels = labels

            if use_exponential_labels:
                try:

                    numeric_labels = [float(label) for label in selected_labels]
                    formatted_labels = [f"{val:.1e}" for val in numeric_labels]
                except (ValueError, TypeError):

                    formatted_labels = selected_labels
            else:

                try:
                    numeric_labels = [float(label) for label in selected_labels]
                    formatted_labels = [f"{val:.1f}" for val in numeric_labels]
                except (ValueError, TypeError):

                    formatted_labels = selected_labels

            if len(formatted_labels) < len(labels):

                tick_positions = []
                tick_labels = []
                for i, label in enumerate(formatted_labels):
                    if i < len(selected_indices):
                        tick_positions.append(selected_indices[i])
                        tick_labels.append(label)
                ax.set_xticks(tick_positions)
                ax.set_xticklabels(tick_labels)
            else:
                ax.set_xticklabels(formatted_labels)

        if rotate_x_labels:
            plt.xticks(rotation=x_label_rotation, ha="right")
        else:
            plt.xticks(rotation=x_rotation, ha="right")
        plt.yticks(rotation=y_rotation, ha="right")

        plt.tight_layout()
        plt.show()

class PercentBarPlot:
    def __init__(self, title):
        self.title = title

    def plot(self, data, legend_labels=None, figsize=(10,6), ylabel = "",
             color: str = "#4c72b0",
             x_font_size: int = 12,
             y_font_size: int = 12,
             title_font_size: int = 16,
             label_font_size: int = 9,
             legend_font_size: int = 11,
             label_density: float = 1.0,
             rotate_labels: bool = True,
             label_rotation: int = 60,
             rotate_x_labels: bool = False,
             x_label_rotation: int = 45,
             decimal_points: int = 1,
             label_fontweight: str = "normal"):
        sns.set_theme(style="white", context="talk")

        categories = [d["title"] for d in data]
        values_matrix = np.array([d["values"] for d in data])

        row_sums = values_matrix.sum(axis=1, keepdims=True)
        percentages = values_matrix / row_sums * 100

        n_segments = percentages.shape[1]

        base_colors = ["#4c72b0", "#55a3ff", "#2c5aa0", "#1e3d72", "#0f1f3a"]
        if color == "#4c72b0":
            palette = [base_colors[i % len(base_colors)] for i in range(n_segments)]
        else:
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
                linewidth=1.2,
                alpha=0.9
            )

            total_bars = len([p for p in percentages[:, i] if p > 3])
            labels_to_show = max(1, int(total_bars * label_density))
            bar_indices = [(j, perc) for j, perc in enumerate(percentages[:, i]) if perc > 3]
            bar_indices.sort(key=lambda x: x[1], reverse=True)
            selected_indices = set([j for j, _ in bar_indices[:labels_to_show]])

            label_positions = []
            min_label_spacing = max(percentages[:, i]) * 0.05 if len(percentages[:, i]) > 0 else 1
            for j, (bar, perc) in enumerate(zip(bars, percentages[:, i])):
                if perc > 3 and j in selected_indices:

                    x_pos = bar.get_x() + bar.get_width()/2
                    y_pos = bar.get_y() + bar.get_height()/2

                    can_place_label = True
                    for existing_x, existing_y in label_positions:
                        if abs(x_pos - existing_x) < bar.get_width() * 0.8:
                            if abs(y_pos - existing_y) < min_label_spacing:
                                can_place_label = False
                                break
                    if can_place_label:

                        if rotate_labels:
                            ha = "center"
                            va = "center"
                        else:
                            ha = "center"
                            va = "center"
                        ax.text(
                            x_pos,
                            y_pos,
                            f"{perc:.{decimal_points}f}%",
                            ha=ha, 
                            va=va, 
                            fontsize=label_font_size, 
                            fontweight=label_fontweight,
                            color="black",
                            rotation=label_rotation if rotate_labels else 0
                        )
                        label_positions.append((x_pos, y_pos))
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
            fontsize=legend_font_size
        )

        ax.set_ylabel(ylabel, fontsize=y_font_size, fontweight="bold")
        ax.set_ylim(0, 100)
        ax.set_title(self.title, fontsize=title_font_size, fontweight="bold", pad=20)
        ax.yaxis.set_major_formatter(FuncFormatter(lambda y, _: f"{y:.0f}%"))


        ax.grid(True, alpha=0.3, linestyle='-', linewidth=0.5)
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['left'].set_linewidth(0.8)
        ax.spines['bottom'].set_linewidth(0.8)


        ax.tick_params(axis='both', labelsize=min(x_font_size, y_font_size))


        if rotate_x_labels:
            plt.xticks(rotation=x_label_rotation, ha="right")
        else:
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
