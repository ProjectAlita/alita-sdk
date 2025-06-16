import os 

PLAN_CODE_PROMPT = """
<dataframe>
{dataframe}
</dataframe>


You are already provided with the following functions that you can call:
{prompt_addon}

You have access to following libraries:
```
- pandas as pd              Data manipulation library for structured data analysis with DataFrame objects
- numpy as np              # Numerical computing library for efficient array operations and mathematical functions
- matplotlib.pyplot as plt # Data visualization library for creating static, interactive, and animated plots
- scipy.stats as ss        # Statistical functions and probability distributions
- statsmodels.api as sm    # Main API interface for statsmodels offering regression and statistical models
- factor_analyzer          # Tool for factor analysis to identify latent variables in multivariate data
- sklearn                  # Machine learning library with tools for classification, regression, clustering, etc.
- base64                   # Encoding binary data as ASCII strings for transferring/storing binary data as text
- io.BytesIO               # In-memory binary stream for treating bytes as file-like objects without disk I/O
- statsmodels              # Statistical modeling and hypothesis testing library
```

---- 

Update this initial code:
```python
# You can use all these libraries in your code
from typing import List, Optional
import pandas as pd 
import matplotlib.pyplot as plt 
import numpy as np
import scipy.stats as ss 
import statsmodels 
import statsmodels.api as sm 
import factor_analyzer 
import sklearn 
import base64 
from io import BytesIO

df = get_dataframe() 

# Write code here 

```

<user_task>
{task}
</user_task>

CODE GENERATION INSTRUCTIONS:
Do not invent column names by yourself, functions that transforms columns (like convert_str_column_to_categorical, label_based_on_bins, etc.) returns column names they created

CHART GENERATION INSTRUCTIONS:
When creating a chart, provide base64 encoded image as a string in the result dictionary with key "chart" and explanation what it is in result dictionary with key "result".
To save charts you must use BytesIO() buffers
Delete file after transforming it to base64 string.
If you need to have multiple charts, put them as a list in the result dictionary with key "chart" and explanation what they are in result dictionary with key "result".

IMPORTANT: Avoid using comments in code, they may cause validation errors.
IMPORTANT: Avoid using __main__ or __name__ == "__main__" in the code.
IMPORTANT: return dataset as "df" key in the result dictionary.
IMPORTANT: last link of the code should start with `result = dict(df = df, result=<result of user task computation>)`

Generate python code and return full updated code:
"""

DEFAULT_CHART_DIRECTORY = os.path.join("charts")
if not os.path.exists(DEFAULT_CHART_DIRECTORY):
    os.makedirs(DEFAULT_CHART_DIRECTORY)