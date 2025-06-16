import json
from pandas import DataFrame


class DataFrameSerializer:
    MAX_COLUMN_TEXT_LENGTH = 200

    @classmethod
    def serialize(cls, df: DataFrame) -> str:
        """
        Convert df to a CSV-like format wrapped inside <table> tags, truncating long text values, and serializing only a subset of rows using df.head().

        Args:
            df (pd.DataFrame): Pandas DataFrame

        Returns:
            str: Serialized DataFrame string
        """
        # Start building the table metadata
        table_name = getattr(df, 'name', 'DataFrame')
        dataframe_info = f'<table table_name="{table_name}"'

        # Add description attribute if available
        description = getattr(df, 'description', None)
        if description is not None:
            dataframe_info += f' description="{description}"'

        # Get dimensions using pandas properties
        rows_count = len(df)
        columns_count = len(df.columns)
        dataframe_info += f' dimensions="{rows_count}x{columns_count}">'

        # Truncate long values
        df_truncated = cls._truncate_dataframe(df.head())

        # Convert to CSV format
        dataframe_info += f"\n{df_truncated.to_csv(index=False)}"

        # Close the table tag
        dataframe_info += "</table>\n"

        return dataframe_info

    @classmethod
    def _truncate_dataframe(cls, df: DataFrame) -> DataFrame:
        """Truncates string values exceeding MAX_COLUMN_TEXT_LENGTH, and converts JSON-like values to truncated strings."""

        def truncate_value(value):
            if isinstance(value, (dict, list)):  # Convert JSON-like objects to strings
                value = json.dumps(value, ensure_ascii=False)

            if isinstance(value, str) and len(value) > cls.MAX_COLUMN_TEXT_LENGTH:
                return f"{value[: cls.MAX_COLUMN_TEXT_LENGTH]}…"
            return value

        # Use applymap safely in case of future pandas deprecation
        return df.map(truncate_value) if hasattr(df, 'map') else df.applymap(truncate_value)