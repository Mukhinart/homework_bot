import logging
import os
import sys
import time
from http import HTTPStatus
from logging import StreamHandler

import requests
import telegram
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

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


def send_message(bot, message):
    """Отправка сообщения в Telegram-чат."""
    try:
        logger.info(
            f'Начата отправка сообщения "{message}"'
            f' в чат {TELEGRAM_CHAT_ID}'
        )
        bot.send_message(TELEGRAM_CHAT_ID, message)
    except Exception:
        logger.error('Ошибка отправки сообщения в телеграм')
    else:
        logger.info(
            f'Сообщение "{message}" успешно отправлено'
            f' в чат {TELEGRAM_CHAT_ID}'
        )


def get_api_answer(current_timestamp):
    """Запрос к эндпоинту API-домашки."""
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    try:
        logger.info('Начат процесс запроса к основному API')
        api_answer = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params=params
        )
    except Exception as error:
        raise Exception(f'Ошибка при запросе к основному API: {error}')
    if api_answer.status_code != HTTPStatus.OK:
        status_code = api_answer.status_code
        raise Exception(f'Ошибка {status_code} при запросе к странице домашки')
    return api_answer.json()


def check_response(response):
    """Проверка ответа API на корректность."""
    if not isinstance(response, dict):
        type_response = type(response)
        raise TypeError(
            f'Ошибка: API возвращает тип данных {type_response}'
            f' вместо словаря'
        )
    try:
        homework_list = response['homeworks']
    except KeyError:
        raise KeyError('Ошибка словаря по ключу "homeworks"')
    try:
        homework = homework_list[0]
    except IndexError:
        raise IndexError('Пустой список домашних работ')
    return homework


def parse_status(homework):
    """Извлечение статуса конкретной домашней работы."""
    if 'homework_name' not in homework:
        raise KeyError('Отсутствует ключ "homework_name" в ответе API')
    if 'status' not in homework:
        raise KeyError('Отсутствует ключ "status" в ответе API')
    homework_name = homework['homework_name']
    homework_status = homework['status']
    if homework_status not in HOMEWORK_STATUSES:
        raise Exception(f'Неизвестный статус работы: {homework_status}')
    verdict = HOMEWORK_STATUSES[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Проверка доступности переменных окружения."""
    return all([PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID])


def main():
    """Основная логика работы бота."""
    STATUS_MESSAGE = {}
    ERROR_MESSAGE = ''
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    if not check_tokens():
        logger.critical('Отсутствуют одна или несколько переменных окружения')
        raise Exception('Отсутствуют одна или несколько переменных окружения')
    while True:
        try:
            response = get_api_answer(current_timestamp)
            message = parse_status(check_response(response))
            current_timestamp = response.get('current_date')
            if message != STATUS_MESSAGE:
                send_message(bot, message)
                STATUS_MESSAGE = message.copy()
        except Exception as error:
            logger.error(error)
            err_message = f'Сбой в работе программы: {error}'
            if err_message != ERROR_MESSAGE:
                send_message(bot, err_message)
                ERROR_MESSAGE = err_message
        finally:
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    logger.setLevel(logging.DEBUG)
    handler = StreamHandler(stream=sys.stdout)
    logger.addHandler(handler)
    formatter = logging.Formatter(
        '[%(asctime)s: %(levelname)s] %(name)s %(message)s, %(funcName)s'
    )
    handler.setFormatter(formatter)
    main()
