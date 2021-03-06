import s3fs
import slate3k
import logging
from tqdm import tqdm
# from boto3 import Session
import os
import pandas as pd
import json
from typing import Tuple, Dict, Optional


logger = logging.getLogger(__name__)


class DocumentScraper:
    """
    This class has methods for scraping all the files with '.pdf' extension within a given folder, cleaning the text,
    and generating a pd.DataFrame where:
        - each column contains the text of a separate pdf file (column name is pdf title without extension), and
        - each row within a column contains the text of one page within that pdf.
    If different pdf files have different number of pages, any empty rows at the bottom of a column are filled with nan.
    It also offers support for folders stored in the cloud (AWS S3 buckets only).
    """
    def __init__(self, path: str, json_filename: Optional[str] = None, from_s3_bucket: bool = False) -> None:
        """
        :param path: path to the folder containing pdf files to be scraped. Can also be an S3 bucket (see below).
        :param json_filename: full path of the json file created by the module json_creator.py. This json file
               contains dictionary of words to replace (e.g. Dr. --> Dr), used for text cleaning. Defaults to None, in
               which case no ad-hoc text cleaning will be performed.
        :param from_s3_bucket: a boolean specifying whether to scrape the PDFs from a folder located in an AWS S3
               bucket. If set to True, the path can either start with "s3://" or omit this prefix. Default: False.
        """
        self.path = path
        self.open_json = self._read_config(json_filename)
        self.from_s3_bucket = from_s3_bucket


    @staticmethod
    def _read_config(json_filename: Optional[str]) -> Dict[str, str]:
        """
        :param json_filename: json filename to be deserialized.
        :return: the dictionary from json object. If json_filename is None, and empty dictionary will be returned.
        """
        if json_filename is None:
            logger.warning('No .json file for text cleaning was provided. Ad-hoc text cleaning will not be performed.')
            return dict()
        logger.info(f'Reading {json_filename} file for text cleaning.')
        assert '.json' in json_filename, 'The json_filename provided does not correspond to a .json file.'
        with open(json_filename, 'r') as file:
            return json.load(file)

    def _text_to_series_of_pages(self, pdf_name: str = "") -> Tuple[pd.Series, int]:
        """
        :param pdf_name: full name of pdf (including .pdf extension) to be scraped and converted into a pd.Series
        :return: document_series: a pd.Series where each row contains the text of one pdf page.
                 num_pages: int, the number of pages of the input pdf file
        """
        document_series = pd.Series()
        pdf = open(os.path.join(self.path), 'rb')
        pdf_reader = slate3k.PDF(pdf)
        num_pages = len(pdf_reader)
        for i, page in enumerate(pdf_reader):
            logger.debug(f'Reading page {i+1} of PDF file {pdf_name}')
            page_text = self._clean_text(page)
            page_series = pd.Series(page_text)
            document_series = document_series.append(page_series, ignore_index=True)
        pdf.close()

        return document_series, num_pages

    def _clean_text(self, text: str) -> str:
        """
        :param text: the text to be cleaned. This replaces certain words based on the dict self.open_json
        :return: text: the cleaned text.
        """
        for k, v in self.open_json.items():
            text = text.replace(k, v)
        text = text.strip()
        return text

    def document_corpus_to_pandas_df(self) -> pd.DataFrame:
        """
        This method can be called by the user to generate the final pd.DataFrame as described in class docstring.
        :return: df: a pd.DataFrame. See class docstring.
        """
        df = pd.DataFrame()
        if not os.path.exists(self.path):
            logger.warning(
                f'\nThe following files were present in the directory {self.path}, but were not scraped as they '
                f'are not in .pdf format: \n{self.path}'
            )
            return df
        logger.info('Starting scraping PDFs...')
        file = self.path
        # sorted is so pdfs are extracted in alphabetic order, and to make testing more robust.
        series, num_pages = self._text_to_series_of_pages(file)
        if isinstance(series, pd.Series):
            series.rename(str(file).replace('.pdf', ''), inplace=True)
            df = pd.concat([df, series], axis=1)
        return df
