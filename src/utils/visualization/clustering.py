from pyspark.sql import DataFrame
from matplotlib import pyplot as plt

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
        cluster_distribution['count']
    )
    plt.title(title)
    plt.xlabel(xlabel)
    plt.ylabel(ylabel)
    plt.show()