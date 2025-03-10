import asyncio
import logging
import json
import os
import time
import pandas as pd
import zipfile
import fcntl  # Unix용 모듈-윈도우에서 실행시 주석처리 필요
from auth import create_broker


# 증권 API 브로커 생성
broker = create_broker()
CACHE_DURATION = 60
STOCK_CODES = [
    "005930", "000660", "005380", "035420", "207940", "051910", "068270", "000270",
    "105560", "012330", "036570", "015760", "055550", "017670", "018260", "032830",
    "066570", "003550", "030200", "086790"
]

def safe_open_file(filepath, mode='r'):
    for _ in range(10):  # 최대 10번 시도
        try:
            file = open(filepath, mode)
            if os.name == 'nt':  # Windows
                msvcrt.locking(file.fileno(), msvcrt.LK_NBLCK, os.path.getsize(filepath))
            else:  # Unix
                fcntl.flock(file, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return file
        except FileNotFoundError:
            logging.error(f"파일을 찾을 수 없습니다: {filepath}")
            return None
        except (BlockingIOError, OSError):
            logging.warning(f"파일 잠금 대기 중: {filepath}")
            time.sleep(1)
    logging.error(f"파일 접근 실패: {filepath}")
    return None

def safe_close_file(file):
    try:
        if os.name == 'nt':  # Windows
            msvcrt.locking(file.fileno(), msvcrt.LK_UNLCK, os.path.getsize(file.name))
        else:  # Unix
            fcntl.flock(file, fcntl.LOCK_UN)
        file.close()
    except Exception as e:
        logging.error(f"파일 닫기 실패: {e}")

def initialize_broker_and_symbols():
    broker = create_broker()
    symbols = broker.fetch_symbols()
    symbols.set_index('단축코드', inplace=True)
    return broker, symbols

async def fetch_stock_data(code, broker, symbols, redis_client_stock=None):
    """
    종목 데이터를 가져오는 함수 (호가 포함)
    """
    try:
        resp = broker.fetch_price(code)
        output = resp.get("output", {})

        if not output:
            logging.error(f"가격 데이터 없음: {code}")
            return None

        name = symbols.loc[code, '한글명'] if code in symbols.index else '알 수 없음'
        
        # OHLCV 데이터 가져오기
        ohlcv_resp = broker.fetch_ohlcv(symbol=code, timeframe='D', adj_price=True)
        price_history = ohlcv_resp.get('output2', [])

        # OHLCV 필드 추가
        stock_data = {
            "name": name,
            "code": code,
            "price": int(output.get("stck_prpr", 0)),
            "open": int(output.get("stck_oprc", 0)),  # ✅ Open price 추가
            "high": int(output.get("stck_hgpr", 0)),  # ✅ High price 추가
            "low": int(output.get("stck_lwpr", 0)),  # ✅ Low price 추가
            "close": int(output.get("stck_clpr", 0)),  # ✅ Close price 추가
            "volume": int(output.get("acml_vol", 0)),  # ✅ Volume 추가
            "previous_close": int(output.get("stck_sdpr", 0)),
            "price_history": price_history
        }

        stock_data["change"] = stock_data["price"] - stock_data["previous_close"]
        stock_data["percent_change"] = round(
            (stock_data["change"] / stock_data["previous_close"]) * 100, 2
        ) if stock_data["previous_close"] != 0 else 0

        if redis_client_stock:
            redis_client_stock.set(f'stock_data:{code}', json.dumps(stock_data), ex=CACHE_DURATION)

        return stock_data

    except Exception as e:
        logging.error(f"Error fetching stock data for code {code}: {e}")
        return None



async def fetch_all_stock_data(redis_client_stock=None):
    broker, symbols = initialize_broker_and_symbols()
    semaphore = asyncio.Semaphore(30)  # 동시에 최대 30개의 작업만 실행되도록 제한

    async def limited_fetch_stock_data(code):
        async with semaphore:
            return await fetch_stock_data(code, broker, symbols, redis_client_stock)

    tasks = [limited_fetch_stock_data(code) for code in STOCK_CODES]
    results = await asyncio.gather(*tasks)
    stock_data_list = [result for result in results if result is not None]
    return stock_data_list

def fetch_chart_data(symbol, timeframe):
    try:
        if timeframe == "1m":
            result = broker.fetch_today_1m_ohlcv(symbol)
        elif timeframe in ["D", "M"]:
            result = broker.fetch_ohlcv(symbol, timeframe=timeframe)
        else:
            raise ValueError("Invalid timeframe")

        data = result.get("output2", [])  # "output2"로 변경
        if not data:
            raise ValueError(f"No data found for symbol: {symbol}")

        df = pd.DataFrame(data)
        required_columns = {
            "stck_oprc": "open",
            "stck_hgpr": "high",
            "stck_lwpr": "low",
            "stck_clpr": "close",
            "acml_vol": "volume",
            "stck_bsop_date": "datetime"
        }

        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            raise ValueError(f"Missing columns in data: {missing_columns}")

        df.rename(columns=required_columns, inplace=True)
        df["datetime"] = pd.to_datetime(df["datetime"], format="%Y%m%d")
        df.set_index("datetime", inplace=True)
        df = df[["open", "high", "low", "close", "volume"]].sort_index()

        return {
            "timestamps": df.index.strftime('%Y-%m-%d %H:%M:%S').tolist(),
            "open": df["open"].tolist(),
            "high": df["high"].tolist(),
            "low": df["low"].tolist(),
            "close": df["close"].tolist(),
            "volume": df["volume"].tolist()
        }

    except Exception as e:
        logging.error(f"Error fetching chart data: {e}")
        return str(e)


async def fetch_merged_stock_data(code, redis_client_stock=None):
    try:
        broker, symbols = initialize_broker_and_symbols()
        stock_data = await fetch_stock_data(code, broker, symbols, redis_client_stock)

        if stock_data:
            chart_data = fetch_chart_data(code, 'D')
            if isinstance(chart_data, str):  # 오류 발생 시 기본값 할당
                logging.error(f"❌ Chart data fetch failed for {code}")
                stock_data["chart_data"] = {
                    "timestamps": [],
                    "open": [],
                    "high": [],
                    "low": [],
                    "close": [],
                    "volume": []
                }
            else:
                stock_data["chart_data"] = chart_data

            return stock_data

    except Exception as e:
        logging.error(f"Error fetching merged stock data for code {code}: {e}")
        return None

