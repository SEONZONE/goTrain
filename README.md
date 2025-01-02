![SRT흐름](https://github.com/user-attachments/assets/8f3bbee5-a31d-4348-a5a3-7d96e56c4010)


```
[프론트엔드 - React]
        ↓
[웹 서버 - Node.js] → [MySQL]
        ↓
[예약 서버 - Flask/Selenium] → [Redis]
```

# 서비스 구조 명세서

## 1. 웹 서버 (API Server)
### 기술 스택
- Node.js
- MySQL
- Docker

### 주요 기능
- 회원 관리
- 예약 내역 관리
- 프론트엔드와 통신
- 예약 서버와 통신

## 2. 예약 서버 (Crawler Server)
### 기술 스택
- Flask
- Redis
- Selenium (Headless)
- Docker

### 주요 기능
- SRT 예약 자동화
- 작업 상태 관리
- 비동기 처리 (Thread)

## 3. 프론트엔드
### 기술 스택
- React

## 4. 인프라
- AWS EC2
  - 웹 서버: t2.micro 
  - 예약 서버: t2.small or medium
- GitHub Actions (CI/CD)

