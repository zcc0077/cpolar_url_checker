import random
import sys

import requests
from bs4 import BeautifulSoup
import json
import time
import os
import logging
import urllib3

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

g_tunnels = {}
g_token = ''
g_sleep = 1800


def push_wechat(title, msg):
    try:
        global g_token
        url = 'http://www.pushplus.plus/send'
        data = {
            "token": g_token,
            "title": title,
            "content": msg
        }
        body = json.dumps(data).encode(encoding='utf-8')
        headers = {'Content-Type': 'application/json'}
        response = requests.post(url, data=body, headers=headers)
        if response.status_code != 200:
            logging.error(f'Fail to send message to wechat, response: {response.text}')
    except Exception as e:
        logging.error(f"Pushplus 推动失败: {e}")


def read_config():
    global g_token, g_sleep
    config_path = '/app/config/config.json'

    if os.path.isfile(config_path):
        try:
            with open(config_path, 'r') as file:
                config = json.load(file)
            username = config.get('username', '')
            password = config.get('password', '')
            g_token = config.get('token', '')
            g_sleep = config.get('sleep', 1800)
        except Exception as e:
            logging.error(f"Error reading config file: {e}")
            sys.exit(1)
    else:
        logging.warning("Config file not found, please check!")
        sys.exit(1)

    return username, password


def login(session, username, password):
    try:
        login_page_url = 'https://dashboard.cpolar.com/login'
        login_page_response = session.get(login_page_url, verify=False)
        login_page_soup = BeautifulSoup(login_page_response.text, 'html.parser')

        login_form = login_page_soup.find('form')

        hidden_inputs = login_form.find_all('input', type='hidden')
        form_data = {input.get('name'): input.get('value') for input in hidden_inputs}

        form_data['login'] = username
        form_data['password'] = password

        login_action_url = login_form.get('action')
        if not login_action_url.startswith('http'):
            login_action_url = 'https://dashboard.cpolar.com' + login_action_url
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        response = session.post(login_action_url, data=form_data, headers=headers, verify=False)

        response_soup = BeautifulSoup(response.text, 'html.parser')
        alert_error = response_soup.find('div', class_='alert alert-error')
        if alert_error:
            logging.error(f"Login failed: {alert_error.text.strip()}")
            push_wechat('cpolar登录失败', f'登录失败: {alert_error.text.strip()}')
            return False

        return True
    except Exception as e:
        push_wechat('cpolar登录解析异常', f'错误: {e}')
        logging.error(f"Error during login: {e}")
        return False


def get_status_page(session):
    try:
        status_url = 'https://dashboard.cpolar.com/status'
        response = session.get(status_url, verify=False)
        return response.text, response.url
    except Exception as e:
        push_wechat('cpolar解析异常', f'错误: {e}')
        logging.error(f"Error getting status page: {e}")
        return None, None


def parse_status_page(html):
    tunnels = {}
    try:
        soup = BeautifulSoup(html, 'html.parser')
        table = soup.find('table', {'class': 'table table-sm'})

        if table:
            rows = table.find('tbody').find_all('tr')
            for row in rows:
                name_td = row.find('td')
                url_th = row.find('th')
                if name_td and url_th:
                    name = name_td.text.strip()
                    a_tag = url_th.find('a')
                    if a_tag and ".top" in a_tag['href']:
                        url = a_tag['href']
                        if name in tunnels:
                            tunnels[name].append(url)
                        else:
                            tunnels[name] = [url]
    except Exception as e:
        push_wechat(f'status页面无法加载，请及时修复', f'错误:{e}')
        logging.error(f"Error parsing status page: {e}")

    return tunnels


def main():
    global g_tunnels
    username, password = read_config()
    session = requests.Session()

    while True:
        try:
            status_page, current_url = get_status_page(session)
            if current_url and current_url.endswith('/status'):
                logging.info('Succeed to get status page')
            else:
                logging.warning('Session expired, need to re-Login.')
                logged_in = login(session, username, password)
                if logged_in:
                    logging.info('Login successful')
                    status_page, current_url = get_status_page(session)
                else:
                    logging.error('Login failed')
                    time.sleep(g_sleep + random.randint(20, 120))
                    continue

            if status_page:
                tunnels = parse_status_page(status_page)
                for tunnel in tunnels:
                    logging.info(f"隧道名称: {tunnel}, 公网地址: {tunnels[tunnel]}")
                    str_tunnel = json.dumps(tunnels[tunnel], indent=4, ensure_ascii=False)
                    if tunnel not in g_tunnels:
                        push_wechat(f'检测到新的隧道[{tunnel}]', f'公网地址:{str_tunnel}')
                        logging.info(f"检测到新的隧道: {tunnel}, 公网地址: {tunnels[tunnel]}")
                        g_tunnels[tunnel] = tunnels[tunnel]
                    for url in tunnels[tunnel]:
                        if url not in g_tunnels[tunnel]:
                            push_wechat(f'隧道[{tunnel}]地址发生变化', f'新的隧道地址:{tunnels[tunnel]}')
                            g_tunnels[tunnel] = tunnels[tunnel]
                            break
            else:
                logging.error('Failed to get status page')

            time.sleep(g_sleep + random.randint(20, 120))
        except Exception as e:
            push_wechat('未识别的错误', f'错误: {e}')
            logging.error(f"Unexpected error: {e}")
            time.sleep(g_sleep + random.randint(20, 120))


if __name__ == '__main__':
    main()
