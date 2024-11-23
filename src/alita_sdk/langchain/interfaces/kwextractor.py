# Copyright (c) 2023 Artem Rozumenko
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from typing import Optional
from keybert import KeyBERT

class BertKeyphraseExtractor:
    kw_strategy_settings = {
        'naked': {
            'top_n': 10
        },
        'max_sum': {
            'keyphrase_ngram_range': (2, 3),
            'use_maxsum': True,
            'nr_candidates': 20,
            'top_n': 10
        },
        'max_mmr_high': {
            'keyphrase_ngram_range': (2, 3),
            'use_mmr': True,
            'diversity': 0.7,
            'top_n': 10
        },
        'max_mmr_low': {
            'keyphrase_ngram_range': (1, 3),
            'use_mmr': True,
            'diversity': 0.2,
            'top_n': 10
        }
    }

    def __init__(self, kw_strategy='max_sum'):
        self.kw_model = KeyBERT()
        self.kw_strategy = kw_strategy
    
    def extract_keywords(self, text):
        kws = self.kw_model.extract_keywords(text, **self.kw_strategy_settings[self.kw_strategy])
        if kws:
            return [x[0] for x in kws]
        else:
            return []


_classmap = {
    'Bert': BertKeyphraseExtractor
}


class KWextractor:
    def __init__(self, kw_extractor_name: Optional[str], kw_extractor_params: Optional[dict]) -> None:
        self.extractor = None
        if kw_extractor_name and kw_extractor_name in _classmap.keys():
            self.extractor = _classmap[kw_extractor_name](**kw_extractor_params)
    
    def extract_keywords(self, text: str) -> Optional[list]:
        if self.extractor:
            return self.extractor.extract_keywords(text)
        return []


