# Ohcoach Cell Tools

셀 에서 추출한 `.ftg` 파일의 파싱 및 데이터 분석을 지원하기 위한 툴들의 모음

## R&R

- Repository 담당팀: @fitogether-org/data-platform
- Repository 담당자: @fito-domin
## Features

- Cell Parser
- Services
  - [AWS Lambda] Intermed Generator
- Parsing Scripts

## Install (Windows - Pycharm)
```
1. pycharm standard 기준 설치 후
2. python 3.9 이상으로 윈도우 설치 (https://www.python.org/downloads/release/python-392/)
3. pycharm 에서 python 3.9 interpreter 로 설정
4. pands / timezonefinder package 설치
```
- 실행
```
1. terminal 명령어 -> cd scripts -> python parse.py ```directory path``` -t rgp/rim/rbs
2. 실행 후 정상적으로 완료 되었다면, 해당 폴더 path 에 result 라는 폴더 명으로 CSV 파일
```

## Install (MAC)
### Poetry 설치
```shell script
$ curl -sSL https://install.python-poetry.org | python3.9 -
```
- 참고) Poetry uninstall
```shell script
$ curl -sSL https://install.python-poetry.org | python3.9 - --uninstall
```

- Peotry PATH 설정
.zshrc 에 다음 줄 추가 (poetry install 스크립트 실행 후 위치가 나옵니다.)
```
(example) export PATH="/Users/jbshin/Library/Python/3.10/bin:$PATH"
```

- 가상환경 실행
```shell script
$ poetry shell
```

### 패키지 설치
```shell script
$ poetry install
```

- (M1 맥북용) proj & pyproj 설치
```shell script
$ brew install proj
$ pip install pyproj --no-binary pyproj
```


### 유닛 테스트 실행
```shell script
$ poetry run pytest
```

### code coverage 실행
```shell script
$ poetry run pytest --cov=ohcoach_cell_tools --cov-report term-missing --no-cov-on-fail
```
- \--cov
  - 커버리지 검사하는 파일 경로
- \--cov-report
  - 검사 결과 보기
  - term-missing
    - 코드 빠진 라인 보기
- \--no-cov-on-fail
  - 테스트 코드 fail 시 report 출력 안 함

### Pre-commit, pre-push git hooks installation
- Git pre-commit hook
commit을 수행하기전에 코드 스타일/타입 체킹을 수행하는 hook 입니다.
```shell script
$ pre-commit install
```

- Git pre-push hook
Remote에 Push하기 직전에 pytest를 수행하는 hook 입니다.

```shell script
$ touch .git/hooks/pre-push
$ chmod +x .git/hooks/pre-push
$ cat <<EOF >> .git/hooks/pre-push
poetry run pytest
status=$?

if [ $status != 0 ]; then
    echo 'TEST FAILED! GIT PUSH REJECTED' && exit 1
else
    exit 0
fi
EOF
```
## Git LFS 설치 (대용량 파일 관리 시스템)
Remote에 Push 할 때, 필요한 대용량 파일 관리 Tool 입니다.
```
$ brew install git-lfs
$ git lfs install
```
- .gitattributes 로 관리
- 필요한 파일 관리
  ```
  $ git lfs track "*.gp"
  ```
- file push
  ```
  $ git lfs push origin main --all
  ```
### Change Python Version
- pyproject.toml 파일의
  ```
  [tool.poetry.dependencies]
  python = "^3.9"
  ```
  부분을 해당 버전에 맞게 변경
- Python 실행환경 변경
```shell script
$ poetry use path/to/python
ex> $ poetry use /opt/homebrew/bin/python3.9
```
- 결과:
```
Creating virtualenv ohcoach-cell-tools-gpWfayfC-py3.9 in /Users/jbshin/Library/Caches/pypoetry/virtualenvs
Using virtualenv: /Users/jbshin/Library/Caches/pypoetry/virtualenvs/ohcoach-cell-tools-gpWfayfC-py3.9
```
- Poetry Lock 업데이트
```shell script
$ poetry lock
```

## Deployment

git tag 명령을 사용하여 tag push 에만 배포하도록 하였습니다.
(PR, branch Commit/Push 등에는 동작하지 않음)

### 예제
```shell script
$ git tag dev-converter-220209
$ git push origin dev-converter-220209
```

### Tag 형식
`{ENV}-{Lambda Function}-{DATE}`

- ENV: `dev` | `test` | `stg` | `prod`
- Lambda Function:
  - `converter` : lambda_function_ftg_to_gp_im_converter
  - `intermed` : lambda_function_intermed_generator
  - `intermed_ftg` : lambda_function_imtermed_generator_newcell
  - `unzip` : lambda_function_unzip_ftg
    - 환경 구별 없음
  - TBA
- DATE: 날짜인데 배포스크립트에서 의미는 없기 때문에 자유롭게 기술 가능

## Scripts
### Parse
- 용도: 로컬 파싱용 스크립트
  - 파싱 동작 확인
  - 파싱 에러 확인
  - 기타 실험

- 실행 방법
```shell script
$ poetry run parse ./data/220307 -d ./parsing_results -t rgp/rim/rbs
```

- 도움말
```shell script
$ poetry run parse -h
```
```
usage: parse [-h] [--destination DESTINATION] [--target TARGET] source

A Script for Ohcoach Cell Tools

positional arguments:
  source                place where ftg files are stored

optional arguments:
  -h, --help            show this help message and exit
  --destination DESTINATION, -d DESTINATION
                        place where result files will be stored
  --target TARGET, -t TARGET
                        format to be parsed as: rgp/rim/rbs | gp/im | both
```

- source: 필수
  - 파일: ex> ./data/220307/CLBX-4B-41561_4.6_0_1646640018_0.ftg
  - 디렉토리: ex> ./data/220307

- destination: 옵션 - 지정하지 않으면 `source` 의 디렉토리로 자동 지정

- target: 옵션
  - `both`: rgp, rim, rbs 및 gp, im 모두 출력
  - `rgp/rim/rbs`
  - `gp/im`

### Datetime Converter
- 용도: ftg/rgp/rim/rbs datetime 변경
  - intermed/team_221/09/01/CLBX-4B-41561_5.9_0_1662001969 활용
  - 원하는 날짜와 시간대의 데이터 등록을 하기 위함
  - 로컬에서 입력받은 날짜와 시간을 기준으로 하여 약 2시간 가량의 data 저장
  - scripts/datetime_converter/results 하위에 결과 저장

- 실행 방법
```shell script
$ poetry run converter 2022-02-22
```

```shell script
$ poetry run converter 2022-02-22 -t 15:00:00
```

- 도움말
```shell script
$ poetry run converter -h
```
```
usage: converter [-h] [--time TIME] date

A Script for datetime converter

positional arguments:
  date                  date you want to change (ex. 2022-02-22)

optional arguments:
  -h, --help            show this help message and exit
  --time TIME, -t TIME  time you want to change (defalut 00:00:00)
```

- date: 필수 - 원하는 날짜: 2022-02-22 dash를 포함하여 입력

- time: 옵션 - 지정하지 않으면 입력 날짜의 00:00:00 으로 자동 지정
### Verification
- 용도 : computed.csv와 action.csv의 값 검증을 위한 스크립트
  - computed aggregate, action aggregate, interval_summary(1m, 5m, 15m)
- 파일 이름 규칙
  1. 단일 파일만 사용하여 검증하는 경우
    - *_computed.csv
    - *_action.csv
  2. interval_summary를 포함하여 검증하는 경우
    - 동일한 prefix 필요
    - {prefix}_computed.csv, {predix}_action.csv


- 실행 방법
```shell
poetry run verification ./data/verification/
```
```shell
poetry run verification ./data/verification/ -ad="2022-11-15 01:07:01.700"
```
```shell
poetry run verification ./data/verification/ -formation "2022-11-15 01:00:00" "2022-11-15 03:00:00"
```
```shell
poetry run verification ./data/verification/ -heatmap 10500 7400
```
- 도움말
```shell
poetry run verification -h
```
```
usage: verification [-h] [--destination DESTINATION] [--action_data_detail_datetime ACTION_DATA_DETAIL_DATETIME] [--session_data_formation_datetime SESSION_DATA_FORMATION_DATETIME]
                    [--session_data_heatmap_stadium SESSION_DATA_HEATMAP_STADIUM [SESSION_DATA_HEATMAP_STADIUM ...]]
                    source

A Script for Computed, Action csv data Verification

positional arguments:
  source                place where computed, action files are stroed

optional arguments:
  -h, --help            show this help message and exit
  --destination DESTINATION, -d DESTINATION
                        place where result files will be stroed
  --action_data_detail_datetime ACTION_DATA_DETAIL_DATETIME, -ad ACTION_DATA_DETAIL_DATETIME
                        Write the action data detail datetime to aggregate
  --session_data_formation_datetime SESSION_DATA_FORMATION_DATETIME, -formation SESSION_DATA_FORMATION_DATETIME
                        Write the sesstion data formaion datetime to aggregate
  --session_data_heatmap_stadium SESSION_DATA_HEATMAP_STADIUM [SESSION_DATA_HEATMAP_STADIUM ...], -heatmap SESSION_DATA_HEATMAP_STADIUM [SESSION_DATA_HEATMAP_STADIUM ...]
                        Write the sesstion data heatmap stadium coordinate to aggregate
```
- source: 필수
  - 파일: ex> ./data/verification/test_computed.csv
  - 디렉토리: ex> ./data/verification

- destination: 옵션 - 지정하지 않으면 `source` 의 디렉토리로 자동 지정
- action_data_detail_datetime: 옵션 - action data detail aggregate를 위한 datetime을 입력
  - ex) -ad="2022-11-15 01:42:17"
- session_data_formation_datetime: 옵션 - session data formaion aggregate를 위한 datetime을 입력
  - 시작 datetime과 끝 datetime은 공백으로 구분
  - ex) -formation "2022-11-15 01:42:17" "2022-11-15 01:58:13"

- sesstion_data_heatmap_stadium: 옵션 - sesstion data heatmap aggregate를 위한 stadium의 legnth와 width을 입력
  - length, width 순으로 입력
  - ex) -heatmap 10500 7400
## backoffice-graph
- ftg 파일을 파싱하여 그래프로 보여주기 위한 tool
- 그래프로 볼 수 있는 정보
  - rgp : h_acc, v_acc, pos_mode(n / a or d)를 구분한 h_acc/ v_acc, speed
  - rim : acc_x
  - rbs : hr, battery, cell_temperature, cell_state, reserve_2, reserve_3
- 데이터 테이블로 볼 수 있는 정보
  - 파일 이름, index, start 메시지, end 메시지, error
- 실행방법
  ```shell
  $ cd backoffice
  $ python3 app.py
  ```
  or
  ```shell
  $ python3 backoffice/app.py
  ```
- [사용방법 노션 링크](https://www.notion.so/fitogether/backoffice-0bf6cb114ea64a63b36e8c8daeef594d)
