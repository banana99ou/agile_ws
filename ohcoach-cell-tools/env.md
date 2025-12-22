## ※ 각 환경마다 vpn이 다를 수 있습니다.
## .env
바라볼 환경 (dev | test | stg | prod)을 설정합니다.
```
ENV_MODE=dev
```
## .env.dev
```
DB_HOST_ULTIMATE=ohcoach-dev.ckphr4trm0oh.ap-northeast-2.rds.amazonaws.com
DB_ID_ULTIMATE=dev
DB_PW_ULTIMATE=FitoDev0331!
DB_DATABASE_DEFAULT_SCHEMA_ULTIMATE=ohcoach
ENV_S3_BUCKET=ohcoach-data.dev
```

## .env.test
```
DB_HOST_ULTIMATE=ohcoach-test.ckphr4trm0oh.ap-northeast-2.rds.amazonaws.com
DB_ID_ULTIMATE=dev
DB_PW_ULTIMATE=FitoDev0331!
DB_DATABASE_DEFAULT_SCHEMA_ULTIMATE=ohcoach
ENV_S3_BUCKET=ohcoach-data.test
```

## .env.stg
```
DB_HOST_ULTIMATE=fito-ohcoach-apne2-stg-mariadb.ckphr4trm0oh.ap-northeast-2.rds.amazonaws.com
DB_ID_ULTIMATE=application
DB_PW_ULTIMATE=FitoApp0331!
DB_DATABASE_DEFAULT_SCHEMA_ULTIMATE=ohcoach
ENV_S3_BUCKET=ohcoach-data.stg
```
## .env.prod
```
DB_HOST_ULTIMATE=ohcoach-prod-replica.ckphr4trm0oh.ap-northeast-2.rds.amazonaws.com
DB_ID_ULTIMATE=monitor
DB_PW_ULTIMATE=FitoMonitor0331!
DB_DATABASE_DEFAULT_SCHEMA_ULTIMATE=ohcoach
ENV_S3_BUCKET=ohcoach-data
```
