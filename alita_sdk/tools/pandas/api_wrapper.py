# -*- coding: utf-8 -*-
# This one is heavily inspired by the pandasai library
# 

import csv
from io import StringIO, BytesIO
from typing import Any, Optional
import traceback
import os
import base64
from uuid import uuid4
import chardet
import logging
import pandas as pd
from pydantic import create_model, Field, model_validator

from ..elitea_base import BaseToolApiWrapper
from .dataframe.serializer import DataFrameSerializer
from .dataframe.generator.base import CodeGenerator
from .dataframe.executor.code_executor import CodeExecutor
from langchain_core.callbacks import dispatch_custom_event
from traceback import format_exc

logger = logging.getLogger(__name__)

class PandasWrapper(BaseToolApiWrapper):
    alita: Any = None
    llm: Any = None
    bucket_name: str
    
    _length_to_sniff: int = 1024


    def bytes_content(self, content: Any, filename: str) -> bytes:
        """
        Returns the content of the file as bytes
        """
        if not content:
            content = self.alita.download_artifact(self.bucket_name, filename)
        if isinstance(content, bytes):
            return content
        return content.encode('utf-8')

    def _get_csv_delimiter(self, data: str) -> str:
        """ Get the delimiter of the CSV file. """
        sniffer = csv.Sniffer()
        dialect = sniffer.sniff(data[0:self._length_to_sniff])
        return dialect.delimiter
    
    def _get_dataframe(self, filename: str) -> pd.DataFrame | None:
        """ Get the dataframe from various file formats. """
            
        # Generate df_name from filename by removing extension
        df_name = os.path.splitext(filename)[0]
        
        # Check if df_name exists in artifacts
        artifacts = self.alita.list_artifacts(self.bucket_name)
        df_exists = False
        if artifacts and 'rows' in artifacts:
            df_exists = any(artifact['name'] == df_name for artifact in artifacts['rows'])
        
        df = None
        if df_exists:
            try:
                _df = self.alita.download_artifact(self.bucket_name, df_name)
                if isinstance(_df, bytes):
                    from io import BytesIO
                    df = pd.read_pickle(BytesIO(_df))
                    return df
            except Exception as e:
                logger.warning(f"Failed to load dataframe from {df_name}: {e}")
                df = None
        
        # Fall back to reading the original file
        try:
            from io import BytesIO
            
            # Download the file directly
            file_content = self.alita.download_artifact(self.bucket_name, filename)
            
            # Get file extension to determine how to load the file
            _, file_extension = os.path.splitext(filename.lower())
            file_extension = file_extension.lstrip('.')
            
            # Create BytesIO object from file content if it's bytes
            if isinstance(file_content, bytes):
                file_obj = BytesIO(file_content)
            else:
                # Convert string to bytes if needed
                file_obj = BytesIO(file_content.encode('utf-8'))
                
            # Handle different file formats using pandas' built-in functionality
            if file_extension in ['csv', 'txt']:
                df = pd.read_csv(file_obj)
            elif file_extension in ['xlsx', 'xls']:
                df = pd.read_excel(file_obj, engine='calamine')
            elif file_extension == 'parquet':
                df = pd.read_parquet(file_obj)
            elif file_extension == 'json':
                df = pd.read_json(file_obj)
            elif file_extension == 'xml':
                df = pd.read_xml(file_obj)
            elif file_extension in ['h5', 'hdf5']:
                df = pd.read_hdf(file_obj)
            elif file_extension == 'feather':
                df = pd.read_feather(file_obj)
            elif file_extension in ['pickle', 'pkl']:
                df = pd.read_pickle(file_obj)
            else:
                # Default to CSV for unknown formats
                logging.warning(f"Unknown file format: {file_extension}, attempting to read as CSV")
                df = pd.read_csv(file_obj)
                
        except Exception as e:
            logger.error(f"Failed to read file {filename}: {format_exc()}")
            raise
                
        return df
    
    def _save_dataframe(self, df: pd.DataFrame, filename: str) -> None:
        """ Save the dataframe to the artifact repo. """
        # Generate df_name from filename by removing extension
        df_name = os.path.splitext(filename)[0]
        
        from io import BytesIO
        bytes_io = BytesIO()
        df.to_pickle(bytes_io)
        respone = self.alita.create_artifact(self.bucket_name, df_name, bytes_io.getvalue())
        return respone    
        
    def execute_code(self, df: Any, code: str) -> str:
        """Execute the generated code and return the result."""
        executor = CodeExecutor()
        def get_dataframe():
            return df
        executor.add_to_env("get_dataframe", get_dataframe)
        return executor.execute_and_return_result(code)
    
    def generate_code_with_retries(self, df: Any, query: str) -> Any:
        """Execute the code with retry logic."""
        max_retries = 5
        attempts = 0
        codegen = CodeGenerator(df=df, df_description=DataFrameSerializer.serialize(df), llm=self.llm)
        try:
            return codegen.generate_code(query, None)
        except Exception as e:
            error_trace = traceback.format_exc()
            while attempts <= max_retries:
                try:
                    return codegen.generate_code(query, error_trace)
                except Exception as e:
                    attempts += 1
                    error_trace = traceback.format_exc()
                    if attempts > max_retries:
                        logger.info(f"Maximum retry attempts exceeded. Last error: {e}")
                        raise
                    logger.info(
                        f"Retrying Code Generation ({attempts}/{max_retries})..."
                    )
    
    def process_query(self, query: str, filename: str) -> str:
        """Analyze and process using query on dataset""" 
        df = self._get_dataframe(filename)
        code = self.generate_code_with_retries(df, query)
        self._log_tool_event(tool_name="process_query",
                             message=f"Executing generated code... \n\n```python\n{code}\n```")
        try:
            result = self.execute_code(df, code)
        except Exception as e:
            logger.error(f"Code execution failed: {format_exc()}")
            self._log_tool_event(tool_name="process_query",
                                 message=f"Executing generated code... \n\n```python\n{code}\n```")
            raise
        self._log_tool_event(tool_name="process_query",
                             message=f"Executing generated code... \n\n```python\n{code}\n```")
        if result.get("df") is not None:
            df = result.pop("df")
            # Not saving dataframe to artifact repo for now
            # self._save_dataframe(df, filename)
        if result.get('chart'):
            if isinstance(result['chart'], list):
                for ind, chart in enumerate(result['chart']):
                    chart_filename = f"chart_{uuid4()}.png"
                    chart_data = base64.b64decode(chart)
                    self.alita.create_artifact(self.bucket_name, chart_filename, chart_data)
                    result['result'] = f"Chart #{ind} saved to {chart_filename}"
            else:
                # Handle single chart case (not in a list)
                chart = result['chart']
                chart_filename = f"chart_{uuid4()}.png"
                chart_data = base64.b64decode(chart)
                self.alita.create_artifact(self.bucket_name, chart_filename, chart_data)
                result['result'] = f"Chart saved to {chart_filename}"
        return result.get("result", None)

    def save_dataframe(self, source_df: str, target_file: str) -> str:
        """Save the dataframe to a file in the artifact repo with the specified format.
        
        Args:
            source_df: Name of the source dataframe file
            target_file: Name of the target file with extension
        
        Returns:
            Confirmation message with details of saved file
        """
        df = self._get_dataframe(source_df)
        if df is None:
            raise ValueError(f"Could not load dataframe from {source_df}")
            
        ext = os.path.splitext(target_file)[1].lower()
        
        # For text-based formats, use StringIO
        if ext in ['.csv', '.json', '.txt']:
            buffer = StringIO()
            if ext == '.csv':
                df.to_csv(buffer, index=False)
            elif ext == '.json':
                df.to_json(buffer, orient="records", lines=True)
            elif ext == '.txt':
                buffer.write(str(df))
                
            content = buffer.getvalue().encode("utf-8")
        
        # For binary formats, use BytesIO
        else:
            from io import BytesIO
            buffer = BytesIO()
            
            if ext == '.xlsx':
                df.to_excel(buffer, index=False)
            elif ext == '.parquet':
                df.to_parquet(buffer)
            elif ext in ['.pickle', '.pkl']:
                df.to_pickle(buffer)
            elif ext == '.feather':
                df.to_feather(buffer)
            elif ext in ['.h5', '.hdf5']:
                df.to_hdf(buffer, key='df', mode='w')
            else:
                # Default to pickle for unknown formats
                df.to_pickle(buffer)
                
            content = buffer.getvalue()
        
        response = self.alita.create_artifact(
            self.bucket_name,
            target_file,
            content
        )
        
        return f"Successfully saved dataframe to {target_file} in {self.bucket_name} with response: {response}"

    def get_available_tools(self):
        return [
            {
                "name": "process_query",
                "ref": self.process_query,
                "description": self.process_query.__doc__,
                "args_schema": create_model(
                    "ProcessQueryModel",
                    query=(str, Field(description="Task to solve")),
                    filename=(str, Field(description="File to be processed"))
                )
            },
            {
                "name": "save_dataframe",
                "ref": self.save_dataframe,
                "description": self.save_dataframe.__doc__,
                "args_schema": create_model(
                    "SaveDataFrameModel",
                    source_df=(str, Field(description="Source dataframe file to be saved")),
                    target_file=(str, Field(description="Target filename with extension for saving"))
                )
            }
        ]