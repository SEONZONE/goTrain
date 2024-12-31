from flask import Flask, request, jsonify
from threading import Thread
from uuid import uuid4
from redis import Redis
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.select import Select
from modules.selenium import *
from flask_cors import CORS 
from datetime import datetime
import json
import time
import webbrowser
import logging
from logging.handlers import TimedRotatingFileHandler
import os


##################### 로그 #####################
log_dir = 'logs'
if not os.path.exists(log_dir):
    os.makedirs(log_dir)
    
logger = logging.getLogger('SRT_API')
logger.setLevel(logging.DEBUG)

file_handler = TimedRotatingFileHandler(
    filename=os.path.join(log_dir, 'srt-api.log'),
    when='midnight',
    interval=1,
    backupCount=30,
    encoding='utf-8'
)

formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

###############################################


#Flask 설정
app = Flask(__name__)
CORS(app, supports_credentials=True)

#Redis 설정
redis_client = Redis(host='localhost',port=6379)



# 예약시스템
def ticket_start(ticket_info,task_id):
    driver = None
    try:
        chrome_options = webdriver.ChromeOptions()
        chrome_options.add_argument('--headless')  # GUI 없이 실행
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_path = 'C:/Program Files (x86)/Google/Chrome/Application/chrome.exe %s'

        reserved = False

        # webdriver 파일의 경로 입력
        # 같은 디렉토리에 있기 때문에 chromedriver.exe파일 이름만 써줌
        logger.debug(f"selenium version: {get_selenium_version()}")

        # selenium 버전에 따른 webdriver 분기
        v1, v2, v3 = get_selenium_version().split(".")
        driver = webdriver.Chrome(options=chrome_options) if int(v1) < 4 else webdriver.Chrome(options=chrome_options)


        # 이동을 원하는 페이지 주소 입력
        driver.get('https://etk.srail.co.kr/cmc/01/selectLoginForm.do')
        driver.implicitly_wait(15)


        # 회원번호 매핑
        driver.find_element(By.ID, 'srchDvNm01').send_keys(ticket_info['memberNumber'])

        # 비밀번호 매핑
        driver.find_element(By.ID, 'hmpgPwdCphd01').send_keys(ticket_info['password'])

        # 확인 버튼 클릭
        driver.find_element(By.XPATH, '/html/body/div/div[4]/div/div[2]/form/\
            fieldset/div[1]/div[1]/div[2]/div/div[2]/input').click()
        driver.implicitly_wait(5)

        driver.get('https://etk.srail.kr/hpg/hra/01/selectScheduleList.do')
        driver.implicitly_wait(5)


        # 출발지 입력
        dep_stn = driver.find_element(By.ID, 'dptRsStnCdNm')
        dep_stn.clear()
        dep_stn.send_keys(ticket_info['arrival'])

        # 도착지 입력
        arr_stn = driver.find_element(By.ID, 'arvRsStnCdNm')
        arr_stn.clear()
        arr_stn.send_keys(ticket_info['departure'])

        # 날짜 드롭다운 리스트 보이게
        Select(driver.find_element(By.ID,"dptDt")).select_by_value(ticket_info['standardDate'])

        # 출발 시간
        Select(driver.find_element(By.ID, "dptTm")).select_by_visible_text(ticket_info['standardTime'])

        # 조회하기 버튼
        driver.find_element(By.XPATH, "//input[@value='조회하기']").click()


        train_list = driver.find_elements(By.CSS_SELECTOR, "#result-form > fieldset > \
        div.tbl_wrap.th_thead > table > tbody > tr")

        while True: 
            
            try:
                logger.debug(f"[예약시도][task:{task_id}]")
                #취소 요청이 왔을 경우
                cancle_flag = redis_client.hget(f"task:{task_id}","cancel")
                if cancle_flag == b'true':
                    redis_client.hset(f"task:{task_id}", "status", "cancelled")
                    redis_client.hset(f"task:{task_id}", "message", "사용자 요청으로 취소됨")
                    logger.debug(f"[예약취소] 사용자 요청으로 취소됨. task: task:{task_id}")
                    return "cancelled"
                for i in range(ticket_info['fromTrainNumber'],ticket_info['toTrainNumber'] + 1):
                    standard_seat = driver.find_element(By.CSS_SELECTOR, f"#result-form > fieldset > div.tbl_wrap.th_thead > table > tbody > tr:nth-child({i}) > td:nth-child(7)").text

                    if "예약하기" in standard_seat:
                        logger.debug(f"[예약가능클릭][task:{task_id}]")
                        driver.find_element(By.XPATH, f"/html/body/div[1]/div[4]/div/div[3]/div[1]/\
                        form/fieldset/div[6]/table/tbody/tr[{i}]/td[7]/a/span").click()
                        driver.implicitly_wait(3)

                        if driver.find_elements(By.ID, 'isFalseGotoMain'):
                            reserved = True
                            logger.debug(f'[예약성공][task:{task_id}]')
                            webbrowser.get(chrome_path).open("https://etk.srail.kr/hpg/hra/02/selectReservationList.do?pageId=TK0102010000")
                            # return(jsonify({'success':'예약성공'}), 200)
                            return "success"
                        else:
                            logger.debug("잔여석 없음. 다시 검색")
                            driver.back() #뒤로가기
                            driver.implicitly_wait(5)
                    else :
                        try:
                            standby_seat = driver.find_element(By.CSS_SELECTOR, f"#result-form > fieldset > div.tbl_wrap.th_thead > table > tbody > tr:nth-child({i}) > td:nth-child(8)").text

                            if "신청하기" in standby_seat:
                                logger.debug(f"[예약대기신청][task:{task_id}]")
                                driver.find_element(By.XPATH, f"/html/body/div[1]/div[4]/div/div[3]/div[1]/\
                                form/fieldset/div[6]/table/tbody/tr[{i}]/td[8]/a/span").click()
                                driver.implicitly_wait(3)

                                if driver.find_elements(By.ID, 'isFalseGotoMain'):
                                    reserved = True
                                    logger.debug(f'[예약성공][task:{task_id}]')
                                    webbrowser.get(chrome_path).open("https://etk.srail.kr/hpg/hra/02/selectReservationList.do?pageId=TK0102010000")
                                    # return(jsonify({'success':'예약성공'}), 200)
                                    return "success"
                                else:
                                    logger.debug(f"[예약 대기 신청 실패. 다시 검색][task:{task_id}]")
                                    driver.back() #뒤로가기
                                    driver.implicitly_wait(5)

                        except Exception as e: 
                            logger.debug(f"[예약 대기 신청 불가][task:{task_id}]")
                            pass
            except Exception as e: 
                logger.debug(f'[error][message]${e}')
                pass
        
            if not reserved:
                try:
                # 다시 조회하기
                    submit = driver.find_element(By.XPATH, "/html/body/div/div[4]/div/div[2]/form/fieldset/div[2]/input")
                    driver.execute_script("arguments[0].click();", submit)

                except: 
                    logger.debug("잔여석 없음 #2. 초기화")
                    driver.back() #뒤로가기
                    driver.implicitly_wait(5)

                    driver.refresh() #새로고침
                    driver.implicitly_wait(5)
                    pass

                # 2초 대기
                driver.implicitly_wait(10)
                time.sleep(2)

            else:
                time.sleep(1000)
                break
    except Exception as e:
        return jsonify({'error':str(e)}), 500
    finally:
        if driver:
            driver.quit()


#백그라운드 테스크 실행
def background_task(ticket_info, task_id):
    try:
        # Redis에 작업 시작 상태 저장
        redis_client.hset(
            f"task:{task_id}",
            mapping={
                "status": "running",
                "message": "예약 프로세스 시작",
                "created_at": datetime.now().strftime('%Y%m%d%H%M%S%f'),
                "cancel" : "false"
            }
        )
        logger.debug(f"[예약프로세스 시작] 회원번호: {ticket_info['memberNumber']} task: task:{task_id}")
        # 기존 티켓 예약 로직 실행
        result = ticket_start(ticket_info,task_id)
        
        if result == "success":
            # 성공시 Redis에 완료 상태 저장
            redis_client.hset(
                f"task:{task_id}",
                mapping={
                    "status": "completed",
                    "message": "예약 완료",
                    "created_at": datetime.now().strftime('%Y%m%d%H%M%S%f')
                }
            )
            logger.debug(f"[예약완료] 회원번호: {ticket_info['memberNumber']} task: task:{task_id}")
    except Exception as e:
        # 실패시 Redis에 에러 상태 저장
        redis_client.hset(
            f"task:{task_id}",
            mapping={
                "status": "failed",
                "cancel" : "true",
                "message": str(e)
            }
        )    
        
        logger.debug(f"[예약프로세스 에러] 회원번호: {ticket_info['memberNumber']} task: task:{task_id}")

# 예약API 
@app.route('/srt/booking',methods=['POST'])
def srt():
    try:
        data = request.get_json()
        
        task_id = str(uuid4())
        ticket_info = {
            'memberNumber': data.get('memberNumber'),    # 회원번호
            'password': data.get('password'),            # 비밀번호
            'arrival': data.get('arrival'),              # 출발지
            'departure': data.get('departure'),          # 도착지
            'standardDate': data.get('standardDate'),    # 기준날짜 ex) 20221101
            'standardTime': data.get('standardTime'),    # 기준 시간 ex) 00 - 22 // 2의 배수로 입력
            'fromTrainNumber': data.get('fromTrainNumber'),  # 몇번째 기차부터 조회할지 min = 1, max = 10
            'toTrainNumber': data.get('toTrainNumber')      # 몇번째 기차까지 조회할지 min = from_train_number, max = 10
        }
        
        #쓰레드 설정
        thread = Thread(
            target=background_task,
            args=(ticket_info,task_id),
            daemon=True
        )
        
        thread.start()
        
        # 즉시 응답 반환
        return jsonify({
            'message': '예약 프로세스가 시작되었습니다.',
            'task_id': task_id
        }), 200
        
    except Exception as e:
        return jsonify({'error':str(e)}), 500


#예약현황 상태관리
@app.route('/status/<task_id>', methods=['GET'])
def get_status(task_id):
    logger.debug(f"[예약프로세스 상태 조회]  task: task:{task_id}")
    status = redis_client.hgetall(f"task:{task_id}")    # Redis에서 상태 조회
    
    status = {
        k.decode('utf-8'): v.decode('utf-8')
        for k, v in status.items()
    }
    
    
    if not status:
        return jsonify({'error': '작업을 찾을 수 없습니다'}), 404
    return jsonify(status), 200

#예약 취소 API
@app.route('/srt/cancel/<task_id>', methods=['POST'])
def cancel_srt(task_id):
    try:
        logger.debug(f"[예약프로세스 취소]  task: task:{task_id}")
        # Redis에 작업 취소 상태 저장
        redis_client.hset(
            f"task:{task_id}",
            mapping={
                "status": "cancel",
                "message": "예약 프로세스 취소",
                "created_at": datetime.now().strftime('%Y%m%d%H%M%S%f'),
                "cancel" : "true"
            }
        )
        logging.info(f"[예약프로세스 취소] task: task:{task_id}")
        # 즉시 응답 반환
        return jsonify({
            'message': '취소 요청이 등록 되었습니다..',
            'task_id': task_id
        }), 200
        
    except Exception as e:
        return jsonify({'error':str(e)}), 500
    
if __name__ == '__main__':   
    logger.debug("Starting SRT API server")
    # app.run(host='0.0.0.0', port=5000, debug=True)
    app.run(debug=False)