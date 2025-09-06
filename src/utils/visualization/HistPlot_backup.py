import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter, PercentFormatter
import seaborn as sns
import numpy as np

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
        figsize=(8,6)
    ):
        sns.set_theme(style="white", context="talk")

        fig, ax = plt.subplots(figsize=figsize)

        counts, bin_edges, patches = ax.hist(
            values,
            bins=bins,
            color=color,
            edgecolor="white",
            linewidth=1.2,
            alpha=0.9
        )

        if is_percentage:
            ax.yaxis.set_major_formatter(PercentFormatter(xmax=len(values)))
            ylabel = "Percentage"

        for count, edge_left, edge_right in zip(counts, bin_edges[:-1], bin_edges[1:]):
            if count > 0:
                ax.text(
                    (edge_left + edge_right) / 2,
                    count,
                    f"{count:,.{decimal_points}f}" if not is_percentage else f"{100*count/len(values):.{decimal_points}f}%",
                    ha="center",
                    va="bottom",
                    fontsize=9,
                )

        ax.set_xlabel(xlabel, fontsize=12)
        ax.set_ylabel(ylabel, fontsize=12)
        ax.set_title(self.title, fontsize=16, fontweight="bold")
        ax.yaxis.set_major_formatter(FuncFormatter(
            lambda val, _:
                f"{val:.{decimal_points}f} %" if is_percentage else f"{float(val):,.{decimal_points}f}",
        ))
        plt.tight_layout()
        plt.show()
