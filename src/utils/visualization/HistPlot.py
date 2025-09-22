import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter, PercentFormatter
import seaborn as sns
import numpy as np
from src.utils.text import format_number

class HistPlot:
    def __init__(self, title: str):
        self.title = title

    def plot(
        self,
        values,
        bins: int = 20,
        xlabel: str = "Values",
        ylabel: str = "Frequency",
        is_percentage: bool = False,
        decimal_points: int = 1,
        color: str = "#4c72b0",
        figsize=(8,6),
        x_font_size: int = 12,
        y_font_size: int = 12,
        label_density: float = 1.0,
        rotate_labels: bool = True,
        label_rotation: int = 60,
        rotate_x_labels: bool = False,
        x_label_rotation: int = 45,
    ):
        sns.set_theme(style="white", context="talk")

        fig, ax = plt.subplots(figsize=figsize)


        base_colors = ["#4c72b0", "#55a3ff", "#2c5aa0", "#1e3d72", "#0f1f3a"]

        hist_color = base_colors[0]
        counts, bin_edges, patches = ax.hist(
            values,
            bins=bins,
            color=hist_color,
            edgecolor="white",
            linewidth=1.2,
            alpha=0.9
        )

        if is_percentage:
            ax.yaxis.set_major_formatter(PercentFormatter(xmax=len(values)))
            ylabel = "Percentage"
        else:
            ax.yaxis.set_major_formatter(FuncFormatter(
                lambda val, _: format_number(val)
            ))


        total_bars = len([c for c in counts if c > 0])
        labels_to_show = max(1, int(total_bars * label_density))
        bar_indices = [(i, count) for i, count in enumerate(counts) if count > 0]
        bar_indices.sort(key=lambda x: x[1], reverse=True)
        selected_indices = set([i for i, _ in bar_indices[:labels_to_show]])

        label_positions = []
        min_label_spacing = max(counts) * 0.05
        for i, (count, edge_left, edge_right) in enumerate(zip(counts, bin_edges[:-1], bin_edges[1:])):
            if count > 0 and i in selected_indices:
                display_value = 100*count/len(values) if is_percentage else count
                if is_percentage:
                    display_text = f"{display_value:.{decimal_points}f}%"
                else:
                    display_text = f"{format_number(display_value)}"

                x_pos = (edge_left + edge_right) / 2
                y_pos = count + max(counts) * 0.01

                can_place_label = True
                for existing_x, existing_y in label_positions:
                    if abs(x_pos - existing_x) < (edge_right - edge_left) * 0.8:
                        if abs(y_pos - existing_y) < min_label_spacing:
                            can_place_label = False
                            break
                if can_place_label:

                    if rotate_labels:
                        ha = "center"
                        va = "bottom"

                        y_pos_rotated = y_pos + max(counts) * 0.02
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
                        fontsize=9,
                        color="black",
                        rotation=label_rotation if rotate_labels else 0
                    )
                    label_positions.append((x_pos, y_pos))

        ax.set_xlabel(xlabel, fontsize=12, fontweight="bold")
        ax.set_ylabel(ylabel, fontsize=12, fontweight="bold")
        ax.set_title(self.title, fontsize=16, fontweight="bold", pad=20)
        ax.grid(True, alpha=0.3, linestyle='-', linewidth=0.5)
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['left'].set_linewidth(0.8)
        ax.spines['bottom'].set_linewidth(0.8)


        ax.yaxis.set_tick_params(labelsize=y_font_size)
        ax.xaxis.set_tick_params(labelsize=x_font_size)
        ax.set_ylim(0, max(counts) * 1.1)
        ax.yaxis.set_major_formatter(FuncFormatter(
            lambda val, _: format_number(val) if abs(val) >= 1000 else f"{val:.{decimal_points}f}"
        ))

        if rotate_x_labels:
            plt.xticks(rotation=x_label_rotation, ha="right")
        plt.tight_layout()
        plt.show()


class MultiHistPlot:
    def __init__(self, title: str):
        self.title = title

    def plot(
        self,
        data_list,
        bins: int = 20,
        xlabel: str = "Values",
        ylabel: str = "Frequency",
        is_percentage: bool = False,
        decimal_points: int = 1,
        figsize=(10, 6),
        label_density: float = 0.3,
        alpha: float = 0.9,
        show_legend: bool = True,
        legend_loc: str = "upper right",
        normalize: bool = False,
        layout: str = "horizontal",
        cols: int = None,
        rows: int = None,
        rotate_labels: bool = False,
        label_rotation: int = 45,
        rotate_x_labels: bool = False,
        x_label_rotation: int = 45,
    ):
        sns.set_theme(style="white", context="talk")


        n_histograms = len(data_list)
        if layout == "horizontal":
            if cols is None:
                cols = min(3, n_histograms)
            rows = (n_histograms + cols - 1) // cols
        else:
            if rows is None:
                rows = min(3, n_histograms)
            cols = (n_histograms + rows - 1) // rows

        if layout == "horizontal":
            figsize = (figsize[0] * cols, figsize[1] * rows)
        else:
            figsize = (figsize[0] * cols, figsize[1] * rows)
        fig, axes = plt.subplots(rows, cols, figsize=figsize)

        if n_histograms == 1:
            axes = [axes]
        elif rows == 1 or cols == 1:
            axes = axes.flatten()
        else:
            axes = axes.flatten()


        base_colors = ["#4c72b0", "#55a3ff", "#2c5aa0", "#1e3d72", "#0f1f3a"]

        all_counts = []
        all_values = []

        for i, data in enumerate(data_list):
            values = data["values"]
            label = data.get("label", f"Dataset {i+1}")
            subtitle = data.get("title", label)
            ax = axes[i]

            hist_color = base_colors[i % len(base_colors)]

            counts, bin_edges, patches = ax.hist(
                values,
                bins=bins,
                color=hist_color,
                edgecolor="white",
                linewidth=1.2,
                alpha=alpha,
                density=normalize
            )
            all_counts.append(counts)
            all_values.extend(values)

            if is_percentage:
                ax.yaxis.set_major_formatter(PercentFormatter(xmax=len(values)))
                subplot_ylabel = "Percentage"
            else:
                ax.yaxis.set_major_formatter(FuncFormatter(
                    lambda val, _: format_number(val)
                ))
                subplot_ylabel = ylabel

            if not normalize:
                total_bars = len([c for c in counts if c > 0])
                labels_to_show = max(1, int(total_bars * label_density))
                bar_indices = [(i, count) for i, count in enumerate(counts) if count > 0]
                bar_indices.sort(key=lambda x: x[1], reverse=True)
                selected_indices = set([i for i, _ in bar_indices[:labels_to_show]])

                label_positions = []
                min_label_spacing = max(counts) * 0.05 if len(counts) > 0 else 1
                for j, (count, edge_left, edge_right) in enumerate(zip(counts, bin_edges[:-1], bin_edges[1:])):
                    if count > 0 and j in selected_indices:
                        display_value = 100*count/len(values) if is_percentage else count
                        if is_percentage:
                            display_text = f"{display_value:.{decimal_points}f}%"
                        else:
                            display_text = f"{format_number(display_value)}"

                        x_pos = (edge_left + edge_right) / 2
                        y_pos = count + max(counts) * 0.01

                        can_place_label = True
                        for existing_x, existing_y in label_positions:
                            if abs(x_pos - existing_x) < (edge_right - edge_left) * 0.8:
                                if abs(y_pos - existing_y) < min_label_spacing:
                                    can_place_label = False
                                    break
                        if can_place_label:

                            if rotate_labels:
                                ha = "center"
                                va = "bottom"

                                y_pos_rotated = y_pos + max(counts) * 0.02
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
                                fontsize=9,
                                fontweight="bold",
                                color="black",
                                rotation=label_rotation if rotate_labels else 0
                            )
                            label_positions.append((x_pos, y_pos))

            ax.set_xlabel(xlabel, fontsize=10, fontweight="bold")
            ax.set_ylabel(subplot_ylabel, fontsize=10, fontweight="bold")
            ax.set_title(subtitle, fontsize=12, fontweight="bold", pad=10)

            ax.grid(True, alpha=0.3, linestyle='-', linewidth=0.5)
            ax.spines['top'].set_visible(False)
            ax.spines['right'].set_visible(False)
            ax.spines['left'].set_linewidth(0.8)
            ax.spines['bottom'].set_linewidth(0.8)

            if len(counts) > 0:
                ax.set_ylim(0, max(counts) * 1.1)

            ax.xaxis.set_major_formatter(FuncFormatter(
                lambda val, _: format_number(val) if abs(val) >= 1000 else f"{val:.{decimal_points}f}"
            ))

            if rotate_x_labels:
                ax.tick_params(axis='x', rotation=x_label_rotation)

        for j in range(n_histograms, len(axes)):
            axes[j].axis("off")

        fig.suptitle(self.title, fontsize=16, fontweight="bold", y=0.98)
        plt.tight_layout(rect=[0, 0, 1, 0.96])
        plt.show()











































































