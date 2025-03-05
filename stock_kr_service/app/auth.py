import os
import mojito
import logging

logger = logging.getLogger(__name__)

def create_broker():
    key_path = os.getenv("KOREA_INVESTMENT_KEY_PATH")
    if not key_path:
        logger.error("KOREA_INVESTMENT_KEY_PATH 환경 변수가 설정되지 않았습니다.")
        raise ValueError("KOREA_INVESTMENT_KEY_PATH 환경 변수가 설정되지 않았습니다.")

    try:
        with open(key_path) as f:
            lines = f.readlines()
            if len(lines) < 3:
                logger.error(f"키 파일 {key_path}의 형식이 잘못되었습니다. 3줄이 필요합니다.")
                raise ValueError(f"키 파일 {key_path}의 형식이 잘못되었습니다.")
            
            key = lines[0].strip()
            secret = lines[1].strip()
            acc_no = lines[2].strip()

        logger.info(f"API Key: {key[:5]}..., Secret Key: {secret[:5]}..., Account No: {acc_no}")

        broker = mojito.KoreaInvestment(
            api_key=key,
            api_secret=secret,
            acc_no=acc_no
        )

        logger.info("Broker 생성 성공")
        return broker
    except FileNotFoundError:
        logger.error(f"키 파일 {key_path}을 찾을 수 없습니다.", exc_info=True)
        raise
    except IndexError:
        logger.error(f"키 파일 {key_path}의 형식이 잘못되었습니다.", exc_info=True)
        raise
    except Exception as e:
        logger.error(f"Broker 생성 중 오류 발생: {str(e)}", exc_info=True)
        raise
