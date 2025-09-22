from pyspark.ml import Pipeline
from pyspark.ml.feature import Tokenizer, StopWordsRemover, Normalizer, RegexTokenizer
import pyspark.sql.functions as F
import re
from typing import Dict, List, Optional

class CleanWords:
    def __init__(self):
        pass

    def _get_tokenizer(self, input_column, output_column):
        return (
            Tokenizer()
                .setInputCol(input_column)
                .setOutputCol(output_column)
        )

    def _get_stop_words_remover(self, input_column, output_column):
        return (
            StopWordsRemover()
                .setInputCol(input_column)
                .setOutputCol(output_column)
        )
    
    def _get_normalizer(self, input_column, output_column):
        return (
            Normalizer()
                .setInputCol(input_column)
                .setOutputCol(output_column)
                .setP(2.0)
        )
    
    def _get_regex_tokenizer(self, input_column, output_column, pattern=r"\W+"):
        return (
            RegexTokenizer()
                .setInputCol(input_column)
                .setOutputCol(output_column)
                .setPattern(pattern)
                .setGaps(True)
        )

    def _normalize_text_with_functions(self, df, input_column, output_column):
        return df.withColumn(
            output_column,
            F.lower(F.regexp_replace(F.col(input_column), "[^a-zA-Z0-9\\s]", " "))
        )
    

    def transform_default_no_tokenization(self, df, input_column, output_column):
        df = df.withColumn(output_column, F.col(input_column))
        clean_html = self.clean_html(
            df,
            output_column
        )
        clean_emojis = self.separate_emojis(
            clean_html,
            output_column
        )
        return clean_emojis

    def transform_default_no_normalization(self, df, input_column, pre_tokenized_column, output_column):
        df = df.withColumn(pre_tokenized_column, F.col(input_column))
        clean_html = self.clean_html(
            df,
            pre_tokenized_column
        )
        clean_emojis = self.separate_emojis(
            clean_html,
            pre_tokenized_column
        )
        clean_tokenized = self.tokenize(
            clean_emojis,
            input_column=pre_tokenized_column, output_column = output_column
        )
        return clean_tokenized

    def transform_default_with_normalization(
        self, 
        df, 
        input_column, 
        pre_tokenized_column, 
        output_column
    ):
        df = df.withColumn(pre_tokenized_column, F.col(input_column))
        clean_html = self.clean_html(
            df,
            pre_tokenized_column
        )
        clean_emojis = self.separate_emojis(
            clean_html,
            pre_tokenized_column
        )
        clean_tokenized = self.tokenize(
            clean_emojis,
            input_column=pre_tokenized_column, output_column = output_column
        )
        clean_normalization = self.normalize_text(
            clean_tokenized,
            pre_tokenized_column
        )
        
        return clean_normalization
        
    def tokenize(self, df, input_column, output_column):
        tokenizer = self._get_tokenizer(input_column, output_column)
        tokenized = tokenizer.transform(df)
        tokenized = tokenized.withColumn(
            output_column,
            F.transform(F.col(output_column), lambda x: F.trim(x))
        ).withColumn(
            output_column,
            F.filter(F.col(output_column), lambda x: x != "")
        )

        return tokenized
    def remove_stop_words(self, df, input_column, output_column):
        remover = self._get_stop_words_remover(input_column, output_column)
        cleaned = remover.transform(df)
        return cleaned

    def clean_html(self, df, column_name):
        return df.withColumn(column_name, F.regexp_replace(F.col(column_name), "<[^>]+>", " "))

    def normalize_text(self, df, column_name):
        cleaned = self._normalize_text_with_functions(df, column_name, column_name)
        return cleaned
    
    def spelling_correction(self, df, input_column, output_column):
        return df.withColumn(output_column, F.col(input_column))
 
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
                F.col(column_name),
                emoji_pattern, r" $1 "
            ))
        )
        return result_df
    
