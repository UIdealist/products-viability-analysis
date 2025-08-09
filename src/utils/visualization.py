import math
import matplotlib.pyplot as plt

def plot_percentage_matrix_focus_category(
        data,
        title, target_index = 0, label_index = 1,
        target_color = "#4CAF50", others_color = "#E0E0E0"
    ):
    n = len(data)
    cols = min(3, n)
    rows = math.ceil(n / cols)

    fig, axes = plt.subplots(rows, cols, figsize=(3*cols, 3*rows))
    axes = axes.flatten() if n > 1 else [axes]

    for i, d in enumerate(data):
        target = d[target_index]
        category = d[label_index]

        total = sum([
            d[i] for i in range(len(d))
                if i != label_index
        ])
        ax = axes[i]

        pct = target / total if total > 0 else 0

        ax.pie(
            [pct, 1 - pct],
            colors=[target_color, others_color],
            startangle=90,
            counterclock=False,
            wedgeprops={'linewidth': 1, 'edgecolor': 'white'}
        )

        ax.set_title(f"{category} ({pct*100:.1f}%)", fontsize=12)

        ax.set_aspect('equal')

    for j in range(i+1, len(axes)):
        axes[j].axis("off")

    fig.suptitle(title, fontsize=16, fontweight="bold", y=1.02)
    plt.tight_layout()
    plt.show()