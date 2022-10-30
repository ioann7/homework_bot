import os
import time
import logging
from typing import Optional, Union
from http import HTTPStatus

import telegram
from telegram.error import TelegramError
import requests
from dotenv import load_dotenv

from exceptions import (MissingEnvironmentVariable,
                        EndpointBadResponse)


load_dotenv()


logger = logging.getLogger(__name__)
stream_handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')
stream_handler.setFormatter(formatter)
logger.addHandler(stream_handler)
logger.setLevel(logging.DEBUG)


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


TApiAnswer = dict[str, Union[list, int]]


def send_message(bot: telegram.Bot, message: str) -> None:
    """
    Sends message to Telegram chat.
    Defined by environment variable `TELEGRAM_CHAT_ID`.
    """
    try:
        bot.send_message(text=message, chat_id=TELEGRAM_CHAT_ID)
        logger.info(f'Bot sent message: {message}')
    except TelegramError as e:
        logger.error(f'Message {message} is not sending. Error: {e}')


def get_api_answer(current_timestamp: Optional[int] = None) -> TApiAnswer:
    """Makes a request to yandex homework API."""
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}

    try:
        response = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params=params
        )
        if response.status_code == HTTPStatus.INTERNAL_SERVER_ERROR:
            raise EndpointBadResponse('Response status code == 500')
        if response.status_code != HTTPStatus.OK:
            raise EndpointBadResponse('Response status code != 200')
        response = response.json()
    except Exception as e:
        error_message = f'Homework endpoint request was not sent. Error: {e}'
        logger.error(error_message)
        raise EndpointBadResponse(error_message)
    return response


def check_response(response: TApiAnswer) -> list:
    """Checks API response for correctness."""
    error_message = None
    if not isinstance(response, dict):
        error_message = 'Response is not a dict.'
        logger.error(error_message)
        raise TypeError(error_message)
    try:
        homeworks = response['homeworks']
    except KeyError as e:
        error_message = f'`response` missing key `homeworks`. Error {e}'
        logger.error(error_message)
        raise KeyError(error_message)
    if not isinstance(response['homeworks'], list):
        error_message = 'response["homeworks"] is not list'
        logger.error(error_message)
        raise EndpointBadResponse(error_message)
    if not homeworks:
        logger.debug('No new statuses')
    return homeworks


def parse_status(homework: dict) -> str:
    """Extract homework status from concrete homework."""
    if not isinstance(homework, dict):
        error_message = '`homework` is not a dict'
        logger.error(error_message)
        raise TypeError(error_message)
    try:
        homework_name = homework['homework_name']
    except KeyError as e:
        error_message = f'`homework` missing key `homework_name`. Error: {e}'
        logger.error(error_message)
        raise KeyError(error_message)
    try:
        homework_status = homework['status']
    except KeyError as e:
        error_message = f'`homework` missing key `status`. Error: {e}'
        logger.error(error_message)
        raise KeyError(error_message)
    try:
        verdict = HOMEWORK_STATUSES[homework_status]
    except KeyError as e:
        error_message = f'Unexpected status. Error {e}'
        logger.error(error_message)
        raise KeyError(error_message)
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens() -> bool:
    """Checks the availability of environment variables."""
    environment_variables = (PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID)
    for variable in environment_variables:
        if variable is None:
            error_message = 'Missing environment variable `{variable}`'
            logger.critical(error_message)
            return False
    return True


def main() -> None:
    """The main logic of the bot."""
    if not check_tokens():
        raise MissingEnvironmentVariable

    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = 1

    while True:
        try:
            response = get_api_answer(current_timestamp)
            current_timestamp = int(time.time())
            new_homeworks = check_response(response)
            for homework in new_homeworks:
                message = parse_status(homework)
                send_message(bot, message)
            time.sleep(RETRY_TIME)
        except Exception as error:
            message = f'Program crash: {error}'
            send_message(bot, message)
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
