from pyspark.ml.feature import Tokenizer, StopWordsRemover
import pyspark.sql.functions as F

class CleanWords:
    def __init__(self):
        pass

    def tokenize(self, df, input_column, output_column):
        tokenizer = Tokenizer(
            inputCol=input_column,
            outputCol=output_column
        )
        tokenized = tokenizer.transform(df)
        return tokenized
    
    def remove_stop_words(self, df, input_column, output_column):
        remover = StopWordsRemover(
            inputCol=input_column,
            outputCol=output_column
        )
        cleaned = remover.transform(df)
        return cleaned

    def clean_html(self, df, column_name):
        return df.withColumn(column_name, F.regexp_replace(F.col(column_name), "<[^>]+>", " "))
    
    def separate_emojis(self, df, column_name):
        emoji_pattern = (
            "(["
            "\\x{1F300}-\\x{1F5FF}"
            "\\x{1F600}-\\x{1F64F}"
            "\\x{1F680}-\\x{1F6FF}"
            "\\x{1F700}-\\x{1F77F}"
            "\\x{1F780}-\\x{1F7FF}"
            "\\x{1F800}-\\x{1F8FF}"
            "\\x{1F900}-\\x{1F9FF}"
            "\\x{1FA70}-\\x{1FAFF}"
            "\\x{2600}-\\x{26FF}" 
            "\\x{2700}-\\x{27BF}"
            "])"
        )

        result_df = df.withColumn(
            column_name,
            F.trim(F.regexp_replace(
                F.concat(F.lit(" 😊"), F.col(column_name), F.lit("😊")), 
                emoji_pattern, r" $1 "
            ))
        )
        
        return result_df
