from pyspark.sql import DataFrame
from matplotlib import pyplot as plt

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
plt.rcParams['font.family'] = 'Times New Roman'
plt.rcParams['axes.labelsize'] = 12
plt.rcParams['axes.titlesize'] = 14
plt.rcParams['xtick.labelsize'] = 10
plt.rcParams['ytick.labelsize'] = 10
plt.rcParams['legend.fontsize'] = 10
plt.rcParams['figure.titlesize'] = 16

def plot_cluster_distribution(
    df: DataFrame, column: str,
    title: str = 'Distribución de tamaño de clusters',
    xlabel: str = 'ID de cluster',
    ylabel: str = 'Número de items'
) -> None:
    cluster_distribution = (
        df
            .groupBy(column)
            .count()
            .orderBy(column)
        ).toPandas()

    plt.figure(figsize=(12, 6))
    plt.bar(
        cluster_distribution[column],
        cluster_distribution['count'],
        color=COLD_COLOR_PALETTE[0],
        edgecolor="white",
        linewidth=1.2,
        alpha=0.9
    )
    plt.title(title, fontsize=16, fontweight="bold")
    plt.xlabel(xlabel, fontsize=12, fontweight="bold")
    plt.ylabel(ylabel, fontsize=12, fontweight="bold")
    plt.show()