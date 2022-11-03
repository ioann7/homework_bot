import os
import time
import sys
import logging
from typing import Optional
from http import HTTPStatus

import telegram
from telegram.error import TelegramError
import requests
from dotenv import load_dotenv

from exceptions import (BaseStateDeviation,
                        SendMessageError, MissingNotRequiredKey,
                        EndpointBadResponse)


load_dotenv()


stream_handler = logging.StreamHandler(stream=sys.stdout)
file_handler = logging.FileHandler('logs.log', 'a')
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=(stream_handler, file_handler))


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def send_message(bot: telegram.Bot, message: str) -> None:
    """
    Sends message to Telegram chat.
    Defined by environment variable `TELEGRAM_CHAT_ID`.
    """
    try:
        logging.DEBUG(f'Bot starts sending message: {message}')
        bot.send_message(text=message, chat_id=TELEGRAM_CHAT_ID)
        logging.INFO(f'Bot sent message: {message}')
    except TelegramError as e:
        raise SendMessageError(f'Message {message} is not sending. Error: {e}')


def get_api_answer(current_timestamp: Optional[int] = None) -> dict:
    """Makes a request to yandex homework API."""
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}

    try:
        response = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params=params
        )
        if response.status_code != HTTPStatus.OK:
            raise EndpointBadResponse((
                f'Response status code {response.status_code} != 200\n'
                f'Response reason: {response.reason}\n'
                f'ENDPOINT: {ENDPOINT}\n'
                f'HEADERS: {HEADERS}\n'
                f'Params: {params}\n'
                f'Response text: {response.text}'
            ))
        return response.json()
    except Exception as e:
        raise EndpointBadResponse(
            f'Homework endpoint request was not sent. Error: {e}'
        )


def check_response(response: dict) -> list:
    """Checks API response for correctness."""
    logging.DEBUG(f'Starts checking api response {response}')
    if not isinstance(response, dict):
        raise TypeError('Response is not a dict.')

    homeworks = response.get('homeworks')
    current_date = response.get('current_date')

    if not homeworks:
        raise EndpointBadResponse(
            'Response missing required key `homeworks`'
        )
    if not current_date:
        raise MissingNotRequiredKey(
            'Response missing not required key `current_date`'
        )
    if not isinstance(homeworks, list):
        raise EndpointBadResponse(
            'response["homeworks"] is not list'
        )
    return homeworks


def parse_status(homework: dict) -> str:
    """Extract homework status from concrete homework."""
    if not isinstance(homework, dict):
        raise TypeError('`homework` is not a dict')
    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')
    if not homework_name:
        raise KeyError('`homework` missing key `homework_name`')
    if not homework_status:
        raise KeyError('`homework` missing key `status`')

    verdict = HOMEWORK_STATUSES.get(homework_status)
    if not verdict:
        raise KeyError('Unexpected status')
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens() -> bool:
    """Checks the availability of environment variables."""
    if all(PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID):
        return True
    return False


def main() -> None:
    """The main logic of the bot."""
    if not check_tokens():
        error_message = 'Missing environment variable'
        logging.CRITICAL(error_message)
        sys.exit(error_message)

    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())

    while True:
        try:
            response = get_api_answer(current_timestamp)
            current_timestamp = response.get('current_date', current_timestamp)
            new_homeworks = check_response(response)
            if not new_homeworks:
                logging.DEBUG('No new statuses')
            else:
                newest_homework = new_homeworks[0]
                message = parse_status(newest_homework)
                send_message(bot, message)
        except BaseStateDeviation as error:
            logging.ERROR(error)
        except Exception as error:
            logging.ERROR(error)
            message = f'Program crash: {error}'
            send_message(bot, message)
        finally:
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
