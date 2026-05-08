from collections import defaultdict

import chardet
from bs4 import BeautifulSoup
from dateutil import parser

from common.common import format_datetime, to_float
from core.bt.tools.trader_report_calculate import process_auto_upload, process_manual_upload
from database.db_mysql import async_db_session


class TraderReportSubmitService:
    REPORT_DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"
    MANUAL_UPLOAD_TYPE = "2"
    AUTO_ORDER_TYPES = {"buy", "sell"}

    @classmethod
    def parse_report_time(cls, value):
        return parser.parse(value).strftime(cls.REPORT_DATETIME_FORMAT)

    @staticmethod
    def load_html_soup(file_path):
        with open(file_path, 'rb') as file:
            raw_data = file.read()
            encoding = chardet.detect(raw_data)['encoding'] or "utf-8"

        with open(file_path, 'r', encoding=encoding) as file:
            return BeautifulSoup(file, 'html.parser')

    @staticmethod
    def get_cell_text(cols, index, default=""):
        return cols[index].text.strip() if len(cols) > index else default

    @classmethod
    def build_auto_transaction(cls, cols):
        order_type = cls.get_cell_text(cols, 2).lower()
        if len(cols) < 14 or order_type not in cls.AUTO_ORDER_TYPES:
            return None
        if 'title' not in cols[0].attrs:
            return None

        return {
            'tradeid': cls.get_cell_text(cols, 0, 0),
            'timestamp': format_datetime(cls.get_cell_text(cols, 1)) if len(cols) > 1 else None,
            'openTime': format_datetime(cls.get_cell_text(cols, 1)) if len(cols) > 1 else None,
            'orderType': cls.get_cell_text(cols, 2, '0'),
            'goodsId': cls.get_cell_text(cols, 4, None),
            'size': to_float(cls.get_cell_text(cols, 3)) if len(cols) > 3 else 0.0,
            'openPrice': to_float(cls.get_cell_text(cols, 5)) if len(cols) > 5 else 0.0,
            'stopLoss': to_float(cls.get_cell_text(cols, 6)) if len(cols) > 6 else 0.0,
            'takeProfit': to_float(cls.get_cell_text(cols, 7)) if len(cols) > 7 else 0.0,
            'closeTime': format_datetime(cls.get_cell_text(cols, 8)) if len(cols) > 8 else None,
            'price': to_float(cls.get_cell_text(cols, 9)) if len(cols) > 9 else 0.0,
            'commission': to_float(cls.get_cell_text(cols, 10)) if len(cols) > 10 else 0.0,
            'taxes': to_float(cls.get_cell_text(cols, 11)) if len(cols) > 11 else 0.0,
            'swap': to_float(cls.get_cell_text(cols, 12)) if len(cols) > 12 else 0.0,
            'pnl': to_float(cls.get_cell_text(cols, 13)) if len(cols) > 13 else 0.0,
            "keyid": cls.get_cell_text(cols, 2)
        }

    @classmethod
    def extract_auto_grouped_transactions(cls, soup):
        transactions = []
        identifiers = []

        for row in soup.find_all('tr', align='right'):
            cols = row.find_all('td')
            transaction = cls.build_auto_transaction(cols)
            if transaction:
                transactions.append(transaction)
            elif len(cols) == 3:
                identifiers.append(cls.get_cell_text(cols, 2))

        grouped_transactions = defaultdict(list)
        for transaction, identifier in zip(transactions, identifiers):
            key = identifier.split('@')[0]
            transaction['identifier'] = identifier
            grouped_transactions[key].append(transaction)

        return grouped_transactions

    @staticmethod
    async def run_manual_upload_task(soup, data_json, strategy, startTime, endTime, uid, goods, period, upload_type):
        async with async_db_session() as db:
            await process_manual_upload(
                soup, data_json, strategy, startTime, endTime, uid, goods, period, db, upload_type
            )

    @staticmethod
    async def run_auto_upload_task(soup, grouped_transactions, startTime, endTime):
        async with async_db_session() as db:
            await process_auto_upload(soup, db, grouped_transactions, startTime, endTime)
