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
        label_density: float = 1.0,
        
    ):
        sns.set_theme(style="white", context="talk")

        fig, ax = plt.subplots(figsize=figsize)

        # Use consistent color palette with CircularPlot
        base_colors = ["#4c72b0", "#55a3ff", "#2c5aa0", "#1e3d72", "#0f1f3a"]
        # Override the color parameter to use consistent scheme
        hist_color = base_colors[0]  # Use primary color #4c72b0
        
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

        # Anti-overlap label logic
        total_bars = len([c for c in counts if c > 0])
        labels_to_show = max(1, int(total_bars * label_density))
        
        bar_indices = [(i, count) for i, count in enumerate(counts) if count > 0]
        bar_indices.sort(key=lambda x: x[1], reverse=True)
        selected_indices = set([i for i, _ in bar_indices[:labels_to_show]])
        
        # Track label positions to prevent overlap
        label_positions = []
        min_label_spacing = max(counts) * 0.05  # Minimum spacing between labels
        
        for i, (count, edge_left, edge_right) in enumerate(zip(counts, bin_edges[:-1], bin_edges[1:])):
            if count > 0 and i in selected_indices:
                display_value = 100*count/len(values) if is_percentage else count
                
                if is_percentage:
                    display_text = f"{display_value:.{decimal_points}f}%"
                else:
                    display_text = f"{format_number(display_value)}"
                
                # Calculate label position
                x_pos = (edge_left + edge_right) / 2
                y_pos = count + max(counts) * 0.01
                
                # Check for overlap with existing labels
                can_place_label = True
                for existing_x, existing_y in label_positions:
                    if abs(x_pos - existing_x) < (edge_right - edge_left) * 0.8:  # Horizontal overlap check
                        if abs(y_pos - existing_y) < min_label_spacing:  # Vertical overlap check
                            can_place_label = False
                            break
                
                if can_place_label:
                    ax.text(
                        x_pos,
                        y_pos,
                        display_text,
                        ha="center",
                        va="bottom",
                        fontsize=9,
                        fontweight="bold",
                        color="black"
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
        
        ax.set_ylim(0, max(counts) * 1.1)
        
        ax.xaxis.set_major_formatter(FuncFormatter(
            lambda val, _: format_number(val) if abs(val) >= 1000 else f"{val:.{decimal_points}f}"
        ))
        
        plt.tight_layout()
        plt.show()


class MultiHistPlot:
    def __init__(self, title: str):
        self.title = title

    def plot(
        self,
        data_list,  # List of dictionaries with 'values', 'label', and optionally 'title'
        bins: int = 20,
        xlabel: str = "Values",
        ylabel: str = "Frequency",
        is_percentage: bool = False,
        decimal_points: int = 1,
        figsize=(10, 6),
        label_density: float = 0.3,  # Lower density for multiple histograms
        alpha: float = 0.7,  # Transparency for overlapping histograms
        show_legend: bool = True,
        legend_loc: str = "upper right",
        normalize: bool = False,  # Whether to normalize histograms to same scale
    ):
        sns.set_theme(style="white", context="talk")

        fig, ax = plt.subplots(figsize=figsize)

        # Use consistent color palette with CircularPlot
        base_colors = ["#4c72b0", "#55a3ff", "#2c5aa0", "#1e3d72", "#0f1f3a"]
        
        # Track all counts for normalization and label positioning
        all_counts = []
        all_bin_edges = []
        all_values = []
        
        # Plot each histogram
        for i, data in enumerate(data_list):
            values = data["values"]
            label = data.get("label", f"Dataset {i+1}")
            
            # Use color from palette, cycling through if more datasets than colors
            hist_color = base_colors[i % len(base_colors)]
            
            # Calculate histogram
            counts, bin_edges, patches = ax.hist(
                values,
                bins=bins,
                color=hist_color,
                edgecolor="white",
                linewidth=1.2,
                alpha=alpha,
                label=label,
                density=normalize  # Normalize if requested
            )
            
            all_counts.append(counts)
            all_bin_edges.append(bin_edges)
            all_values.extend(values)

        # Set up axis formatting
        if is_percentage:
            ax.yaxis.set_major_formatter(PercentFormatter(xmax=len(all_values)))
            ylabel = "Percentage"
        else:
            ax.yaxis.set_major_formatter(FuncFormatter(
                lambda val, _: format_number(val)
            ))

        # Add labels for the most significant bins across all histograms
        if not normalize:  # Only add labels if not normalized
            # Combine all counts to find most significant bins
            max_counts = [max(counts) for counts in all_counts]
            global_max_count = max(max_counts) if max_counts else 1
            
            # Track label positions across all histograms
            global_label_positions = []
            min_label_spacing = global_max_count * 0.05
            
            for hist_idx, (counts, bin_edges, values) in enumerate(zip(all_counts, all_bin_edges, [d["values"] for d in data_list])):
                # Select bins to label for this histogram
                total_bars = len([c for c in counts if c > 0])
                labels_to_show = max(1, int(total_bars * label_density))
                
                bar_indices = [(i, count) for i, count in enumerate(counts) if count > 0]
                bar_indices.sort(key=lambda x: x[1], reverse=True)
                selected_indices = set([i for i, _ in bar_indices[:labels_to_show]])
                
                # Add labels for this histogram
                for i, (count, edge_left, edge_right) in enumerate(zip(counts, bin_edges[:-1], bin_edges[1:])):
                    if count > 0 and i in selected_indices:
                        display_value = 100*count/len(values) if is_percentage else count
                        
                        if is_percentage:
                            display_text = f"{display_value:.{decimal_points}f}%"
                        else:
                            display_text = f"{format_number(display_value)}"
                        
                        # Calculate label position
                        x_pos = (edge_left + edge_right) / 2
                        y_pos = count + global_max_count * 0.01
                        
                        # Check for overlap with existing labels (across all histograms)
                        can_place_label = True
                        for existing_x, existing_y in global_label_positions:
                            if abs(x_pos - existing_x) < (edge_right - edge_left) * 0.8:  # Horizontal overlap check
                                if abs(y_pos - existing_y) < min_label_spacing:  # Vertical overlap check
                                    can_place_label = False
                                    break
                        
                        if can_place_label:
                            ax.text(
                                x_pos,
                                y_pos,
                                display_text,
                                ha="center",
                                va="bottom",
                                fontsize=8,  # Smaller font for multiple histograms
                                fontweight="bold",
                                color="black"
                            )
                            global_label_positions.append((x_pos, y_pos))

        # Set labels and title
        ax.set_xlabel(xlabel, fontsize=12, fontweight="bold")
        ax.set_ylabel(ylabel, fontsize=12, fontweight="bold")
        ax.set_title(self.title, fontsize=16, fontweight="bold", pad=20)
        
        # Add legend if requested
        if show_legend and len(data_list) > 1:
            ax.legend(loc=legend_loc, frameon=True, fancybox=True, shadow=True)
        
        # Styling
        ax.grid(True, alpha=0.3, linestyle='-', linewidth=0.5)
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['left'].set_linewidth(0.8)
        ax.spines['bottom'].set_linewidth(0.8)
        
        # Set y-axis limits
        if all_counts:
            max_count = max([max(counts) for counts in all_counts if len(counts) > 0])
            ax.set_ylim(0, max_count * 1.1)
        
        # Format x-axis
        ax.xaxis.set_major_formatter(FuncFormatter(
            lambda val, _: format_number(val) if abs(val) >= 1000 else f"{val:.{decimal_points}f}"
        ))
        
        plt.tight_layout()
        plt.show()


# Example usage of MultiHistPlot:
# 
# from src.utils.visualization.HistPlot import MultiHistPlot
# import numpy as np
# 
# # Create sample data
# data1 = np.random.normal(100, 15, 1000)
# data2 = np.random.normal(120, 20, 800)
# data3 = np.random.normal(90, 10, 1200)
# 
# # Prepare data list
# data_list = [
#     {"values": data1, "label": "Dataset 1"},
#     {"values": data2, "label": "Dataset 2"},
#     {"values": data3, "label": "Dataset 3"}
# ]
# 
# # Create and plot
# multi_hist = MultiHistPlot("Multiple Histograms Comparison")
# multi_hist.plot(
#     data_list=data_list,
#     bins=30,
#     xlabel="Values",
#     ylabel="Frequency",
#     figsize=(12, 8),
#     alpha=0.6,
#     show_legend=True,
#     legend_loc="upper right"
# )
