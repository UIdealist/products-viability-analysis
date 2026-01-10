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

COLD_COLOR_PALETTE = [
    '#193169',
    '#D4E0EC',
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

def get_label_color(bar_color):
    if bar_color == COLD_COLOR_PALETTE[0]:
        return "white"
    elif bar_color == COLD_COLOR_PALETTE[1]:
        return "black"
    else:
        r = int(bar_color[1:3], 16)
        g = int(bar_color[3:5], 16)
        b = int(bar_color[5:7], 16)
        brightness = (r * 299 + g * 587 + b * 114) / 1000
        return "black" if brightness > 128 else "white"

plt.rcParams["font.family"] = "Times New Roman"
plt.rcParams['axes.labelsize'] = 12
plt.rcParams['axes.titlesize'] = 14
plt.rcParams['xtick.labelsize'] = 10
plt.rcParams['ytick.labelsize'] = 10
plt.rcParams['legend.fontsize'] = 10
plt.rcParams['figure.titlesize'] = 16

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
            rotate_labels: bool = False,
            label_rotation: int = 60,
            rotate_x_labels: bool = False,
            x_label_rotation: int = 45,
            label_fontweight: str = "normal",
            x_rotation = 45,
            y_rotation = 0,
            reduce_gaps: bool = False,
            labels_on_top: bool = False,
        ):
        n = len(data)
        cols = min(self.cols, n)
        rows = math.ceil(n / cols)

        fig, axes = plt.subplots(rows, cols, figsize=(cols_size*cols, rows_size*rows))
        axes = axes.flatten() if n > 1 else [axes]

        sns.set_theme(style="white", context="talk")
        plt.rcParams["font.family"] = "Times New Roman"

        bar_color = COLD_COLOR_PALETTE[0] if color == "#4c72b0" or color == "#4F79BD" or color == "#687B8B" else color

        for i, d in enumerate(data):
            values = d["values"]
            labels = d["labels"]
            subtitle = d["title"]

            ax = axes[i]

            bar_height = 1.0 if reduce_gaps else 0.8
            bars = ax.barh(
                labels, values,
                height=bar_height,
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
                if val > 0 and (labels_on_top or j in selected_indices):
                    display_value = 100*val/len(values) if is_percentage else val
                    if is_percentage:
                        display_text = f"{display_value:.{decimal_points}f}%"
                    else:
                        display_text = f"{format_number(display_value)}"

                    if labels_on_top:
                        x_pos = bar.get_x() + bar.get_width()
                        y_pos = bar.get_y() + bar.get_height() / 2
                    else:
                        x_pos = bar.get_x() + bar.get_width() / 2
                        y_pos = bar.get_y() + bar.get_height() / 2

                    can_place_label = True
                    for existing_x, existing_y in label_positions:
                        if abs(x_pos - existing_x) < bar.get_width() * 0.8:
                            if abs(y_pos - existing_y) < min_label_spacing:
                                can_place_label = False
                                break
                    if can_place_label:

                        if labels_on_top:
                            ha = "left"
                            va = "center"
                        elif rotate_labels:
                            ha = "center"
                            va = "center"
                        else:
                            ha = "center"
                            va = "center"
                        label_color = "black" if labels_on_top else get_label_color(bar_color)
                        ax.text(
                            x_pos,
                            y_pos,
                            display_text,
                            ha=ha,
                            va=va,
                            fontsize=label_font_size,
                            fontweight=label_fontweight,
                            color=label_color,
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
        plt.xticks(rotation=x_rotation, ha="right")
        plt.yticks(rotation=y_rotation, ha="right")
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
            rotate_labels: bool = False,
            label_rotation: int = 60,
            rotate_x_labels: bool = False,
            x_label_rotation: int = 45,
            label_fontweight: str = "normal",
            show_x_labels: bool = False,
            x_label_density: float = 1.0,
            bar_width: float = 1.0,
            use_exponential_labels: bool = False,
            horizontal: bool = True,
            reduce_gaps: bool = False,
            labels_on_top: bool = False,
        ):
        values = data["values"]
        labels = data["labels"]

        fig, ax = plt.subplots(figsize=figsize)
        sns.set_theme(style="white", context="talk")
        plt.rcParams["font.family"] = "Times New Roman"

        bar_color = COLD_COLOR_PALETTE[0] if color == "#4c72b0" or color == "#4F79BD" or color == "#687B8B" else color

        if horizontal:
            bar_height = 1.0 if reduce_gaps else 0.8
            bars = ax.barh(labels, values, height=bar_height, color=bar_color, edgecolor="white", linewidth=1.2, alpha=0.9)
        else:
            bar_width_val = 1.0 if reduce_gaps else 0.8
            bars = ax.bar(labels, values, width=bar_width_val, color=bar_color, edgecolor="white", linewidth=1.2, alpha=0.9)

        total_bars = len([v for v in values if v > 0])
        labels_to_show = max(1, int(total_bars * label_density))
        bar_indices = [(i, val) for i, val in enumerate(values) if val > 0]
        bar_indices.sort(key=lambda x: x[1], reverse=True)
        selected_indices = set([i for i, _ in bar_indices[:labels_to_show]])

        label_positions = []
        min_label_spacing = max(values) * 0.05 if len(values) > 0 else 1

        for i, (bar, val) in enumerate(zip(bars, values)):
            if val > 0 and (labels_on_top or i in selected_indices):
                display_value = 100*val/len(values) if is_percentage else val
                if is_percentage:
                    display_text = f"{display_value:.{decimal_points}f}%"
                else:
                    display_text = f"{format_number(display_value)}"

                if horizontal:
                    if labels_on_top:
                        x_pos = bar.get_x() + bar.get_width()
                        y_pos = bar.get_y() + bar.get_height() / 2
                    else:
                        x_pos = bar.get_x() + bar.get_width() / 2
                        y_pos = bar.get_y() + bar.get_height() / 2
                else:
                    x_pos = bar.get_x() + bar.get_width() / 2
                    if labels_on_top:
                        y_pos = bar.get_y() + bar.get_height() + max(values) * 0.02
                    else:
                        y_pos = bar.get_y() + bar.get_height()

                can_place_label = True
                for existing_x, existing_y in label_positions:
                    if horizontal:
                        if abs(x_pos - existing_x) < bar.get_width() * 0.8:
                            if abs(y_pos - existing_y) < min_label_spacing:
                                can_place_label = False
                                break
                    else:
                        if abs(y_pos - existing_y) < bar.get_height() * 0.8:
                            if abs(x_pos - existing_x) < min_label_spacing:
                                can_place_label = False
                                break
                if can_place_label:

                    if horizontal:
                        if labels_on_top:
                            ha = "left"
                            va = "center"
                        elif rotate_labels:
                            ha = "center"
                            va = "center"
                        else:
                            ha = "center"
                            va = "center"
                    else:
                        if labels_on_top:
                            ha = "center"
                            va = "bottom"
                        elif rotate_labels:
                            ha = "center"
                            va = "bottom"
                        else:
                            ha = "center"
                            va = "bottom"
                    label_color = "black" if labels_on_top else get_label_color(bar_color)
                    ax.text(
                        x_pos,
                        y_pos,
                        display_text,
                        ha=ha,
                        va=va,
                        fontsize=label_font_size,
                        fontweight=label_fontweight,
                        color=label_color,
                        rotation=label_rotation if rotate_labels else 0
                    )
                    label_positions.append((x_pos, y_pos))

        if horizontal:
            ax.set_xlabel(ylabel, fontsize=y_font_size, fontweight="bold")
            ax.set_ylabel(xlabel, fontsize=x_font_size, fontweight="bold")
            ax.set_xlim(0, max(values) * 1.1)
            ax.invert_yaxis()
        else:
            ax.set_xlabel(xlabel, fontsize=x_font_size, fontweight="bold")
            ax.set_ylabel(ylabel, fontsize=y_font_size, fontweight="bold")
            ax.set_ylim(0, max(values) * 1.1)
        ax.set_title(self.title, fontsize=title_font_size, fontweight="bold", pad=20)


        ax.grid(True, alpha=0.3, linestyle='-', linewidth=0.5)
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['left'].set_linewidth(0.8)
        ax.spines['bottom'].set_linewidth(0.8)


        if horizontal:
            if is_percentage:
                ax.xaxis.set_major_formatter(PercentFormatter(100))
            else:
                ax.xaxis.set_major_formatter(FuncFormatter(
                    lambda val, _: format_number(val) if abs(val) >= 1000 else f"{val:.{decimal_points}f}"
                ))
            ax.yaxis.set_tick_params(labelsize=y_font_size)
            ax.xaxis.set_tick_params(labelsize=x_font_size)
        else:
            if is_percentage:
                ax.yaxis.set_major_formatter(PercentFormatter(100))
            else:
                ax.yaxis.set_major_formatter(FuncFormatter(
                    lambda val, _: format_number(val) if abs(val) >= 1000 else f"{val:.{decimal_points}f}"
                ))
            ax.yaxis.set_tick_params(labelsize=y_font_size)
            ax.xaxis.set_tick_params(labelsize=x_font_size)


        if show_x_labels:
            axis_to_use = ax.yaxis if horizontal else ax.xaxis
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
                if horizontal:
                    ax.set_yticks(tick_positions)
                    ax.set_yticklabels(tick_labels)
                else:
                    ax.set_xticks(tick_positions)
                    ax.set_xticklabels(tick_labels)
            else:
                if horizontal:
                    ax.set_yticklabels(formatted_labels)
                else:
                    ax.set_xticklabels(formatted_labels)

        if horizontal:
            if rotate_x_labels:
                plt.xticks(rotation=x_label_rotation, ha="right")
            else:
                plt.xticks(rotation=x_rotation, ha="right")
            plt.yticks(rotation=y_rotation, ha="right")
        else:
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
             rotate_labels: bool = False,
             label_rotation: int = 60,
             rotate_x_labels: bool = False,
             x_label_rotation: int = 45,
             decimal_points: int = 1,
             label_fontweight: str = "normal",
             reduce_gaps: bool = False,
             labels_on_top: bool = False):
        sns.set_theme(style="white", context="talk")
        plt.rcParams["font.family"] = "Times New Roman"

        categories = [d["title"] for d in data]
        values_matrix = np.array([d["values"] for d in data])

        row_sums = values_matrix.sum(axis=1, keepdims=True)
        percentages = values_matrix / row_sums * 100

        n_segments = percentages.shape[1]

        if color == "#4c72b0" or color == "#4F79BD" or color == "#687B8B":
            palette = [COLD_COLOR_PALETTE[i % len(COLD_COLOR_PALETTE)] for i in range(n_segments)]
        else:
            palette = [COLD_COLOR_PALETTE[i % len(COLD_COLOR_PALETTE)] for i in range(n_segments)]

        fig, ax = plt.subplots(figsize=figsize)

        left = np.zeros(len(categories))
        bar_width_val = 1.0 if reduce_gaps else 0.8
        for i in range(n_segments):
            bars = ax.bar(
                categories,
                percentages[:, i],
                bottom=left,
                width=bar_width_val,
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
                if perc > 3 and (labels_on_top or j in selected_indices):

                    x_pos = bar.get_x() + bar.get_width()/2
                    if labels_on_top:
                        y_pos = bar.get_y() + bar.get_height() + max(percentages[:, i]) * 0.01
                    else:
                        y_pos = bar.get_y() + bar.get_height()/2

                    can_place_label = True
                    for existing_x, existing_y in label_positions:
                        if abs(x_pos - existing_x) < bar.get_width() * 0.8:
                            if abs(y_pos - existing_y) < min_label_spacing:
                                can_place_label = False
                                break
                    if can_place_label:

                        if labels_on_top:
                            ha = "center"
                            va = "bottom"
                        elif rotate_labels:
                            ha = "center"
                            va = "center"
                        else:
                            ha = "center"
                            va = "center"
                        label_color = "black" if labels_on_top else get_label_color(palette[i])
                        ax.text(
                            x_pos,
                            y_pos,
                            f"{perc:.{decimal_points}f}%",
                            ha=ha, 
                            va=va, 
                            fontsize=label_font_size, 
                            fontweight=label_fontweight,
                            color=label_color,
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
